"""Achievements — unit tests against in-memory SQLite.

Locks in behaviour for:
    * _streaker (3+ consecutive sessions with SP > 0)
    * _centurion (100+ stanks in a chain)
    * _comeback_kid (negative → positive net SP)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from stankbot.db.models import Altar, Chain, ChainMessage, EventType, Guild, PlayerTotal
from stankbot.db.repositories import events as events_repo
from stankbot.services.achievements import (
    _centurion,
    _comeback_kid,
    _streaker,
    _unlock_repeatable,
    badges_for_with_counts,
    catalog_rows,
    definition,
    evaluate_session_close,
)

# ── helpers ────────────────────────────────────────────────────────────────


def _fp(result: Any) -> list[Any]:
    """Filter ranking_results for fourth_place entries."""
    return [r for r in result.ranking_results if r.achievement_key == "fourth_place"]


async def _event(
    session: Any,
    *,
    guild_id: int = 1,
    user_id: int,
    type: EventType | str,
    delta: int = 0,
    session_id: int | None = None,
    chain_id: int | None = None,
) -> None:
    await events_repo.append(
        session,
        guild_id=guild_id,
        type=type,
        delta=delta,
        user_id=user_id,
        session_id=session_id,
        chain_id=chain_id,
    )


async def _start_session(session: Any, guild_id: int = 1) -> int:
    ev = await events_repo.append(
        session, guild_id=guild_id, type=EventType.SESSION_START
    )
    return ev.id


async def _mk_guild_altar(session: Any, guild_id: int = 1) -> None:
    session.add(Guild(id=guild_id, name="Test"))
    await session.flush()
    session.add(Altar(guild_id=guild_id, channel_id=200, sticker_name_pattern="stank"))
    await session.flush()


async def _mk_chain(
    session: Any, guild_id: int = 1, altar_id: int = 1, starter_id: int = 100,
) -> Chain:
    chain = Chain(
        guild_id=guild_id,
        altar_id=altar_id,
        starter_user_id=starter_id,
        session_id=0,
        started_at=datetime.now(tz=UTC),
    )
    session.add(chain)
    await session.flush()
    return chain


# ── _streaker ──────────────────────────────────────────────────────────────


async def test_streaker_three_consecutive_sessions(session: Any) -> None:
    sid1 = await _start_session(session)
    sid2 = await _start_session(session)
    sid3 = await _start_session(session)

    await _event(session, user_id=100, type=EventType.SP_BASE, delta=10, session_id=sid1)
    await _event(session, user_id=100, type=EventType.SP_BASE, delta=10, session_id=sid2)
    await _event(session, user_id=100, type=EventType.SP_BASE, delta=10, session_id=sid3)

    assert await _streaker(session, 1, 100) is True


async def test_streaker_not_enough_sessions(session: Any) -> None:
    sid1 = await _start_session(session)
    sid2 = await _start_session(session)

    await _event(session, user_id=100, type=EventType.SP_BASE, delta=10, session_id=sid1)
    await _event(session, user_id=100, type=EventType.SP_BASE, delta=10, session_id=sid2)

    assert await _streaker(session, 1, 100) is False


async def test_streaker_gap_breaks_run(session: Any) -> None:
    sid1 = await _start_session(session)
    await _start_session(session)  # sid2 — no stank for user 100, creates gap
    sid3 = await _start_session(session)
    sid4 = await _start_session(session)

    # User stanked in sessions 1, 3, 4 — gap at 2 breaks the run
    await _event(session, user_id=100, type=EventType.SP_BASE, delta=10, session_id=sid1)
    # sid2: no stank for user 100
    await _event(session, user_id=100, type=EventType.SP_BASE, delta=10, session_id=sid3)
    await _event(session, user_id=100, type=EventType.SP_BASE, delta=10, session_id=sid4)

    assert await _streaker(session, 1, 100) is False


async def test_streaker_four_consecutive_returns_true(session: Any) -> None:
    sid1 = await _start_session(session)
    sid2 = await _start_session(session)
    sid3 = await _start_session(session)
    sid4 = await _start_session(session)

    await _event(session, user_id=100, type=EventType.SP_BASE, delta=10, session_id=sid1)
    await _event(session, user_id=100, type=EventType.SP_BASE, delta=10, session_id=sid2)
    await _event(session, user_id=100, type=EventType.SP_BASE, delta=10, session_id=sid3)
    await _event(session, user_id=100, type=EventType.SP_BASE, delta=10, session_id=sid4)

    assert await _streaker(session, 1, 100) is True


async def test_streaker_zero_sessions_total(session: Any) -> None:
    assert await _streaker(session, 1, 100) is False


async def test_streaker_different_user_unaffected(session: Any) -> None:
    sid1 = await _start_session(session)
    sid2 = await _start_session(session)
    sid3 = await _start_session(session)

    await _event(session, user_id=200, type=EventType.SP_BASE, delta=10, session_id=sid1)
    await _event(session, user_id=200, type=EventType.SP_BASE, delta=10, session_id=sid2)
    await _event(session, user_id=200, type=EventType.SP_BASE, delta=10, session_id=sid3)

    # User 100 did nothing — should not be a streaker
    assert await _streaker(session, 1, 100) is False


# ── _centurion ──────────────────────────────────────────────────────────────


async def test_centurion_100_sp_events_in_single_chain(session: Any) -> None:
    await _mk_guild_altar(session)
    chain = await _mk_chain(session, starter_id=100)
    now = datetime.now(tz=UTC)

    for i in range(100):
        session.add(
            ChainMessage(
                chain_id=chain.id,
                message_id=i + 1,
                user_id=100,
                position=i + 1,
                created_at=now,
            )
        )
    await session.flush()

    assert await _centurion(session, 1, 100) is True


async def test_centurion_below_threshold(session: Any) -> None:
    await _mk_guild_altar(session)
    chain = await _mk_chain(session, starter_id=100)
    now = datetime.now(tz=UTC)

    for i in range(99):
        session.add(
            ChainMessage(
                chain_id=chain.id,
                message_id=i + 1,
                user_id=100,
                position=i + 1,
                created_at=now,
            )
        )
    await session.flush()

    assert await _centurion(session, 1, 100) is False


async def test_centurion_combined_across_chains_not_enough(session: Any) -> None:
    await _mk_guild_altar(session)
    now = datetime.now(tz=UTC)
    # 50 stanks in chain A + 50 in chain B ≠ 100 in one chain
    for chain_i in range(2):
        chain = await _mk_chain(session, starter_id=100)
        for i in range(50):
            session.add(
                ChainMessage(
                    chain_id=chain.id,
                    message_id=(chain_i * 1000) + i + 1,
                    user_id=100,
                    position=i + 1,
                    created_at=now,
                )
            )
    await session.flush()

    assert await _centurion(session, 1, 100) is False


async def test_centurion_user_in_100plus_chain_one_message(session: Any) -> None:
    """User contributed only 1 message but the chain itself reached 100."""
    await _mk_guild_altar(session)
    chain = await _mk_chain(session, starter_id=200)  # started by someone else
    now = datetime.now(tz=UTC)

    # User 100 has just 1 message in the chain.
    session.add(
        ChainMessage(
            chain_id=chain.id,
            message_id=1,
            user_id=100,
            position=1,
            created_at=now,
        )
    )
    # 99 more messages from other users fill out the chain to 100 total.
    for i in range(99):
        session.add(
            ChainMessage(
                chain_id=chain.id,
                message_id=i + 1000,
                user_id=300,  # different user
                position=i + 2,
                created_at=now,
            )
        )
    await session.flush()

    assert await _centurion(session, 1, 100) is True


# ── _comeback_kid ───────────────────────────────────────────────────────────


async def test_comeback_kid_was_negative_now_positive(session: Any) -> None:
    # Went -30 PP, then earned +50 SP → net = +20, and was negative at some point
    await _event(session, user_id=100, type=EventType.PP_BREAK, delta=30)
    await _event(session, user_id=100, type=EventType.SP_BASE, delta=50)

    assert await _comeback_kid(session, 1, 100) is True


async def test_comeback_kid_never_negative(session: Any) -> None:
    await _event(session, user_id=100, type=EventType.SP_BASE, delta=10)
    await _event(session, user_id=100, type=EventType.SP_BASE, delta=20)

    assert await _comeback_kid(session, 1, 100) is False


async def test_comeback_kid_still_negative(session: Any) -> None:
    await _event(session, user_id=100, type=EventType.PP_BREAK, delta=50)
    await _event(session, user_id=100, type=EventType.SP_BASE, delta=10)

    assert await _comeback_kid(session, 1, 100) is False


async def test_comeback_kid_no_events_at_all(session: Any) -> None:
    assert await _comeback_kid(session, 1, 100) is False


async def test_comeback_kid_team_player_never_negative(session: Any) -> None:
    """Team Player SP then PP, net still positive, never actually negative."""
    await _event(session, user_id=100, type=EventType.SP_TEAM_PLAYER, delta=20)
    await _event(session, user_id=100, type=EventType.PP_BREAK, delta=15)

    # Net +5, but was never negative (team_player kept them in the green).
    assert await _comeback_kid(session, 1, 100) is False


async def test_comeback_kid_team_player_genuine_comeback(session: Any) -> None:
    """Team Player SP after being negative counts as a genuine comeback."""
    await _event(session, user_id=100, type=EventType.PP_BREAK, delta=30)
    await _event(session, user_id=100, type=EventType.SP_TEAM_PLAYER, delta=20)
    await _event(session, user_id=100, type=EventType.SP_BASE, delta=15)

    # Net +5, was negative after PP, then team_player + SP base recovered.
    assert await _comeback_kid(session, 1, 100) is True


# ── evaluate_session_close (fourth place) ─────────────────────────────────


async def _seed_player_total(
    session: Any,
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


async def test_fourth_place_awards_correct_user(session: Any) -> None:
    """User with 4th-highest net SP gets the achievement."""
    session.add(Guild(id=1, name="Test"))
    await session.flush()
    sid = await _start_session(session)

    # 5 participants with descending SP
    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 40), (105, 20)]:
        await _seed_player_total(
            session, user_id=uid, session_id=sid, earned_sp=sp
        )

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104, 105], session_id=sid
    )
    assert len(_fp(result)) == 1
    assert _fp(result)[0].user_id == 104
    assert _fp(result)[0].sp_earned == 40


async def test_fourth_place_tie_at_4th_no_award(session: Any) -> None:
    """Two users tied at 4th place — no award (ambiguous)."""
    session.add(Guild(id=1, name="Test"))
    await session.flush()
    sid = await _start_session(session)

    # Exactly 4 users: 1st=100, 2nd=80, 3rd+4th tied at 60
    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 60)]:
        await _seed_player_total(
            session, user_id=uid, session_id=sid, earned_sp=sp
        )

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104], session_id=sid
    )
    assert len(_fp(result)) == 0


async def test_fourth_place_fewer_than_4_participants(session: Any) -> None:
    """Fewer than 4 participants — no 4th-place award."""
    session.add(Guild(id=1, name="Test"))
    await session.flush()
    sid = await _start_session(session)

    for uid, sp in [(101, 100), (102, 80), (103, 60)]:
        await _seed_player_total(
            session, user_id=uid, session_id=sid, earned_sp=sp
        )

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103], session_id=sid
    )
    assert len(_fp(result)) == 0


async def test_fourth_place_repeatable_award_count_increments(session: Any) -> None:
    """Repeatable badge increments award_count on each unlock."""
    session.add(Guild(id=1, name="Test"))
    await session.flush()
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


async def test_fourth_place_net_sp_used_for_ranking(session: Any) -> None:
    """Ranking uses net SP (earned - punishments), not raw earned SP."""
    session.add(Guild(id=1, name="Test"))
    await session.flush()
    sid = await _start_session(session)

    # User 104: 60 earned, 30 PP = net 30
    # User 105: 35 earned, 0 PP = net 35 (beats 104 on net)
    # Ranking: 101(100) > 102(80) > 103(60) > 105(35) > 104(30)
    # So 105 is 4th, 104 is 5th
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


# ── toggle disabled ────────────────────────────────────────────────────────


async def test_fourth_place_toggle_disabled_no_award(session: Any) -> None:
    """When fourth_place_enabled is False via settings, no award is given."""
    from stankbot.db.models import Achievement
    from stankbot.services.settings_service import SettingsService

    session.add(Guild(id=1, name="Test"))
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

    svc = SettingsService(session)
    await svc.set(1, "fourth_place_enabled", False)

    sid = await _start_session(session)
    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 40), (105, 20)]:
        await _seed_player_total(
            session, user_id=uid, session_id=sid, earned_sp=sp
        )

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104, 105], session_id=sid
    )
    assert len(_fp(result)) == 0


# ── min_participants gate ──────────────────────────────────────────────────


async def test_fourth_place_min_participants_gate_blocks(session: Any) -> None:
    """Custom min_participants=6 blocks a 5-participant session."""
    from stankbot.db.models import Achievement
    from stankbot.services.settings_service import SettingsService

    session.add(Guild(id=1, name="Test"))
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

    svc = SettingsService(session)
    await svc.set(1, "fourth_place_min_participants", 6)

    sid = await _start_session(session)
    for uid, sp in [(101, 100), (102, 80), (103, 60), (104, 40), (105, 20)]:
        await _seed_player_total(
            session, user_id=uid, session_id=sid, earned_sp=sp
        )

    result = await evaluate_session_close(
        session, guild_id=1, user_ids=[101, 102, 103, 104, 105], session_id=sid
    )
    assert len(_fp(result)) == 0


# ── badges_for_with_counts ─────────────────────────────────────────────────


async def test_badges_for_with_counts_returns_correct_dict(session: Any) -> None:
    """badges_for_with_counts returns {key: sum(award_count)} for a user."""
    from stankbot.db.models import Achievement

    # Seed the fourth_place achievement so FK passes
    session.add(Guild(id=1, name="Test"))
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

    achievement = definition("fourth_place")
    assert achievement is not None
    assert achievement.repeatable is True

    # Award 3 times
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
    assert "fourth_place" in counts
    assert counts["fourth_place"] == 3

    # A user with no badges returns empty dict
    counts_empty = await badges_for_with_counts(session, 1, 999)
    assert counts_empty == {}


# ── catalog_rows includes repeatable field ─────────────────────────────────


async def test_catalog_rows_includes_repeatable_field() -> None:
    """catalog_rows() returns a list of dicts that each include 'repeatable'."""
    rows = catalog_rows()
    assert isinstance(rows, list)
    assert len(rows) > 0

    # Every row must have the repeatable key
    for row in rows:
        assert "repeatable" in row, f"Missing 'repeatable' in {row.get('key')}"
        assert isinstance(row["repeatable"], bool)

    # The fourth_place entry specifically is repeatable
    fp_row = next(r for r in rows if r["key"] == "fourth_place")
    assert fp_row["repeatable"] is True
    assert fp_row["name"] == "Fourth Place"

    # A non-repeatable entry (e.g. first_stank) should be False
    fs_row = next(r for r in rows if r["key"] == "first_stank")
    assert fs_row["repeatable"] is False


# ── definition() ───────────────────────────────────────────────────────────


async def test_definition_fourth_place_is_repeatable() -> None:
    """definition('fourth_place') returns an AchievementDef with repeatable=True."""
    ach = definition("fourth_place")
    assert ach is not None
    assert ach.key == "fourth_place"
    assert ach.repeatable is True
    assert ach.session_close_only is True
