"""Verify _broadcast_fourth_place tags SP_FOURTH_PLACE with the ended session.

Regression test for the bug where the event was tagged with the *new*
session's id (via ``svc.current()``) instead of the ended session's id.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import Altar, Event, EventType, Guild
from stankbot.db.repositories import events as events_repo
from stankbot.scheduling.session_scheduler import _broadcast_fourth_place
from stankbot.services.achievements import RankingResult

# ── helpers ─────────────────────────────────────────────────────────────


async def _seed_guild(session: AsyncSession, guild_id: int = 1) -> None:
    session.add(Guild(id=guild_id, name="Test Guild"))
    await session.flush()


async def _seed_altar(session: AsyncSession, guild_id: int = 1) -> None:
    session.add(
        Altar(
            guild_id=guild_id,
            channel_id=999,
        )
    )
    await session.flush()


async def _start_session(session: AsyncSession, guild_id: int = 1) -> int:
    ev = await events_repo.append(
        session, guild_id=guild_id, type=EventType.SESSION_START
    )
    return ev.id


# ── test ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sp_fourth_place_tags_ended_session(session: AsyncSession) -> None:
    """SP_FOURTH_PLACE event must use ended_id, not the current session."""
    guild_id = 1
    await _seed_guild(session, guild_id)
    await _seed_altar(session, guild_id)

    # Two sessions: the ended one and the new one opened by end_session.
    ended_id = await _start_session(session, guild_id)
    new_session_id = await _start_session(session, guild_id)

    # SettingsService uses the DEFAULTS dict, so no explicit seed needed.

    fp_results = [
        RankingResult(user_id=1001, achievement_key="fourth_place", sp_earned=40, net_sp=30, award_count=1),
    ]

    # Build a mock bot that satisfies all bot.* accesses inside the function.
    mock_bot = MagicMock()
    mock_bot.config.oauth_redirect_uri = "https://example.com"
    mock_bot.get_guild.return_value = None  # guild lookups return None → embed uses fallback

    # Patch embed_builders and broadcast_to_guild so we don't need a real Discord guild.
    with (
        patch(
            "stankbot.scheduling.session_scheduler.embed_builders"
        ) as mock_eb,
        patch(
            "stankbot.scheduling.session_scheduler.broadcast_to_guild",
            new_callable=AsyncMock,
        ),
    ):
        mock_eb.board_url_for.return_value = "https://example.com/board"
        mock_eb.display_name_of = AsyncMock(return_value="TestUser")
        mock_eb.FourthPlaceVars = MagicMock()
        mock_eb.build_fourth_place_embed = AsyncMock(return_value=MagicMock())

        await _broadcast_fourth_place(
            session,
            bot=mock_bot,
            guild_id=guild_id,
            fourth_place_results=fp_results,
            ended_id=ended_id,
        )

    # Query the emitted SP_FOURTH_PLACE event.
    stmt = select(Event).where(
        Event.guild_id == guild_id,
        Event.type == EventType.SP_FOURTH_PLACE,
    )
    result = (await session.execute(stmt)).scalars().all()

    assert len(result) == 1, f"Expected 1 SP_FOURTH_PLACE event, got {len(result)}"
    event = result[0]

    assert event.session_id == ended_id, (
        f"SP_FOURTH_PLACE session_id should be ended_id ({ended_id}), "
        f"got {event.session_id} (new session was {new_session_id})"
    )
    assert event.user_id == 1001
    assert event.delta == 50  # flat_sp only, no chain_length
    assert event.reason == "fourth_place"
