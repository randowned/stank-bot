"""SessionService: event-sourced lifecycle and replay."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from stankbot.db.models import EventType, Guild, SessionEndReason
from stankbot.db.repositories import events as events_repo
from stankbot.services.session_service import SessionService


@pytest.fixture
async def guild(session):  # type: ignore[no-untyped-def]
    g = Guild(id=1, name="Maphra")
    session.add(g)
    await session.flush()
    return g


async def test_current_is_none_before_ensure_started(session, guild) -> None:  # type: ignore[no-untyped-def]
    svc = SessionService(session=session)
    assert await svc.current(guild.id) is None


async def test_ensure_started_emits_session_start_once(session, guild) -> None:  # type: ignore[no-untyped-def]
    svc = SessionService(session=session)
    first = await svc.ensure_started(guild.id)
    second = await svc.ensure_started(guild.id)
    assert first == second  # idempotent while the session is alive
    # Exactly one session_start event
    ids = await events_repo.session_event_ids(session, guild.id)
    assert ids == [first]


async def test_end_session_emits_end_then_start(session, guild) -> None:  # type: ignore[no-untyped-def]
    svc = SessionService(session=session)
    s1 = await svc.ensure_started(guild.id, when=datetime(2026, 4, 19, 0, 0, tzinfo=UTC))
    ended, s2 = await svc.end_session(
        guild.id,
        reason=SessionEndReason.AUTO,
        when=datetime(2026, 4, 19, 7, 0, tzinfo=UTC),
    )
    assert ended == s1
    assert s2 is not None and s2 != s1
    # Sessions in order
    assert await events_repo.session_event_ids(session, guild.id) == [s1, s2]


async def test_end_session_with_open_new_false(session, guild) -> None:  # type: ignore[no-untyped-def]
    svc = SessionService(session=session)
    s1 = await svc.ensure_started(guild.id)
    ended, new = await svc.end_session(
        guild.id, reason=SessionEndReason.BOARD_RESET, open_new=False
    )
    assert ended == s1
    assert new is None
    # No alive session after a reset without re-open.
    assert await svc.current(guild.id) is None
    s2 = await svc.ensure_started(guild.id)
    assert s2 != s1


async def test_session_events_slice(session, guild) -> None:  # type: ignore[no-untyped-def]
    svc = SessionService(session=session)
    s1 = await svc.ensure_started(guild.id)
    # Inject a scoring event in session 1
    await events_repo.append(
        session,
        guild_id=guild.id,
        type=EventType.SP_BASE,
        delta=10,
        user_id=42,
        session_id=s1,
    )
    await svc.end_session(guild.id, reason=SessionEndReason.AUTO)
    s2 = await svc.current(guild.id)
    await events_repo.append(
        session,
        guild_id=guild.id,
        type=EventType.SP_BASE,
        delta=20,
        user_id=42,
        session_id=s2,
    )

    s1_events = await svc.session_events(guild.id, s1)
    s2_events = await svc.session_events(guild.id, s2)
    assert [e.delta for e in s1_events if e.type == EventType.SP_BASE] == [10]
    assert [e.delta for e in s2_events if e.type == EventType.SP_BASE] == [20]
