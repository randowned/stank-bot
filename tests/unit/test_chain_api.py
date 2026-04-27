"""Chain detail API endpoint — integration tests against in-memory SQLite.

Covers:
    * response includes reactions_in_chain and stanks_in_chain per user
    * nonexistent chain returns 404
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
async def test_chain_api_returns_reactions_and_stanks(session: Any) -> None:
    guild = Guild(id=1, name="Test")
    session.add(guild)
    altar = Altar(guild_id=1, channel_id=200, sticker_id=300, display_name="primary")
    session.add(altar)
    await session.flush()

    now = datetime.now(tz=UTC)

    sid = (await events_repo.append(session, guild_id=1, type=EventType.SESSION_START)).id

    chain = Chain(
        guild_id=1,
        altar_id=altar.id,
        session_id=sid,
        started_at=now,
        starter_user_id=100,
    )
    session.add(chain)
    await session.flush()

    for pos, uid in [(1, 100), (2, 200), (3, 100)]:
        session.add(ChainMessage(
            chain_id=chain.id,
            message_id=10_000_000 + pos,
            user_id=uid,
            position=pos,
            created_at=now,
        ))
    await session.flush()

    await events_repo.append(
        session, guild_id=1, type=EventType.SP_BASE, delta=10, user_id=100, session_id=sid, chain_id=chain.id
    )
    await events_repo.append(
        session, guild_id=1, type=EventType.SP_BASE, delta=10, user_id=200, session_id=sid, chain_id=chain.id
    )
    await events_repo.append(
        session, guild_id=1, type=EventType.SP_BASE, delta=10, user_id=100, session_id=sid, chain_id=chain.id
    )
    await events_repo.append(
        session, guild_id=1, type=EventType.SP_STARTER_BONUS, delta=15, user_id=100, session_id=sid, chain_id=chain.id
    )
    await events_repo.append(
        session, guild_id=1, type=EventType.SP_POSITION_BONUS, delta=1, user_id=200, session_id=sid, chain_id=chain.id
    )
    await events_repo.append(
        session, guild_id=1, type=EventType.SP_POSITION_BONUS, delta=2, user_id=100, session_id=sid, chain_id=chain.id
    )

    await events_repo.append(
        session, guild_id=1, type=EventType.SP_REACTION, delta=1, user_id=300, session_id=sid, chain_id=chain.id
    )
    await events_repo.append(
        session, guild_id=1, type=EventType.SP_REACTION, delta=1, user_id=400, session_id=sid, chain_id=chain.id
    )
    await events_repo.append(
        session, guild_id=1, type=EventType.SP_REACTION, delta=1, user_id=300, session_id=sid, chain_id=chain.id
    )

    await session.flush()

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/chain/{chain.id}")

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["chain_id"] == chain.id

    lb = body["leaderboard"]
    user_rows = {int(r["user_id"]): r for r in lb}

    assert 100 in user_rows
    assert user_rows[100]["stanks_in_chain"] == 2
    assert user_rows[100]["reactions_in_chain"] == 0
    assert "reactions_in_session" not in user_rows[100]

    assert 200 in user_rows
    assert user_rows[200]["stanks_in_chain"] == 1
    assert user_rows[200]["reactions_in_chain"] == 0

    assert 300 in user_rows
    assert user_rows[300]["stanks_in_chain"] == 0
    assert user_rows[300]["reactions_in_chain"] == 2

    assert 400 in user_rows
    assert user_rows[400]["stanks_in_chain"] == 0
    assert user_rows[400]["reactions_in_chain"] == 1


@pytest.mark.asyncio
async def test_chain_api_returns_404_for_nonexistent_chain(session: Any) -> None:
    guild = Guild(id=1, name="Test")
    session.add(guild)
    await session.flush()

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/chain/999")

    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_chain_api_wrong_guild_returns_404(session: Any) -> None:
    guild = Guild(id=1, name="Test")
    session.add(guild)
    await session.flush()

    chain = Chain(
        guild_id=2,
        altar_id=1,
        session_id=None,
        started_at=datetime.now(tz=UTC),
        starter_user_id=100,
    )
    session.add(chain)
    await session.flush()

    app = _build_test_app(session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/chain/{chain.id}")

    assert resp.status_code == status.HTTP_404_NOT_FOUND
