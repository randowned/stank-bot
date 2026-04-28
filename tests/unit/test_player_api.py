"""Player profile API endpoint — integration tests against in-memory SQLite.

Covers:
    * response includes discord_avatar, rank, stank_streak
    * nonexistent player returns 404
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import Altar, Chain, EventType, Guild, Player
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
async def test_player_api_returns_avatar_rank_and_streak(session: Any) -> None:
    guild = Guild(id=1, name="Test")
    session.add(guild)
    altar = Altar(guild_id=1, channel_id=200, sticker_id=300, display_name="primary")
    session.add(altar)
    player = Player(
        guild_id=1,
        user_id=100,
        display_name="Alice",
        discord_avatar="abc123",
    )
    session.add(player)
    await session.flush()

    now = datetime.now(tz=UTC)
    sid = (await events_repo.append(session, guild_id=1, type=EventType.SESSION_START)).id

    chain = Chain(
        guild_id=1, altar_id=altar.id, session_id=sid, started_at=now, starter_user_id=100,
    )
    session.add(chain)
    await session.flush()

    await events_repo.append(session, guild_id=1, type=EventType.SP_BASE, delta=10, user_id=100, session_id=sid, chain_id=chain.id)

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/player/100")

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()

    assert body["user_id"] == "100"
    assert body["display_name"] == "Alice"
    assert body["discord_avatar"] == "abc123"
    assert body["rank"] == 1
    assert "stank_streak" in body
    assert body["stank_streak"]["current"] >= 0
    assert body["stank_streak"]["longest"] >= 0
    assert "achievements" in body
    assert "badges" not in body  # badges field was removed


@pytest.mark.asyncio
async def test_player_api_returns_404_for_nonexistent(session: Any) -> None:
    guild = Guild(id=1, name="Test")
    session.add(guild)
    await session.flush()

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/player/999")

    assert resp.status_code == status.HTTP_404_NOT_FOUND
