"""ChainService — end-to-end against in-memory SQLite.

Exercises the invariants from the plan's verification checklist:
    * starter SP = SP_FLAT + SP_STARTER_BONUS
    * cooldown rejects a re-stank within the window
    * finish-bonus skips the chainbreaker
    * break penalty = base + length * per-stank
    * reaction anti-cheat: remove + re-add cannot re-award
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from stankbot.db.models import Altar, Guild
from stankbot.db.repositories import events as events_repo
from stankbot.services.chain_service import (
    ChainOutcome,
    ChainService,
    StankInput,
)
from stankbot.services.scoring_service import ScoringConfig
from stankbot.services.session_service import SessionService


@pytest.fixture
async def setup(session):  # type: ignore[no-untyped-def]
    guild = Guild(id=100, name="Test")
    session.add(guild)
    await session.flush()
    altar = Altar(
        guild_id=100,
        channel_id=200,
        sticker_id=300,
        display_name="primary",
    )
    session.add(altar)
    await session.flush()
    sess_svc = SessionService(session=session)
    await sess_svc.ensure_started(100)
    chain_svc = ChainService(session=session, session_id_provider=sess_svc)
    return session, guild, altar, chain_svc


@pytest.fixture
def cfg() -> ScoringConfig:
    return ScoringConfig()


async def test_first_stank_awards_base_plus_starter_bonus(setup, cfg) -> None:  # type: ignore[no-untyped-def]
    session, guild, altar, chain_svc = setup
    now = datetime(2026, 4, 19, 12, 0, tzinfo=UTC)
    result = await chain_svc.process(
        StankInput(
            guild_id=guild.id,
            altar=altar,
            message_id=1001,
            author_id=500,
            author_display_name="alice",
            is_stank=True,
            created_at=now,
        ),
        cfg,
    )
    assert result.outcome == ChainOutcome.VALID_STANK
    assert result.sp_awarded == cfg.sp_flat + cfg.sp_starter_bonus  # 10 + 15
    assert result.chain_length == 1


async def test_second_stank_gets_position_bonus(setup, cfg) -> None:  # type: ignore[no-untyped-def]
    session, guild, altar, chain_svc = setup
    now = datetime(2026, 4, 19, 12, 0, tzinfo=UTC)
    await chain_svc.process(
        StankInput(
            guild_id=guild.id, altar=altar, message_id=1,
            author_id=500, author_display_name="alice", is_stank=True, created_at=now,
        ),
        cfg,
    )
    r2 = await chain_svc.process(
        StankInput(
            guild_id=guild.id, altar=altar, message_id=2,
            author_id=600, author_display_name="bob", is_stank=True,
            created_at=now + timedelta(minutes=1),
        ),
        cfg,
    )
    # Position 2: base (10) + 1 * position_bonus (1) = 11
    assert r2.sp_awarded == cfg.sp_flat + cfg.sp_position_bonus
    assert r2.chain_length == 2


async def test_cooldown_rejects_fast_restank_same_user(setup, cfg) -> None:  # type: ignore[no-untyped-def]
    session, guild, altar, chain_svc = setup
    t0 = datetime(2026, 4, 19, 12, 0, tzinfo=UTC)
    await chain_svc.process(
        StankInput(
            guild_id=guild.id, altar=altar, message_id=1,
            author_id=500, author_display_name="alice", is_stank=True, created_at=t0,
        ),
        cfg,
    )
    r2 = await chain_svc.process(
        StankInput(
            guild_id=guild.id, altar=altar, message_id=2,
            author_id=500, author_display_name="alice", is_stank=True,
            created_at=t0 + timedelta(minutes=5),
        ),
        cfg,
    )
    assert r2.outcome == ChainOutcome.COOLDOWN
    assert r2.cooldown_seconds_remaining > 0


async def test_chain_break_punishes_breaker_and_awards_finish_to_prior(
    setup, cfg
) -> None:  # type: ignore[no-untyped-def]
    session, guild, altar, chain_svc = setup
    t = datetime(2026, 4, 19, 12, 0, tzinfo=UTC)
    # Build a chain: alice, bob, carol
    for i, uid in enumerate([500, 600, 700]):
        await chain_svc.process(
            StankInput(
                guild_id=guild.id, altar=altar, message_id=100 + i,
                author_id=uid, author_display_name=f"u{uid}",
                is_stank=True, created_at=t + timedelta(minutes=i),
            ),
            cfg,
        )
    # carol (700) also breaks — finish bonus should go to bob (600), not carol.
    r = await chain_svc.process(
        StankInput(
            guild_id=guild.id, altar=altar, message_id=999,
            author_id=700, author_display_name="carol",
            is_stank=False, created_at=t + timedelta(minutes=5),
        ),
        cfg,
    )
    assert r.outcome == ChainOutcome.CHAIN_BREAK
    assert r.broken_length == 3
    assert r.finish_bonus_user_id == 600
    assert r.pp_awarded == cfg.pp_break_base + 3 * cfg.pp_break_per_stank
    assert r.sp_awarded == cfg.sp_finish_bonus


async def test_reaction_anti_cheat_blocks_readd(setup, cfg) -> None:  # type: ignore[no-untyped-def]
    session, guild, altar, chain_svc = setup
    t = datetime(2026, 4, 19, 12, 0, tzinfo=UTC)
    # Land at least one stank so there's a chain to react to.
    await chain_svc.process(
        StankInput(
            guild_id=guild.id, altar=altar, message_id=1,
            author_id=500, author_display_name="alice", is_stank=True, created_at=t,
        ),
        cfg,
    )
    first = await chain_svc.award_reaction_bonus(
        guild_id=guild.id, altar=altar,
        message_id=1, user_id=999, sticker_id=altar.sticker_id,
        config=cfg, created_at=t,
    )
    second = await chain_svc.award_reaction_bonus(
        guild_id=guild.id, altar=altar,
        message_id=1, user_id=999, sticker_id=altar.sticker_id,
        config=cfg, created_at=t + timedelta(seconds=10),
    )
    assert first == cfg.sp_reaction
    assert second == 0  # remove + re-add cannot double-dip


async def test_event_log_captures_every_score_delta(setup, cfg) -> None:  # type: ignore[no-untyped-def]
    session, guild, altar, chain_svc = setup
    t = datetime(2026, 4, 19, 12, 0, tzinfo=UTC)
    await chain_svc.process(
        StankInput(
            guild_id=guild.id, altar=altar, message_id=1,
            author_id=500, author_display_name="alice", is_stank=True, created_at=t,
        ),
        cfg,
    )
    sp, pp = await events_repo.sp_pp_totals(session, guild.id, 500)
    # starter: SP_FLAT + SP_STARTER_BONUS = 25
    assert sp == 25
    assert pp == 0
