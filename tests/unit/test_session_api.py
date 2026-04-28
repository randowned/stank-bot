"""Session detail API endpoint — integration tests against in-memory SQLite.

Covers:
    * response includes total_sp, total_pp, total_stanks, total_reactions
    * response includes session_leaderboard
    * nonexistent session returns 404
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
async def test_session_api_returns_totals_and_leaderboard(session: Any) -> None:
    guild = Guild(id=1, name="Test")
    session.add(guild)
    altar = Altar(guild_id=1, channel_id=200, sticker_id=300, display_name="primary")
    session.add(altar)
    session.add(Player(guild_id=1, user_id=100, display_name="Alice"))
    session.add(Player(guild_id=1, user_id=200, display_name="Bob"))
    await session.flush()

    now = datetime.now(tz=UTC)
    sid = (await events_repo.append(session, guild_id=1, type=EventType.SESSION_START)).id

    chain = Chain(
        guild_id=1, altar_id=altar.id, session_id=sid, started_at=now, starter_user_id=100,
    )
    session.add(chain)
    await session.flush()

    await events_repo.append(session, guild_id=1, type=EventType.SP_BASE, delta=10, user_id=100, session_id=sid, chain_id=chain.id)
    await events_repo.append(session, guild_id=1, type=EventType.SP_STARTER_BONUS, delta=15, user_id=100, session_id=sid, chain_id=chain.id)
    await events_repo.append(session, guild_id=1, type=EventType.SP_POSITION_BONUS, delta=1, user_id=100, session_id=sid, chain_id=chain.id)
    await events_repo.append(session, guild_id=1, type=EventType.SP_BASE, delta=10, user_id=200, session_id=sid, chain_id=chain.id)
    await events_repo.append(session, guild_id=1, type=EventType.PP_BREAK, delta=25, user_id=200, session_id=sid, chain_id=chain.id)
    await events_repo.append(session, guild_id=1, type=EventType.CHAIN_START, chain_id=chain.id, session_id=sid, user_id=100)

    await session.flush()

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/session/{sid}")

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()

    # Totals
    assert body["total_sp"] == 36  # 10 + 15 + 1 + 10
    assert body["total_pp"] == 25
    assert body["total_stanks"] == 2

    # Leaderboard
    lb = body["session_leaderboard"]
    assert len(lb) >= 2
    alice = next(r for r in lb if r["user_id"] == "100")
    bob = next(r for r in lb if r["user_id"] == "200")
    assert alice["earned_sp"] == 26
    assert bob["punishments"] == 25
    assert alice["net"] > bob["net"]  # Alice should be ranked higher

    # Chains
    assert len(body["chains"]) >= 1
    assert body["chains_started"] == 1


@pytest.mark.asyncio
async def test_session_api_returns_404_for_nonexistent(session: Any) -> None:
    guild = Guild(id=1, name="Test")
    session.add(guild)
    await session.flush()

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/session/999")

    assert resp.status_code == status.HTTP_404_NOT_FOUND
