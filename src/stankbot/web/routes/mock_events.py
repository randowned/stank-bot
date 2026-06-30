"""Mock event API — only mounted when ENV=dev-mock.

These endpoints allow manual and automated injection of fake stanks,
breaks, and reactions for local development and Playwright E2E tests.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select, text

from stankbot.db.engine import session_scope
from stankbot.db.models import SessionEndReason
from stankbot.services.session_service import SessionService
from stankbot.web.tools import get_config
from stankbot.web.transport import MsgPackResponse

router = APIRouter(prefix="/api/mock", tags=["mock"])
log = logging.getLogger(__name__)


def _dev_only(request: Request) -> None:
    config = request.app.state.config
    if config.env != "dev-mock":
        raise HTTPException(status_code=403, detail="Mock endpoints only available in dev-mock mode")


def _get_bridge(request: Request):
    """Lazy-initialize the MockEventBridge on first use."""
    bridge = getattr(request.app.state, "_mock_event_bridge", None)
    if bridge is None:
        from stankbot.services.mock_event_bridge import MockEventBridge

        bridge = MockEventBridge(
            request.app.state.session_factory,
            request.app.state.config,
        )
        request.app.state._mock_event_bridge = bridge
    return bridge


def _get_generator(request: Request):
    """Lazy-initialize the MockEventGenerator on first use."""
    gen = getattr(request.app.state, "_mock_event_generator", None)
    if gen is None:
        from stankbot.services.mock_event_generator import MockEventGenerator

        config = request.app.state.config
        guild_id = config.mock_default_guild_id or config.default_guild_id
        bridge = _get_bridge(request)
        gen = MockEventGenerator(bridge, guild_id, interval=config.mock_auto_events_interval)
        request.app.state._mock_event_generator = gen
    return gen


@router.post("/stank")
async def mock_stank(
    request: Request,
    config=Depends(get_config),
) -> MsgPackResponse:
    _dev_only(request)
    body = await request.json()
    guild_id = body.get("guild_id", config.mock_default_guild_id or config.default_guild_id)
    user_id = body.get("user_id", 1001)
    display_name = body.get("display_name", "Alice")

    bridge = _get_bridge(request)
    await bridge.ensure_guild(guild_id)
    result = await bridge.inject_stank(guild_id, user_id, display_name)
    return MsgPackResponse(result, request)


@router.post("/break")
async def mock_break(
    request: Request,
    config=Depends(get_config),
) -> MsgPackResponse:
    _dev_only(request)
    body = await request.json()
    guild_id = body.get("guild_id", config.mock_default_guild_id or config.default_guild_id)
    user_id = body.get("user_id", 1001)
    display_name = body.get("display_name", "Alice")

    bridge = _get_bridge(request)
    await bridge.ensure_guild(guild_id)
    result = await bridge.inject_break(guild_id, user_id, display_name)
    return MsgPackResponse(result, request)


@router.post("/reaction")
async def mock_reaction(
    request: Request,
    config=Depends(get_config),
) -> MsgPackResponse:
    _dev_only(request)
    body = await request.json()
    guild_id = body.get("guild_id", config.mock_default_guild_id or config.default_guild_id)
    message_id = body.get("message_id", 10_000_001)
    user_id = body.get("user_id", 1001)
    sticker_id = body.get("sticker_id", 1)

    bridge = _get_bridge(request)
    await bridge.ensure_guild(guild_id)
    result = await bridge.inject_reaction(guild_id, message_id, user_id, sticker_id)
    return MsgPackResponse(result, request)


@router.post("/noise")
async def mock_noise(
    request: Request,
    config=Depends(get_config),
) -> MsgPackResponse:
    _dev_only(request)
    body = await request.json()
    guild_id = body.get("guild_id", config.mock_default_guild_id or config.default_guild_id)
    user_id = body.get("user_id", 1001)
    display_name = body.get("display_name", "Alice")

    bridge = _get_bridge(request)
    await bridge.ensure_guild(guild_id)
    result = await bridge.inject_noise(guild_id, user_id, display_name)
    return MsgPackResponse(result, request)


@router.post("/session/start")
async def mock_session_start(
    request: Request,
    config=Depends(get_config),
) -> MsgPackResponse:
    _dev_only(request)
    body = await request.json()
    guild_id = body.get("guild_id", config.mock_default_guild_id or config.default_guild_id)

    async with session_scope(request.app.state.session_factory) as session:
        svc = SessionService(session)
        session_id = await svc.start(guild_id)
    return MsgPackResponse({"session_id": session_id}, request)


@router.post("/session/end")
async def mock_session_end(
    request: Request,
    config=Depends(get_config),
) -> MsgPackResponse:
    _dev_only(request)
    body = await request.json()
    guild_id = body.get("guild_id", config.mock_default_guild_id or config.default_guild_id)

    async with session_scope(request.app.state.session_factory) as session:
        svc = SessionService(session)
        end_result = await svc.end_session(guild_id, reason=SessionEndReason.MANUAL)
    return MsgPackResponse(
        {"ended_session_id": end_result.ended_session_id, "new_session_id": end_result.new_session_id},
        request,
    )


@router.post("/random/start")
async def mock_random_start(
    request: Request,
    config=Depends(get_config),
) -> MsgPackResponse:
    _dev_only(request)
    body = await request.json()
    interval = body.get("interval", config.mock_auto_events_interval)
    guild_id = body.get("guild_id", config.mock_default_guild_id or config.default_guild_id)

    gen = _get_generator(request)
    gen.guild_id = guild_id
    gen.interval = interval
    await gen.start()
    return MsgPackResponse({"status": "started", "interval": interval, "guild_id": guild_id}, request)


@router.post("/random/stop")
async def mock_random_stop(
    request: Request,
) -> MsgPackResponse:
    _dev_only(request)
    gen = _get_generator(request)
    await gen.stop()
    return MsgPackResponse({"status": "stopped"}, request)


@router.post("/bot-guilds")
async def mock_set_bot_guilds(
    request: Request,
) -> MsgPackResponse:
    _dev_only(request)
    body = await request.json()
    request.app.state.bot_guilds = body.get("guilds", [])
    return MsgPackResponse({"ok": True}, request)


@router.get("/state")
async def mock_state(
    request: Request,
) -> MsgPackResponse:
    _dev_only(request)
    gen = getattr(request.app.state, "_mock_event_generator", None)
    running = gen is not None and gen._task is not None and not gen._task.done()
    return MsgPackResponse({
        "running": running,
        "interval": getattr(gen, "interval", None) if gen else None,
        "guild_id": getattr(gen, "guild_id", None) if gen else None,
    }, request)


@router.post("/version")
async def mock_set_version(
    request: Request,
) -> MsgPackResponse:
    """Override the server version for testing version mismatch notifications."""
    _dev_only(request)
    body = await request.json()
    version = body.get("version", "0.0.0")
    request.app.state.app_version = version
    return MsgPackResponse({"version": version}, request)


@router.post("/leaderboard-seed")
async def mock_leaderboard_seed(
    request: Request,
    config=Depends(get_config),
) -> MsgPackResponse:
    """Bulk inject stanks to create a dense leaderboard for visual testing."""
    _dev_only(request)
    body = await request.json()
    guild_id = body.get("guild_id", config.mock_default_guild_id or config.default_guild_id)
    count = int(body.get("count", 25))
    base_user_id = int(body.get("base_user_id", 10_000))
    prefix = body.get("prefix", "SeedUser")

    bridge = _get_bridge(request)
    await bridge.ensure_guild(guild_id)
    results = []
    for i in range(count):
        uid = base_user_id + i
        name = f"{prefix}{i}"
        result = await bridge.inject_stank(guild_id, uid, name)
        results.append(result)
    return MsgPackResponse({"injected": len(results), "guild_id": guild_id}, request)


@router.post("/version-broadcast")
async def mock_version_broadcast(
    request: Request,
) -> MsgPackResponse:
    """Immediately broadcast a version mismatch event to all connected clients."""
    _dev_only(request)
    body = await request.json()
    server_version = body.get("server_version", "99.99.99")
    client_version = body.get("client_version", "0.0.0")
    guild_id = body.get("guild_id", 0)

    from stankbot.web.ws import MSG_TYPE_VERSION_MISMATCH, manager

    await manager.broadcast_json(
        guild_id,
        {
            "t": MSG_TYPE_VERSION_MISMATCH,
            "d": {
                "server_version": server_version,
                "client_version": client_version,
            },
        },
    )
    return MsgPackResponse({"broadcast": True}, request)


@router.post("/achievement")
async def mock_achievement(
    request: Request,
    config=Depends(get_config),
) -> MsgPackResponse:
    """Insert PlayerBadge rows and optionally broadcast via WebSocket."""
    _dev_only(request)
    body = await request.json()
    guild_id = body.get("guild_id", config.mock_default_guild_id or config.default_guild_id)
    user_id = int(body.get("user_id", 1001))
    achievement_key = body.get("achievement_key", "first_stank")
    count = int(body.get("count", 1))
    broadcast = body.get("broadcast", True)

    from stankbot.db.models import Achievement, PlayerBadge
    from stankbot.services import achievements as achievements_svc

    async with session_scope(request.app.state.session_factory) as session:
        # Ensure the achievement row exists in the catalog table.
        existing_ach = (
            await session.execute(
                select(Achievement).where(Achievement.key == achievement_key)
            )
        ).scalar_one_or_none()
        if existing_ach is None:
            # Insert from the code catalog.
            cat_row = next(
                (r for r in achievements_svc.catalog_rows() if r["key"] == achievement_key),
                None,
            )
            if cat_row is None:
                return MsgPackResponse(
                    {"error": f"Unknown achievement key: {achievement_key}"},
                    request,
                    status_code=400,
                )
            session.add(
                Achievement(
                    key=cat_row["key"],
                    name=cat_row["name"],
                    description=cat_row["description"],
                    icon=cat_row["icon"],
                    rule_json=cat_row["rule_json"],
                    is_global=cat_row["is_global"],
                )
            )
            await session.flush()

        # Upsert: set award_count on the single row for this user+achievement.
        existing_badge = (
            await session.execute(
                select(PlayerBadge).where(
                    PlayerBadge.guild_id == guild_id,
                    PlayerBadge.user_id == user_id,
                    PlayerBadge.achievement_key == achievement_key,
                )
            )
        ).scalar_one_or_none()
        if existing_badge is not None:
            existing_badge.award_count = max(count, 1)
        else:
            session.add(
                PlayerBadge(
                    guild_id=guild_id,
                    user_id=user_id,
                    achievement_key=achievement_key,
                    award_count=max(count, 1),
                )
            )
        await session.flush()

        # Resolve the badge name/icon for broadcast.
        cat_row = next(
            (r for r in achievements_svc.catalog_rows() if r["key"] == achievement_key),
            None,
        )

    if broadcast and cat_row:
        from stankbot.web.ws import notify_achievement

        await notify_achievement(
            guild_id,
            user_id,
            {
                "key": cat_row["key"],
                "name": cat_row["name"],
                "icon": cat_row["icon"],
                "description": cat_row["description"],
                "unlocked_at": datetime.now(tz=UTC).isoformat(),
            },
        )

    return MsgPackResponse(
        {"ok": True, "achievement_key": achievement_key, "count": count},
        request,
    )


@router.post("/db/reset")
async def mock_db_reset(
    request: Request,
) -> MsgPackResponse:
    """Reset all mock data — clears events, sessions, media, and derived rows.

    Only available in dev-mock mode. Used between E2E spec files to prevent
    cross-file data contamination (shared SQLite DB accumulates data).
    Re-seeds the default guild/altar/players after clearing.
    """
    _dev_only(request)

    from stankbot.db.models import (
        Achievement,
        Chain,
        ChainMessage,
        Cooldown,
        Event,
        Guild,
        MediaItem,
        MediaMilestone,
        MediaOwner,
        MediaOwnerMilestone,
        MediaOwnerSnapshot,
        MetricCache,
        MetricSnapshot,
        Player,
        PlayerBadge,
        PlayerChainTotal,
        PlayerTotal,
        ReactionAward,
        Record,
        TissueCount,
    )

    # Stop the random event generator so it doesn't re-insert during cleanup
    gen = getattr(request.app.state, "_mock_event_generator", None)
    if gen is not None:
        try:
            await gen.stop()
        except Exception:
            pass

    async with session_scope(request.app.state.session_factory) as session:
        # Delete data tables — FK-safe order (children first)
        tables = [
            ReactionAward,
            PlayerBadge,
            ChainMessage,
            MetricSnapshot,
            MetricCache,
            MediaMilestone,
            MediaOwnerSnapshot,
            MediaOwnerMilestone,
            MediaOwner,
            MediaItem,
            TissueCount,
            PlayerChainTotal,
            PlayerTotal,
            Cooldown,
            Record,
            Event,
            Chain,
            Player,
            Achievement,
            Guild,
        ]
        for table in tables:
            await session.execute(delete(table))
        # Reset auto-increment counters for clean IDs
        if request.app.state.config.database_url.startswith("sqlite"):
            for table in tables:
                await session.execute(
                    text(f"DELETE FROM sqlite_sequence WHERE name='{table.__tablename__}'")
                )

    # Re-seed the base guild structure for the next test
    config = request.app.state.config
    bridge = _get_bridge(request)
    guild_id = config.mock_default_guild_id or config.default_guild_id
    await bridge.ensure_guild(guild_id)

    return MsgPackResponse({"success": True}, request)


@router.post("/achievement-broadcast")
async def mock_achievement_broadcast(
    request: Request,
) -> MsgPackResponse:
    """Broadcast an achievement WS event without inserting DB rows.

    Use this to test the toast notification independently of the DB state.
    """
    _dev_only(request)
    body = await request.json()
    guild_id = body.get("guild_id", 123456789)
    user_id = body.get("user_id", 1001)
    badge = body.get("badge", {
        "key": "first_stank",
        "name": "First Stank",
        "icon": "✨",
        "description": "Dropped your very first stank.",
    })

    from stankbot.web.ws import notify_achievement

    await notify_achievement(guild_id, int(user_id), badge)
    return MsgPackResponse({"broadcast": True}, request)
