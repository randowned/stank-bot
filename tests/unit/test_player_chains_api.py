"""Player chains API endpoint — integration tests against in-memory SQLite.

Covers:
    * returns last 10 chains with user_stanks count
    * returns empty list for player with no chains
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import Altar, Chain, ChainMessage, EventType, Guild
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
async def test_player_chains_returns_recent_chains(session: Any) -> None:
    guild = Guild(id=1, name="Test")
    session.add(guild)
    altar = Altar(guild_id=1, channel_id=200, sticker_id=300, display_name="primary")
    session.add(altar)
    await session.flush()

    now = datetime.now(tz=UTC)
    sid = (await events_repo.append(session, guild_id=1, type=EventType.SESSION_START)).id

    chain = Chain(
        guild_id=1, altar_id=altar.id, session_id=sid, started_at=now, starter_user_id=100,
    )
    session.add(chain)
    await session.flush()

    session.add(ChainMessage(
        chain_id=chain.id, message_id=10_000_001, user_id=100, position=1, created_at=now,
    ))
    session.add(ChainMessage(
        chain_id=chain.id, message_id=10_000_002, user_id=100, position=2, created_at=now,
    ))
    await session.flush()

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/player/100/chains")

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert len(body) == 1
    assert body[0]["chain_id"] == chain.id
    assert body[0]["user_stanks"] == 2


@pytest.mark.asyncio
async def test_player_chains_empty_for_new_player(session: Any) -> None:
    guild = Guild(id=1, name="Test")
    session.add(guild)
    await session.flush()

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/player/999/chains")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == []
