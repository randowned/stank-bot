"""SessionService — session lifecycle, event-sourced.

Session boundaries are events in the log:
    * ``session_start`` (id X) — X becomes the session_id for all rows
      created until the next ``session_end``.
    * ``session_end`` — closes the window; a new ``session_start`` is
      emitted immediately after unless this was a full reset.

Because sessions are derived from events, **no ``sessions`` table exists**.
Any past session can be reconstructed by filtering the event stream
between two matching start/end markers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import EventType, Record, SessionEndReason
from stankbot.db.repositories import cooldowns as cooldowns_repo
from stankbot.db.repositories import events as events_repo
from stankbot.services import achievements as achievements_svc
from stankbot.services.achievements import SessionCloseResult
from stankbot.services.chain_service import SessionIdProvider

if TYPE_CHECKING:
    from stankbot.db.models import Event

_session_locks: dict[int, asyncio.Lock] = {}


def _lock_for(guild_id: int) -> asyncio.Lock:
    if guild_id not in _session_locks:
        _session_locks[guild_id] = asyncio.Lock()
    return _session_locks[guild_id]


@dataclass(slots=True)
class SessionEndResult:
    """Return type for ``end_session``."""

    ended_session_id: int | None
    new_session_id: int | None
    close_result: SessionCloseResult | None = None


@dataclass(slots=True)
class SessionService(SessionIdProvider):
    """Session lifecycle + "what is the current session_id?" lookups.

    Implements ``SessionIdProvider`` so ``ChainService`` can ask for the
    current session id without knowing about SessionService directly.
    """

    session: AsyncSession

    async def current(self, guild_id: int) -> int | None:
        """Return the id of the currently-alive ``session_start`` event,
        or ``None`` if no session is open.

        "Alive" = the most recent ``session_start`` has no matching
        ``session_end`` yet. Callers that need an id to tag new events
        should prefer ``ensure_started`` so a dead guild auto-opens.
        """
        latest = await events_repo.latest_session_start_id(self.session, guild_id)
        if latest is None:
            return None
        if not await self._session_is_alive(guild_id, latest):
            return None
        return latest

    async def ensure_started(
        self, guild_id: int, *, when: datetime | None = None
    ) -> int:
        """If no session is currently open, emit ``session_start`` and
        return the new session id. Otherwise return the existing id.

        Uses a per-guild lock to prevent two concurrent callers from
        both creating a new session.
        """
        async with _lock_for(guild_id):
            current = await self.current(guild_id)
            if current is not None:
                return current
            event = await events_repo.append(
                self.session,
                guild_id=guild_id,
                type=EventType.SESSION_START,
                reason="session started",
                created_at=when,
            )
            # Fresh session — reset the per-session chain record.
            await self._reset_session_records(guild_id)
            return event.id

    async def end_session(
        self,
        guild_id: int,
        *,
        reason: SessionEndReason = SessionEndReason.AUTO,
        open_new: bool = True,
        when: datetime | None = None,
    ) -> SessionEndResult:
        """Close the current session; optionally open a new one.

        Returns a ``SessionEndResult`` with the ended/new session ids and
        any achievement close data (including fourth-place awards).
        """
        now = when or datetime.now(tz=UTC)
        ended_id = await self.current(guild_id)
        close_result: SessionCloseResult | None = None
        if ended_id is not None:
            await events_repo.append(
                self.session,
                guild_id=guild_id,
                type=EventType.SESSION_END,
                session_id=ended_id,
                reason=str(reason),
                created_at=now,
            )
            # Cooldowns reset at the shift boundary so a player can be the
            # last stank of one shift and the first of the next.
            await cooldowns_repo.clear_for_guild(self.session, guild_id=guild_id)
            participants = await events_repo.session_participants(
                self.session, guild_id, ended_id
            )
            if participants:
                close_result = await achievements_svc.evaluate_session_close(
                    self.session,
                    guild_id=guild_id,
                    user_ids=participants,
                    session_id=ended_id,
                )
        new_id: int | None = None
        if open_new:
            new_event = await events_repo.append(
                self.session,
                guild_id=guild_id,
                type=EventType.SESSION_START,
                reason=f"follows {reason}",
                created_at=now,
            )
            new_id = new_event.id

        # A session boundary occurred — reset the per-session chain record
        # so the new session starts with a blank slate.
        if ended_id is not None or new_id is not None:
            await self._reset_session_records(guild_id)

        return SessionEndResult(
            ended_session_id=ended_id,
            new_session_id=new_id,
            close_result=close_result,
        )

    async def _session_is_alive(self, guild_id: int, session_id: int) -> bool:
        """True if no ``session_end`` event exists for this session id."""
        from sqlalchemy import select

        from stankbot.db.models import Event

        stmt = (
            select(Event.id)
            .where(
                Event.guild_id == guild_id,
                Event.session_id == session_id,
                Event.type == EventType.SESSION_END,
            )
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is None

    async def _reset_session_records(self, guild_id: int) -> None:
        """Delete all SESSION-scope records for every altar in the guild.

        Called at session boundaries so the per-session chain record
        always reflects the *current* session only.
        """
        from sqlalchemy import delete

        await self.session.execute(
            delete(Record).where(
                Record.guild_id == guild_id,
                Record.scope == "session",
            )
        )

    async def session_events(
        self, guild_id: int, session_id: int
    ) -> list[Event]:
        """All events in a given session, ordered oldest-first. Used by
        ``HistoryService`` to build session summaries on demand — no
        snapshot table needed.
        """
        return list(await events_repo.events_in_session(self.session, guild_id, session_id))
