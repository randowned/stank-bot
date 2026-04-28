"""Session list API endpoint — integration tests.

Covers:
    * response includes ended_at, total_sp, total_pp
    * active session has no ended_at
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import EventType, Guild
from stankbot.db.repositories import events as events_repo
from stankbot.web.routes.api import router as api_router


def _build_test_app(db_session: AsyncSession) -> FastAPI:
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


@pytest.mark.asyncio
async def test_session_list_returns_totals_and_ended_at(session: Any) -> None:
    guild = Guild(id=1, name="Test")
    session.add(guild)
    await session.flush()

    sid = (await events_repo.append(session, guild_id=1, type=EventType.SESSION_START)).id
    await events_repo.append(session, guild_id=1, type=EventType.SP_BASE, delta=10, user_id=100, session_id=sid)
    await events_repo.append(session, guild_id=1, type=EventType.SESSION_END, session_id=sid)

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/sessions")

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert len(body) >= 1

    session_data = next(s for s in body if s["session_id"] == sid)
    assert session_data["ended_at"] is not None
    assert session_data["total_sp"] == 10
    assert session_data["total_pp"] == 0
    assert session_data["active"] is False


@pytest.mark.asyncio
async def test_session_list_active_has_no_ended_at(session: Any) -> None:
    guild = Guild(id=1, name="Test")
    session.add(guild)
    await session.flush()

    sid = (await events_repo.append(session, guild_id=1, type=EventType.SESSION_START)).id

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/sessions")

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    session_data = next(s for s in body if s["session_id"] == sid)
    assert session_data["ended_at"] is None
    assert session_data["active"] is True
