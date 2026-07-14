"""Achievements — pure functions over the event log.

An ``Achievement`` rule is a small callable that, given an ``AsyncSession``
and a ``(guild_id, user_id)`` pair, returns ``True`` if the player has
earned the badge. Evaluation is idempotent — a second run when the badge
is already recorded is a no-op courtesy of the ``player_badges`` unique
constraint.

The catalog is code-bound by key. Rows in the ``achievements`` table are
a lightweight registry the dashboard can render; the actual rule logic
lives in ``_RULES`` below. Adding a new achievement = add an entry in
``_RULES`` + an Alembic data-migration row.

Event triggers:
    * Per-stank / per-break events call ``evaluate_for_user`` after the
      scoring write — cheap O(badges) checks, most are early-returned by
      a single COUNT or EXISTS query.
    * Session-end calls ``evaluate_session_close`` to settle achievements
      that only resolve once a session boundary exists.

Positional achievements (ranking-based):
    Positional achievements (e.g. 4th place) are registered in
    ``_POSITIONAL_ACHIEVEMENTS``.  They share a single leaderboard query
    at session close and delegate to ``_evaluate_positional`` which
    handles ranking, tie-handling, and repeatable badge awarding.
    Adding a new positional achievement requires zero changes to
    ``evaluate_session_close`` — just add an entry to the registry.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import (
    Chain,
    ChainMessage,
    Event,
    EventType,
    PlayerBadge,
)
from stankbot.db.repositories import events as events_repo

log = logging.getLogger(__name__)


Rule = Callable[[AsyncSession, int, int], Awaitable[bool]]


@dataclass(slots=True, frozen=True)
class AchievementDef:
    key: str
    name: str
    description: str
    icon: str
    rule: Rule
    # Only evaluated on session close (needs session boundary state).
    session_close_only: bool = False
    # If True, the badge can be earned multiple times; award_count is incremented.
    repeatable: bool = False


@dataclass(slots=True)
class RankingResult:
    """Outcome of a positional/ranking achievement for one user."""

    user_id: int
    achievement_key: str
    sp_earned: int
    net_sp: int
    award_count: int


@dataclass(slots=True)
class SessionCloseResult:
    """Rich return type for ``evaluate_session_close``."""

    unlocks: dict[int, list[str]] = field(default_factory=dict)
    ranking_results: list[RankingResult] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class PositionalAchievement:
    """Generic positional/ranking achievement configuration.

    Fourth place is just ``PositionalAchievement(position=4, ...)``
    To add third place: ``PositionalAchievement(position=3, ...)``
    No changes to ``evaluate_session_close`` needed.
    """

    position: int
    achievement_key: str
    enabled_setting: str
    min_participants_setting: str
    min_participants_default: int = 4


# --- positional achievement constants & registry -------------------------

FOURTH_PLACE_KEY = "fourth_place"


_POSITIONAL_ACHIEVEMENTS: tuple[PositionalAchievement, ...] = (
    PositionalAchievement(
        position=4,
        achievement_key=FOURTH_PLACE_KEY,
        enabled_setting="fourth_place_enabled",
        min_participants_setting="fourth_place_min_participants",
        min_participants_default=4,
    ),
)


# --- individual rules -----------------------------------------------------


async def _first_stank(session: AsyncSession, guild_id: int, user_id: int) -> bool:
    stmt = (
        select(Event.id)
        .where(
            Event.guild_id == guild_id,
            Event.user_id == user_id,
            Event.type == EventType.SP_BASE,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def _chain_starter(session: AsyncSession, guild_id: int, user_id: int) -> bool:
    stmt = (
        select(Event.id)
        .where(
            Event.guild_id == guild_id,
            Event.user_id == user_id,
            Event.type == EventType.CHAIN_START,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def _finisher(session: AsyncSession, guild_id: int, user_id: int) -> bool:
    stmt = (
        select(Event.id)
        .where(
            Event.guild_id == guild_id,
            Event.user_id == user_id,
            Event.type == EventType.SP_FINISH_BONUS,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def _centurion(session: AsyncSession, guild_id: int, user_id: int) -> bool:
    # User has posted in at least one chain whose final_length >= 100
    # (still-alive chains with >=100 current messages also qualify).
    user_chain_ids = (
        select(ChainMessage.chain_id)
        .where(ChainMessage.user_id == user_id)
        .distinct()
    )
    count = func.count(ChainMessage.message_id)
    stmt = (
        select(Chain.id)
        .join(ChainMessage, ChainMessage.chain_id == Chain.id)
        .where(
            Chain.guild_id == guild_id,
            Chain.id.in_(user_chain_ids.scalar_subquery()),
        )
        .group_by(Chain.id)
        .having(count >= 100)
        .limit(1)
    )
    return (await session.execute(stmt)).first() is not None


async def _chainbreaker_dubious(
    session: AsyncSession, guild_id: int, user_id: int
) -> bool:
    stmt = (
        select(Chain.id)
        .where(
            Chain.guild_id == guild_id,
            Chain.broken_by_user_id == user_id,
            Chain.final_length >= 50,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def _comeback_kid(
    session: AsyncSession, guild_id: int, user_id: int
) -> bool:
    sp, pp = await events_repo.sp_pp_totals(session, guild_id, user_id)
    if sp - pp <= 0:
        return False
    # Must have been in the red at some point. Reconstruct by walking
    # events chronologically and tracking the running net.
    stmt = (
        select(Event.type, Event.delta)
        .where(
            Event.guild_id == guild_id,
            Event.user_id == user_id,
        )
        .order_by(Event.id.asc())
    )
    running = 0
    ever_negative = False
    _sp_types = {
        EventType.SP_BASE.value,
        EventType.SP_POSITION_BONUS.value,
        EventType.SP_STARTER_BONUS.value,
        EventType.SP_FINISH_BONUS.value,
        EventType.SP_REACTION.value,
        EventType.SP_TEAM_PLAYER.value,
        EventType.SP_FOURTH_PLACE.value,
    }
    async for row in await session.stream(stmt):
        t, delta = row
        if t in _sp_types:
            running += int(delta or 0)
        elif t == EventType.PP_BREAK.value:
            running -= int(delta or 0)
        if running < 0:
            ever_negative = True
    return ever_negative


async def _perfect_session(
    session: AsyncSession, guild_id: int, user_id: int
) -> bool:
    # At session close: user had at least one SP event this session and no
    # PP_BREAK events. "This session" = the most recently ended session.
    stmt = (
        select(Event.session_id)
        .where(
            Event.guild_id == guild_id,
            Event.type == EventType.SESSION_END,
        )
        .order_by(Event.id.desc())
        .limit(1)
    )
    last_session_id = (await session.execute(stmt)).scalar_one_or_none()
    if last_session_id is None:
        return False
    sp, pp = await events_repo.sp_pp_totals(
        session, guild_id, user_id, session_id=last_session_id
    )
    return sp > 0 and pp == 0


async def _streaker(
    session: AsyncSession, guild_id: int, user_id: int
) -> bool:
    # User stanked in >= 3 consecutive session_ids (ordered chronologically).
    session_ids = await events_repo.session_event_ids(session, guild_id)
    if len(session_ids) < 3:
        return False
    sp_session_set = set(
        await events_repo.session_ids_where_user_has_sp(session, guild_id, user_id)
    )
    run = 0
    for sid in session_ids:
        if sid in sp_session_set:
            run += 1
            if run >= 3:
                return True
        else:
            run = 0
    return False


async def _team_player(
    session: AsyncSession, guild_id: int, user_id: int
) -> bool:
    # Awarded whenever an SP_TEAM_PLAYER event has been recorded for the
    # user; the condition itself is checked when the event is emitted in
    # ChainService so this rule just needs presence.
    stmt = (
        select(Event.id)
        .where(
            Event.guild_id == guild_id,
            Event.user_id == user_id,
            Event.type == EventType.SP_TEAM_PLAYER,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def _voice_stank(
    session: AsyncSession, guild_id: int, user_id: int
) -> bool:
    """True if the user has ever submitted a voice stank."""
    stmt = (
        select(Event.id)
        .where(
            Event.guild_id == guild_id,
            Event.user_id == user_id,
            Event.type == EventType.VOICE_STANK,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def _gritty_voice(
    session: AsyncSession, guild_id: int, user_id: int
) -> bool:
    """True if the user has ever earned a grit bonus on a voice stank."""
    stmt = (
        select(Event.id)
        .where(
            Event.guild_id == guild_id,
            Event.user_id == user_id,
            Event.type == EventType.SP_GRIT_BONUS,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


# --- catalog --------------------------------------------------------------


async def _always_true(
    _session: AsyncSession, _guild_id: int, _user_id: int
) -> bool:
    """Stub rule — positional achievements decide eligibility via ranking."""
    return True


_RULES: tuple[AchievementDef, ...] = (
    AchievementDef(
        key="first_stank",
        name="First Stank",
        description="Dropped your very first stank.",
        icon="✨",
        rule=_first_stank,
    ),
    AchievementDef(
        key="chain_starter",
        name="Chain Starter",
        description="Started a chain.",
        icon="🏃‍➡️",
        rule=_chain_starter,
    ),
    AchievementDef(
        key="centurion",
        name="Centurion",
        description="Posted in a chain that reached 100 stanks.",
        icon="💯",
        rule=_centurion,
    ),
    AchievementDef(
        key="finisher",
        name="Finisher",
        description="Earned the finish bonus on a chain break.",
        icon="🏁",
        rule=_finisher,
    ),
    AchievementDef(
        key="comeback_kid",
        name="Comeback Kid",
        description="Climbed from negative net SP back to positive.",
        icon="📈",
        rule=_comeback_kid,
    ),
    AchievementDef(
        key="perfect_session",
        name="Perfect Session",
        description="Finished a session with SP earned and no breaks.",
        icon="🧼",
        rule=_perfect_session,
        session_close_only=True,
    ),
    AchievementDef(
        key="streaker",
        name="Streaker",
        description="Stanked in three consecutive sessions.",
        icon="⚡",
        rule=_streaker,
        session_close_only=True,
    ),
    AchievementDef(
        key="team_player",
        name="Team Player",
        description="Last stank of one shift, first stank of the next.",
        icon="🤝",
        rule=_team_player,
    ),
    AchievementDef(
        key="voice_stank",
        name="Vocal Stank",
        description="Submitted a stank via voice message.",
        icon="🎤",
        rule=_voice_stank,
    ),
    AchievementDef(
        key="gritty_voice",
        name="Grit Master",
        description="Delivered a gritty voice stank with bonus SP.",
        icon="🔥",
        rule=_gritty_voice,
    ),
    AchievementDef(
        key="chainbreaker",
        name="Chainbreaker",
        description="Broke a chain of 50+ stanks. Dubious honor.",
        icon="💀",
        rule=_chainbreaker_dubious,
    ),
    AchievementDef(
        key=FOURTH_PLACE_KEY,
        name="Fourth Place",
        description="Finished 4th in SP earned during a session. Repeatable.",
        icon="4️⃣",
        rule=_always_true,
        session_close_only=True,
        repeatable=True,
    ),
)


def catalog_rows() -> list[dict[str, Any]]:
    """Registry data inserted by the data-migration."""
    return [
        {
            "key": a.key,
            "name": a.name,
            "description": a.description,
            "icon": a.icon,
            "repeatable": a.repeatable,
            "rule_json": {"impl": "code", "key": a.key},
            "is_global": True,
        }
        for a in _RULES
    ]


# --- evaluator ------------------------------------------------------------


async def _already_unlocked(
    session: AsyncSession, guild_id: int, user_id: int, key: str
) -> bool:
    stmt = (
        select(PlayerBadge.id)
        .where(
            PlayerBadge.guild_id == guild_id,
            PlayerBadge.user_id == user_id,
            PlayerBadge.achievement_key == key,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def _unlock(
    session: AsyncSession,
    *,
    guild_id: int,
    user_id: int,
    achievement: AchievementDef,
    session_id: int | None,
    chain_id: int | None,
) -> bool:
    """Insert the badge + emit ``achievement_unlocked`` event. Returns
    True if newly unlocked, False if the row already existed.
    """
    badge = PlayerBadge(
        guild_id=guild_id,
        user_id=user_id,
        achievement_key=achievement.key,
        chain_id=chain_id,
        session_id=session_id,
    )
    session.add(badge)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return False
    await events_repo.append(
        session,
        guild_id=guild_id,
        type=EventType.ACHIEVEMENT_UNLOCKED,
        user_id=user_id,
        session_id=session_id,
        chain_id=chain_id,
        reason=achievement.key,
        payload={"key": achievement.key, "name": achievement.name},
    )
    return True


async def _unlock_repeatable(
    session: AsyncSession,
    *,
    guild_id: int,
    user_id: int,
    achievement: AchievementDef,
    session_id: int | None,
    chain_id: int | None,
) -> int:
    """Upsert a repeatable badge — increment ``award_count`` if the row
    already exists, insert a fresh row otherwise.  Returns the new
    ``award_count``.
    """
    stmt = (
        select(PlayerBadge)
        .where(
            PlayerBadge.guild_id == guild_id,
            PlayerBadge.user_id == user_id,
            PlayerBadge.achievement_key == achievement.key,
        )
        .limit(1)
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        new_count = (existing.award_count or 1) + 1
        await session.execute(
            update(PlayerBadge)
            .where(PlayerBadge.id == existing.id)
            .values(award_count=new_count, session_id=session_id, chain_id=chain_id)
        )
        await session.flush()
    else:
        badge = PlayerBadge(
            guild_id=guild_id,
            user_id=user_id,
            achievement_key=achievement.key,
            chain_id=chain_id,
            session_id=session_id,
            award_count=1,
        )
        session.add(badge)
        await session.flush()
        new_count = 1

    await events_repo.append(
        session,
        guild_id=guild_id,
        type=EventType.ACHIEVEMENT_UNLOCKED,
        user_id=user_id,
        session_id=session_id,
        chain_id=chain_id,
        reason=achievement.key,
        payload={"key": achievement.key, "name": achievement.name, "count": new_count},
    )
    return new_count


def _build_leaderboard(
    rows: Sequence[Any],
) -> list[tuple[int, int, int]]:
    """Assign sequential ranks to leaderboard rows.

    Input: rows of (user_id, earned_sp, punishments) ordered by net DESC.
    Output: list of (user_id, sp_earned, net_sp) preserving order.

    Ties (same net SP) share the same rank — handled by the caller.
    """
    return [(int(uid), int(sp or 0), int(sp or 0) - int(pp or 0)) for uid, sp, pp in rows]


async def _evaluate_positional(
    session: AsyncSession,
    *,
    guild_id: int,
    session_id: int,
    user_ids: list[int],
    pa: PositionalAchievement,
    leaderboard: list[tuple[int, int, int]],
) -> RankingResult | None:
    """Evaluate a single positional achievement against the leaderboard.

    Returns a ``RankingResult`` if a unique winner exists at the target
    position, or ``None`` if: disabled, too few participants, tie, or
    no one at that rank.
    """
    from stankbot.services.settings_service import SettingsService

    settings_svc = SettingsService(session)

    # Feature toggle.
    enabled = await settings_svc.get(guild_id, pa.enabled_setting, True)
    if not enabled:
        return None

    # Min participants gate.
    min_participants = await settings_svc.get(
        guild_id, pa.min_participants_setting, pa.min_participants_default
    )
    if len(user_ids) < min_participants:
        return None

    # Walk the leaderboard to find the target rank.
    rank = 0
    prev_net: int | None = None
    current_group: list[tuple[int, int, int]] = []  # (uid, sp, net)

    for uid, sp, net in leaderboard:
        if net != prev_net:
            # Flush the previous rank group before starting a new one.
            if current_group:
                rank += 1
                if rank == pa.position:
                    if len(current_group) == 1:
                        winner_uid, winner_sp, winner_net = current_group[0]
                        achievement = definition(pa.achievement_key)
                        if achievement is None:
                            log.error("positional achievement %s not found in catalog", pa.achievement_key)
                            return None
                        award_count = await _unlock_repeatable(
                            session,
                            guild_id=guild_id,
                            user_id=winner_uid,
                            achievement=achievement,
                            session_id=session_id,
                            chain_id=None,
                        )
                        return RankingResult(
                            user_id=winner_uid,
                            achievement_key=pa.achievement_key,
                            sp_earned=winner_sp,
                            net_sp=winner_net,
                            award_count=award_count,
                        )
                    return None  # tie — no award
                if rank > pa.position:
                    return None
            current_group = [(uid, sp, net)]
            prev_net = net
        else:
            current_group.append((uid, sp, net))

    # Flush the last group.
    if current_group:
        rank += 1
        if rank == pa.position and len(current_group) == 1:
            winner_uid, winner_sp, winner_net = current_group[0]
            achievement = definition(pa.achievement_key)
            if achievement is None:
                log.error("positional achievement %s not found in catalog", pa.achievement_key)
                return None
            award_count = await _unlock_repeatable(
                session,
                guild_id=guild_id,
                user_id=winner_uid,
                achievement=achievement,
                session_id=session_id,
                chain_id=None,
            )
            return RankingResult(
                user_id=winner_uid,
                achievement_key=pa.achievement_key,
                sp_earned=winner_sp,
                net_sp=winner_net,
                award_count=award_count,
            )

    return None  # not enough ranked players


async def evaluate_for_user(
    session: AsyncSession,
    *,
    guild_id: int,
    user_id: int,
    session_id: int | None = None,
    chain_id: int | None = None,
) -> list[str]:
    """Evaluate all non-session-close rules for ``user_id``. Returns the
    list of newly-unlocked achievement keys.
    """
    unlocked: list[str] = []
    for achievement in _RULES:
        if achievement.session_close_only:
            continue
        if await _already_unlocked(session, guild_id, user_id, achievement.key):
            continue
        try:
            if not await achievement.rule(session, guild_id, user_id):
                continue
        except Exception:  # noqa: BLE001
            log.exception(
                "achievement rule %s failed for guild=%d user=%d",
                achievement.key,
                guild_id,
                user_id,
            )
            continue
        if await _unlock(
            session,
            guild_id=guild_id,
            user_id=user_id,
            achievement=achievement,
            session_id=session_id,
            chain_id=chain_id,
        ):
            unlocked.append(achievement.key)
    return unlocked


async def evaluate_session_close(
    session: AsyncSession, *, guild_id: int, user_ids: list[int], session_id: int
) -> SessionCloseResult:
    """Evaluate the session-close-only rules for each participating user.

    Returns a ``SessionCloseResult`` containing per-user unlocks and any
    positional/ranking award data.

    The leaderboard is computed once and shared across all positional
    achievements.  Adding a new positional achievement requires zero
    changes here — just register it in ``_POSITIONAL_ACHIEVEMENTS``.
    """
    result = SessionCloseResult()

    # --- positional achievements (computed once, outside the per-user loop) ---
    # Build a session-scoped leaderboard from player_totals cache.
    from stankbot.db.models import PlayerTotal

    lb_stmt = (
        select(
            PlayerTotal.user_id,
            PlayerTotal.earned_sp,
            PlayerTotal.punishments,
        )
        .where(
            PlayerTotal.guild_id == guild_id,
            PlayerTotal.session_id == session_id,
            PlayerTotal.user_id.in_(user_ids),
        )
        .order_by((PlayerTotal.earned_sp - PlayerTotal.punishments).desc())
    )
    lb_rows = (await session.execute(lb_stmt)).all()
    leaderboard = _build_leaderboard(lb_rows)

    # Evaluate each registered positional achievement.
    positional_keys: set[str] = set()
    for pa in _POSITIONAL_ACHIEVEMENTS:
        try:
            ranking_result = await _evaluate_positional(
                session,
                guild_id=guild_id,
                session_id=session_id,
                user_ids=user_ids,
                pa=pa,
                leaderboard=leaderboard,
            )
            if ranking_result is not None:
                result.ranking_results.append(ranking_result)
        except Exception:  # noqa: BLE001
            log.exception("positional achievement %s failed", pa.achievement_key)
        positional_keys.add(pa.achievement_key)

    # --- per-user loop (existing session-close rules, excluding positional) ---
    for uid in user_ids:
        user_unlocks: list[str] = []
        for achievement in _RULES:
            if not achievement.session_close_only:
                continue
            # Skip positional achievements — they're handled above.
            if achievement.key in positional_keys:
                continue
            if await _already_unlocked(session, guild_id, uid, achievement.key):
                continue
            try:
                if not await achievement.rule(session, guild_id, uid):
                    continue
            except Exception:  # noqa: BLE001
                log.exception(
                    "session-close rule %s failed user=%d", achievement.key, uid
                )
                continue
            if await _unlock(
                session,
                guild_id=guild_id,
                user_id=uid,
                achievement=achievement,
                session_id=session_id,
                chain_id=None,
            ):
                user_unlocks.append(achievement.key)
        if user_unlocks:
            result.unlocks[uid] = user_unlocks

    return result


async def badges_for(
    session: AsyncSession, guild_id: int, user_id: int
) -> list[str]:
    """Return the keys of achievements this user has unlocked."""
    stmt = select(PlayerBadge.achievement_key).where(
        PlayerBadge.guild_id == guild_id,
        PlayerBadge.user_id == user_id,
    )
    return list((await session.execute(stmt)).scalars().all())


async def badges_for_with_counts(
    session: AsyncSession, guild_id: int, user_id: int
) -> dict[str, int]:
    """Return ``{achievement_key: count}`` for this user.

    Non-repeatable achievements will have count 1 if unlocked.
    Repeatable achievements will have count >= 1 (from ``award_count``).
    """
    from sqlalchemy import func as sqlfunc

    stmt = (
        select(
            PlayerBadge.achievement_key,
            sqlfunc.sum(PlayerBadge.award_count).label("cnt"),
        )
        .where(
            PlayerBadge.guild_id == guild_id,
            PlayerBadge.user_id == user_id,
        )
        .group_by(PlayerBadge.achievement_key)
    )
    rows = (await session.execute(stmt)).all()
    return {row[0]: int(row[1] or 0) for row in rows}


def definition(key: str) -> AchievementDef | None:
    for a in _RULES:
        if a.key == key:
            return a
    return None


def positional_definitions() -> tuple[PositionalAchievement, ...]:
    """Return all registered positional achievements."""
    return _POSITIONAL_ACHIEVEMENTS


def compute_fourth_place_sp(flat_sp: int, stank_count: int) -> int:
    """Compute the SP awarded for a fourth-place finish."""
    return flat_sp + stank_count
