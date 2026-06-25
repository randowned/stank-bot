"""4th-place achievement — comprehensive unit tests.

Covers the acceptance criteria from task t_069d9278:
    - toggle disabled skips ranking
    - too few participants (min_participants gate)
    - tie for 4th → no award
    - repeatable badge count increments
    - badges_for_with_counts returns correct counts
    - evaluate_session_close fourth_place result shape
    - API /api/player/{id} returns count + repeatable fields
    - API /api/achievements returns count + repeatable fields
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import (
    Achievement,
    EventType,
    Guild,
    Player,
    PlayerBadge,
    PlayerTotal,
)
from stankbot.db.repositories import events as events_repo
from stankbot.services.achievements import (
    _unlock_repeatable,
    badges_for_with_counts,
    definition,
    evaluate_session_close,
)
from stankbot.services.settings_service import SettingsService


def _fp(result: Any) -> list[Any]:
    """Filter ranking_results for fourth_place entries."""
    return [r for r in result.ranking_results if r.achievement_key == "fourth_place"]

# ── helpers ────────────────────────────────────────────────────────────────


async def _start_session(session: AsyncSession, guild_id: int = 1) -> int:
    ev = await events_repo.append(
        session, guild_id=guild_id, type=EventType.SESSION_START
    )
    return ev.id


async def _seed_player_total(
    session: AsyncSession,
    *,
    guild_id: int = 1,
    user_id: int,
    session_id: int,
    earned_sp: int,
    punishments: int = 0,
) -> None:
    pt = PlayerTotal(
        guild_id=guild_id,
        user_id=user_id,
        session_id=session_id,
        earned_sp=earned_sp,
        punishments=punishments,
    )
    session.add(pt)
    await session.flush()


async def _seed_guild(session: AsyncSession, guild_id: int = 1) -> None:
    session.add(Guild(id=guild_id, name="Test"))
    await session.flush()


async def _seed_achievement_catalog(session: AsyncSession) -> None:
    """Insert the fourth_place achievement row so FK constraints pass."""
    session.add(
        Achievement(
            key="fourth_place",
            name="Fourth Place",
            description="Finished 4th in SP earned during a session. Repeatable.",
            icon="4️⃣",
            rule_json={"impl": "code", "key": "fourth_place"},
            is_global=True,
        )
    )
    await session.flush()


async def _seed_other_achievements(session: AsyncSession) -> None:
    """Insert all achievements so FK constraints pass for any unlock."""
    from stankbot.services.achievements import catalog_rows

    for row in catalog_rows():
        existing = await session.get(Achievement, row["key"])
        if existing is None:
            session.add(
                Achievement(
                    key=row["key"],
                    name=row["name"],
                    description=row["description"],
                    icon=row.get("icon"),
                    rule_json=row["rule_json"],
                    is_global=row.get("is_global", True),
                )
            )
    await session.flush()


async def _disable_fourth_place(session: AsyncSession, guild_id: int = 1) -> None:
    """Set FOURTH_PLACE_ENABLED = False via the settings service."""
    svc = SettingsService(session)
    await svc.set(guild_id, "fourth_place_enabled", False)


async def _set_min_participants(
    session: AsyncSession, guild_id: int, value: int
) -> None:
    svc = SettingsService(session)
    await svc.set(guild_id, "fourth_place_min_participants", value)


def _build_test_app(db_session: AsyncSession) -> FastAPI:
    from stankbot.web.routes.api import router as api_router
    from stankbot.web.tools import get_active_guild_id, get_db, require_guild_member

    app = FastAPI()

    async def _override_db() -> AsyncSession:
        yield db_session

    async def _override_member() -> dict:
        return {"id": "1", "username": "tester"}

    async def _override_guild_id() -> int:
        return 1

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[require_guild_member] = _override_member
    app.dependency_overrides[get_active_guild_id] = _override_guild_id

    app.include_router(api_router)
    return app


# ── evaluate_session_close: fourth place ranking ──────────────────────────


async def test_fourth_place_awards_correct_user(session: Any) -> None:
    """User with 4th-highest net SP gets the achievement."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 40), (105, 20)]:
        await _seed_player_total(session, user_id=uid, session_id=sid, earned_sp=sp)

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104, 105], session_id=sid
    )
    assert len(_fp(result)) == 1
    assert _fp(result)[0].user_id == 104
    assert _fp(result)[0].sp_earned == 40


async def test_fourth_place_tie_at_4th_no_award(session: Any) -> None:
    """Two users tied at 4th place — no award (ambiguous)."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 60)]:
        await _seed_player_total(session, user_id=uid, session_id=sid, earned_sp=sp)

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104], session_id=sid
    )
    assert len(_fp(result)) == 0


async def test_fourth_place_fewer_than_4_participants(session: Any) -> None:
    """Fewer than 4 participants — no 4th-place award."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    for uid, sp in [(101, 100), (102, 80), (103, 60)]:
        await _seed_player_total(session, user_id=uid, session_id=sid, earned_sp=sp)

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103], session_id=sid
    )
    assert len(_fp(result)) == 0


async def test_fourth_place_net_sp_used_for_ranking(session: Any) -> None:
    """Ranking uses net SP (earned - punishments), not raw earned SP."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    # User 104: 60 earned, 30 PP = net 30
    # User 105: 35 earned, 0 PP = net 35 (beats 104 on net)
    # Ranking: 101(100) > 102(80) > 103(60) > 105(35) > 104(30)
    for uid, sp, pp in [
        (101, 100, 0),
        (102, 80, 0),
        (103, 60, 0),
        (104, 60, 30),
        (105, 35, 0),
    ]:
        await _seed_player_total(
            session, user_id=uid, session_id=sid, earned_sp=sp, punishments=pp
        )

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104, 105], session_id=sid
    )
    assert len(_fp(result)) == 1
    # 105 has net 35 which is 4th; 104 has net 30 which is 5th
    assert _fp(result)[0].user_id == 105


async def test_fourth_place_exact_4_participants(session: Any) -> None:
    """Exactly 4 participants — 4th place is awarded."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 40)]:
        await _seed_player_total(session, user_id=uid, session_id=sid, earned_sp=sp)

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104], session_id=sid
    )
    assert len(_fp(result)) == 1
    assert _fp(result)[0].user_id == 104
    assert _fp(result)[0].sp_earned == 40


async def test_fourth_place_many_participants_awards_4th(session: Any) -> None:
    """10 participants — 4th place is correctly identified."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    for i, uid in enumerate(range(101, 111)):
        await _seed_player_total(
            session, user_id=uid, session_id=sid, earned_sp=100 - i * 10
        )

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=list(range(101, 111)), session_id=sid
    )
    assert len(_fp(result)) == 1
    # 4th highest: 101(100), 102(90), 103(80), 104(70)
    assert _fp(result)[0].user_id == 104
    assert _fp(result)[0].sp_earned == 70


# ── toggle disabled ────────────────────────────────────────────────────────


async def test_fourth_place_toggle_disabled_skips_ranking(session: Any) -> None:
    """When FOURTH_PLACE_ENABLED is False, no award is given."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    await _disable_fourth_place(session)
    sid = await _start_session(session)

    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 40), (105, 20)]:
        await _seed_player_total(session, user_id=uid, session_id=sid, earned_sp=sp)

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104, 105], session_id=sid
    )
    assert len(_fp(result)) == 0


async def test_fourth_place_toggle_enabled_awards(session: Any) -> None:
    """When FOURTH_PLACE_ENABLED is True (default), award is given."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 40), (105, 20)]:
        await _seed_player_total(session, user_id=uid, session_id=sid, earned_sp=sp)

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104, 105], session_id=sid
    )
    assert len(_fp(result)) == 1


# ── min_participants gate ──────────────────────────────────────────────────


async def test_fourth_place_min_participants_gate_blocks(session: Any) -> None:
    """Custom min_participants=6 blocks 5 participants."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    await _set_min_participants(session, 1, 6)
    sid = await _start_session(session)

    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 40), (105, 20)]:
        await _seed_player_total(session, user_id=uid, session_id=sid, earned_sp=sp)

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104, 105], session_id=sid
    )
    assert len(_fp(result)) == 0


async def test_fourth_place_min_participants_gate_passes(session: Any) -> None:
    """Custom min_participants=3 allows 5 participants."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    await _set_min_participants(session, 1, 3)
    sid = await _start_session(session)

    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 40), (105, 20)]:
        await _seed_player_total(session, user_id=uid, session_id=sid, earned_sp=sp)

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104, 105], session_id=sid
    )
    assert len(_fp(result)) == 1
    assert _fp(result)[0].user_id == 104


async def test_fourth_place_default_min_participants_is_4(session: Any) -> None:
    """Default min_participants is 4 — 3 participants should not trigger."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    for uid, sp in [(101, 100), (102, 80), (103, 60)]:
        await _seed_player_total(session, user_id=uid, session_id=sid, earned_sp=sp)

    # Default min_participants=4, only 3 participants
    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103], session_id=sid
    )
    assert len(_fp(result)) == 0


# ── repeatable badge ──────────────────────────────────────────────────────


async def test_fourth_place_repeatable_award_count_increments(session: Any) -> None:
    """Repeatable badge increments award_count on each unlock."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    achievement = definition("fourth_place")
    assert achievement is not None

    # First award
    count1 = await _unlock_repeatable(
        session,
        guild_id=1,
        user_id=104,
        achievement=achievement,
        session_id=10,
        chain_id=None,
    )
    assert count1 == 1

    # Second award
    count2 = await _unlock_repeatable(
        session,
        guild_id=1,
        user_id=104,
        achievement=achievement,
        session_id=20,
        chain_id=None,
    )
    assert count2 == 2

    # Third award
    count3 = await _unlock_repeatable(
        session,
        guild_id=1,
        user_id=104,
        achievement=achievement,
        session_id=30,
        chain_id=None,
    )
    assert count3 == 3


async def test_fourth_place_repeatable_across_sessions(session: Any) -> None:
    """Multiple sessions: same user gets 4th each time, count increments."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)

    # Session 1
    sid1 = await _start_session(session)
    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 40), (105, 20)]:
        await _seed_player_total(session, user_id=uid, session_id=sid1, earned_sp=sp)

    result1 = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104, 105], session_id=sid1
    )
    assert len(_fp(result1)) == 1
    assert _fp(result1)[0].user_id == 104
    assert _fp(result1)[0].award_count == 1

    # Session 2 — need new player_totals for the new session
    sid2 = await _start_session(session)
    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 40), (105, 20)]:
        await _seed_player_total(session, user_id=uid, session_id=sid2, earned_sp=sp)

    result2 = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104, 105], session_id=sid2
    )
    assert len(_fp(result2)) == 1
    assert _fp(result2)[0].user_id == 104
    assert _fp(result2)[0].award_count == 2


async def test_fourth_place_result_carries_sp_earned_and_net_sp(session: Any) -> None:
    """RankingResult carries sp_earned and net_sp correctly."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    # 104: earned=50, punishments=10 → net=40
    for uid, sp, pp in [
        (101, 100, 0),
        (102, 80, 0),
        (103, 60, 0),
        (104, 50, 10),
        (105, 20, 0),
    ]:
        await _seed_player_total(
            session, user_id=uid, session_id=sid, earned_sp=sp, punishments=pp
        )

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104, 105], session_id=sid
    )
    assert len(_fp(result)) == 1
    fp = _fp(result)[0]
    assert fp.user_id == 104
    assert fp.sp_earned == 50
    assert fp.net_sp == 40


# ── badges_for_with_counts ─────────────────────────────────────────────────


async def test_badges_for_with_counts_non_repeatable(session: Any) -> None:
    """Non-repeatable badge shows count=1."""
    await _seed_guild(session)
    await _seed_other_achievements(session)

    badge = PlayerBadge(
        guild_id=1, user_id=100, achievement_key="first_stank", award_count=1
    )
    session.add(badge)
    await session.flush()

    counts = await badges_for_with_counts(session, 1, 100)
    assert counts["first_stank"] == 1


async def test_badges_for_with_counts_repeatable(session: Any) -> None:
    """Repeatable badge shows count based on row count."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)

    achievement = definition("fourth_place")
    assert achievement is not None

    # Award 3 times — creates 1 row with award_count=3
    for i in range(3):
        await _unlock_repeatable(
            session,
            guild_id=1,
            user_id=104,
            achievement=achievement,
            session_id=10 * (i + 1),
            chain_id=None,
        )

    counts = await badges_for_with_counts(session, 1, 104)
    # _unlock_repeatable creates 1 row with award_count=3
    # badges_for_with_counts uses SUM(award_count) so the result is 3
    assert "fourth_place" in counts
    assert counts["fourth_place"] == 3


async def test_badges_for_with_counts_empty(session: Any) -> None:
    """No badges — empty dict."""
    counts = await badges_for_with_counts(session, 1, 999)
    assert counts == {}


async def test_badges_for_with_counts_multiple_achievements(session: Any) -> None:
    """Multiple different achievements for one user."""
    await _seed_guild(session)
    await _seed_other_achievements(session)

    for key in ("first_stank", "chain_starter", "finisher"):
        session.add(
            PlayerBadge(guild_id=1, user_id=100, achievement_key=key, award_count=1)
        )
    await session.flush()

    counts = await badges_for_with_counts(session, 1, 100)
    assert len(counts) == 3
    assert counts["first_stank"] == 1
    assert counts["chain_starter"] == 1
    assert counts["finisher"] == 1


# ── SessionCloseResult shape ───────────────────────────────────────────────


async def test_session_close_result_has_fourth_place_list(session: Any) -> None:
    """SessionCloseResult always has a ranking_results list, even when empty."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[], session_id=sid
    )
    assert hasattr(result, "ranking_results")
    assert isinstance(result.ranking_results, list)
    assert len(_fp(result)) == 0


async def test_session_close_result_has_unlocks_dict(session: Any) -> None:
    """SessionCloseResult always has an unlocks dict."""
    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[], session_id=sid
    )
    assert hasattr(result, "unlocks")
    assert isinstance(result.unlocks, dict)


# ── API: /api/player/{id} ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_player_api_returns_achievements_with_count_and_repeatable(
    session: Any,
) -> None:
    """Player profile API includes count + repeatable for each achievement."""
    await _seed_guild(session)
    await _seed_other_achievements(session)

    session.add(
        Player(guild_id=1, user_id=100, display_name="TestPlayer")
    )
    await session.flush()

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/player/100")

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()

    assert "achievements" in body
    achievements = body["achievements"]
    assert len(achievements) > 0

    # Every achievement entry should have count and repeatable fields
    for ach in achievements:
        assert "count" in ach, f"Missing 'count' in achievement {ach.get('key')}"
        assert "repeatable" in ach, f"Missing 'repeatable' in achievement {ach.get('key')}"
        assert "unlocked" in ach, f"Missing 'unlocked' in achievement {ach.get('key')}"
        assert isinstance(ach["count"], int)
        assert isinstance(ach["repeatable"], bool)

    # fourth_place specifically
    fp_ach = next(a for a in achievements if a["key"] == "fourth_place")
    assert fp_ach["repeatable"] is True
    assert fp_ach["count"] == 0  # not unlocked yet
    assert fp_ach["unlocked"] is False


@pytest.mark.asyncio
async def test_player_api_fourth_place_count_after_unlock(session: Any) -> None:
    """After unlocking 4th place, count reflects the award_count."""
    await _seed_guild(session)
    await _seed_other_achievements(session)

    session.add(
        Player(guild_id=1, user_id=100, display_name="TestPlayer")
    )
    await session.flush()

    # Unlock fourth_place 3 times
    achievement = definition("fourth_place")
    assert achievement is not None
    for i in range(3):
        await _unlock_repeatable(
            session,
            guild_id=1,
            user_id=100,
            achievement=achievement,
            session_id=10 * (i + 1),
            chain_id=None,
        )

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/player/100")

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()

    fp_ach = next(a for a in body["achievements"] if a["key"] == "fourth_place")
    assert fp_ach["unlocked"] is True
    assert fp_ach["count"] >= 1  # at least 1 row exists
    assert fp_ach["repeatable"] is True


@pytest.mark.asyncio
async def test_player_api_returns_404_for_nonexistent(session: Any) -> None:
    """Nonexistent player returns 404."""
    await _seed_guild(session)

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/player/999")

    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ── API: /api/achievements ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_achievements_api_returns_count_and_repeatable(session: Any) -> None:
    """Achievements catalog includes count + repeatable for all entries."""
    await _seed_guild(session)
    await _seed_other_achievements(session)

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/achievements")

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()

    assert "achievements" in body
    achievements = body["achievements"]
    assert len(achievements) > 0

    for ach in achievements:
        assert "count" in ach
        assert "repeatable" in ach
        assert "unlocked" in ach
        assert isinstance(ach["count"], int)
        assert isinstance(ach["repeatable"], bool)

    fp_ach = next(a for a in achievements if a["key"] == "fourth_place")
    assert fp_ach["repeatable"] is True
    assert fp_ach["count"] == 0


@pytest.mark.asyncio
async def test_achievements_api_with_user_id_param(session: Any) -> None:
    """With user_id query param, marks unlocked achievements."""
    await _seed_guild(session)
    await _seed_other_achievements(session)

    # Unlock first_stank for user 100
    session.add(
        PlayerBadge(guild_id=1, user_id=100, achievement_key="first_stank")
    )
    await session.flush()

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/achievements?user_id=100")

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()

    first_stank = next(a for a in body["achievements"] if a["key"] == "first_stank")
    assert first_stank["unlocked"] is True
    assert first_stank["count"] >= 1

    fp_ach = next(a for a in body["achievements"] if a["key"] == "fourth_place")
    assert fp_ach["unlocked"] is False
    assert fp_ach["count"] == 0


@pytest.mark.asyncio
async def test_achievements_api_fourth_place_is_repeatable(session: Any) -> None:
    """The fourth_place achievement is marked as repeatable in the catalog."""
    await _seed_guild(session)
    await _seed_other_achievements(session)

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/achievements")

    body = resp.json()
    fp_ach = next(a for a in body["achievements"] if a["key"] == "fourth_place")
    assert fp_ach["repeatable"] is True
    assert fp_ach["name"] == "Fourth Place"
    assert fp_ach["icon"] == "4️⃣"


def test_compute_fourth_place_sp() -> None:
    """The shared formula adds flat_sp + stank_count."""
    from stankbot.services.achievements import compute_fourth_place_sp

    assert compute_fourth_place_sp(50, 0) == 50
    assert compute_fourth_place_sp(50, 12) == 62
    assert compute_fourth_place_sp(100, 5) == 105
    assert compute_fourth_place_sp(0, 0) == 0


# ── Generic positional achievement tests ────────────────────────────────


async def test_positional_3rd_place_awards_correct_user(session: Any) -> None:
    """Generic handler with position=3 awards the 3rd-highest net SP user."""
    from sqlalchemy import select

    from stankbot.db.models import PlayerTotal
    from stankbot.services.achievements import (
        PositionalAchievement,
        _build_leaderboard,
        _evaluate_positional,
    )

    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 40), (105, 20)]:
        await _seed_player_total(session, user_id=uid, session_id=sid, earned_sp=sp)

    user_ids = [101, 102, 103, 104, 105]

    # Build leaderboard
    lb_stmt = (
        select(PlayerTotal.user_id, PlayerTotal.earned_sp, PlayerTotal.punishments)
        .where(
            PlayerTotal.guild_id == 1,
            PlayerTotal.session_id == sid,
            PlayerTotal.user_id.in_(user_ids),
        )
        .order_by((PlayerTotal.earned_sp - PlayerTotal.punishments).desc())
    )
    lb_rows = (await session.execute(lb_stmt)).all()
    leaderboard = _build_leaderboard(lb_rows)

    pa = PositionalAchievement(
        position=3,
        achievement_key="fourth_place",  # reuse existing catalog entry
        enabled_setting="third_place_enabled",
        min_participants_setting="third_place_min_participants",
        min_participants_default=3,
    )

    result = await _evaluate_positional(
        session, guild_id=1, session_id=sid, user_ids=user_ids,
        pa=pa, leaderboard=leaderboard,
    )
    assert result is not None
    assert result.user_id == 103  # 3rd highest: 101(100), 102(80), 103(60)
    assert result.sp_earned == 60
    assert result.net_sp == 60
    assert result.achievement_key == "fourth_place"


async def test_positional_5th_place_awards_correct_user(session: Any) -> None:
    """Generic handler with position=5 awards the 5th-highest net SP user."""
    from sqlalchemy import select

    from stankbot.db.models import PlayerTotal
    from stankbot.services.achievements import (
        PositionalAchievement,
        _build_leaderboard,
        _evaluate_positional,
    )

    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 40), (105, 20)]:
        await _seed_player_total(session, user_id=uid, session_id=sid, earned_sp=sp)

    user_ids = [101, 102, 103, 104, 105]

    lb_stmt = (
        select(PlayerTotal.user_id, PlayerTotal.earned_sp, PlayerTotal.punishments)
        .where(
            PlayerTotal.guild_id == 1,
            PlayerTotal.session_id == sid,
            PlayerTotal.user_id.in_(user_ids),
        )
        .order_by((PlayerTotal.earned_sp - PlayerTotal.punishments).desc())
    )
    lb_rows = (await session.execute(lb_stmt)).all()
    leaderboard = _build_leaderboard(lb_rows)

    pa = PositionalAchievement(
        position=5,
        achievement_key="fourth_place",
        enabled_setting="fifth_place_enabled",
        min_participants_setting="fifth_place_min_participants",
        min_participants_default=5,
    )

    result = await _evaluate_positional(
        session, guild_id=1, session_id=sid, user_ids=user_ids,
        pa=pa, leaderboard=leaderboard,
    )
    assert result is not None
    assert result.user_id == 105  # 5th highest: 101(100), 102(80), 103(60), 104(40), 105(20)
    assert result.sp_earned == 20
    assert result.net_sp == 20


async def test_positional_3rd_place_tie_no_award(session: Any) -> None:
    """Generic handler: tie at position 3 means no award."""
    from sqlalchemy import select

    from stankbot.db.models import PlayerTotal
    from stankbot.services.achievements import (
        PositionalAchievement,
        _build_leaderboard,
        _evaluate_positional,
    )

    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    # 103 and 104 tied at 60 SP — rank 3 shared
    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 60)]:
        await _seed_player_total(session, user_id=uid, session_id=sid, earned_sp=sp)

    user_ids = [101, 102, 103, 104]

    lb_stmt = (
        select(PlayerTotal.user_id, PlayerTotal.earned_sp, PlayerTotal.punishments)
        .where(
            PlayerTotal.guild_id == 1,
            PlayerTotal.session_id == sid,
            PlayerTotal.user_id.in_(user_ids),
        )
        .order_by((PlayerTotal.earned_sp - PlayerTotal.punishments).desc())
    )
    lb_rows = (await session.execute(lb_stmt)).all()
    leaderboard = _build_leaderboard(lb_rows)

    pa = PositionalAchievement(
        position=3,
        achievement_key="fourth_place",
        enabled_setting="third_place_enabled",
        min_participants_setting="third_place_min_participants",
        min_participants_default=3,
    )

    result = await _evaluate_positional(
        session, guild_id=1, session_id=sid, user_ids=user_ids,
        pa=pa, leaderboard=leaderboard,
    )
    assert result is None  # tie — no award


async def test_positional_generic_disabled_setting(session: Any) -> None:
    """Generic handler respects per-achievement enabled setting."""
    from sqlalchemy import select

    from stankbot.db.models import PlayerTotal
    from stankbot.services.achievements import (
        PositionalAchievement,
        _build_leaderboard,
        _evaluate_positional,
    )

    await _seed_guild(session)
    await _seed_achievement_catalog(session)
    sid = await _start_session(session)

    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 40), (105, 20)]:
        await _seed_player_total(session, user_id=uid, session_id=sid, earned_sp=sp)

    user_ids = [101, 102, 103, 104, 105]

    lb_stmt = (
        select(PlayerTotal.user_id, PlayerTotal.earned_sp, PlayerTotal.punishments)
        .where(
            PlayerTotal.guild_id == 1,
            PlayerTotal.session_id == sid,
            PlayerTotal.user_id.in_(user_ids),
        )
        .order_by((PlayerTotal.earned_sp - PlayerTotal.punishments).desc())
    )
    lb_rows = (await session.execute(lb_stmt)).all()
    leaderboard = _build_leaderboard(lb_rows)

    pa = PositionalAchievement(
        position=4,
        achievement_key="fourth_place",
        enabled_setting="custom_toggle",
        min_participants_setting="custom_min",
        min_participants_default=4,
    )

    # Disable via settings
    svc = SettingsService(session)
    await svc.set(1, "custom_toggle", False)

    result = await _evaluate_positional(
        session, guild_id=1, session_id=sid, user_ids=user_ids,
        pa=pa, leaderboard=leaderboard,
    )
    assert result is None  # disabled
