"""Mock media API — only mounted when ENV=dev-mock.

Allows E2E tests to inject media items and mock metrics directly into the DB
without needing real YouTube/Spotify API keys.
"""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, select

from stankbot.db.engine import session_scope
from stankbot.db.models import (
    MediaItem,
    MediaOwner,
    MediaOwnerSnapshot,
    MetricCache,
    MetricSnapshot,
)
from stankbot.db.repositories import media as media_repo
from stankbot.services.media_service import _compute_alignment_mask
from stankbot.web.transport import MsgPackResponse, msgpack_body

router = APIRouter(prefix="/api/mock", tags=["mock-media"])
log = logging.getLogger(__name__)


def _dev_only(request: Request) -> None:
    config = request.app.state.config
    if config.env != "dev-mock":
        raise HTTPException(status_code=403, detail="Mock endpoints only available in dev-mock mode")


class MockClearMediaPayload(BaseModel):
    guild_id: int = 123456789


@router.post("/clear-media")
async def mock_clear_media(
    request: Request,
    payload: MockClearMediaPayload = msgpack_body(MockClearMediaPayload),  # type: ignore[assignment]
) -> MsgPackResponse:
    _dev_only(request)

    async with session_scope(request.app.state.session_factory) as session:
        items = (await session.execute(
            select(MediaItem.id).where(MediaItem.guild_id == payload.guild_id)
        )).scalars().all()

        if items:
            await session.execute(
                delete(MetricSnapshot).where(
                    MetricSnapshot.media_item_id.in_(items)
                )
            )
            await session.execute(
                delete(MetricCache).where(
                    MetricCache.media_item_id.in_(items)
                )
            )
            await session.execute(
                delete(MediaItem).where(MediaItem.guild_id == payload.guild_id)
            )

        # Delete orphan owner snapshots + owners that no media item references
        # (owners are global but each test should start with a clean slate).
        await session.execute(
            delete(MediaOwnerSnapshot).where(
                ~MediaOwnerSnapshot.media_owner_id.in_(
                    select(MediaItem.id).where(MediaItem.channel_id == MediaOwner.external_id)
                )
            )
        )
        await session.execute(
            delete(MediaOwner).where(
                ~MediaOwner.id.in_(
                    select(MediaItem.id).where(MediaItem.channel_id == MediaOwner.external_id)
                )
            )
        )

    return MsgPackResponse({"success": True}, request)


class MockMediaPayload(BaseModel):
    guild_id: int
    media_type: str = "youtube"
    external_id: str | None = None
    name: str | None = None
    history_days: int = 30


@router.post("/media")
async def mock_add_media(
    request: Request,
    payload: MockMediaPayload = msgpack_body(MockMediaPayload),  # type: ignore[assignment]
) -> MsgPackResponse:
    _dev_only(request)

    guild_id = payload.guild_id
    media_type = payload.media_type
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    external_id = (
        payload.external_id
        or f"mock_{media_type}_{guild_id}_{stamp}"
    )
    base_name = payload.name or f"mock-{media_type}-{stamp[-12:]}"
    channel_id = f"UC_mock_{stamp[-12:]}"
    artist_name = "Mock Artist" if media_type == "spotify" else "Mock Channel"

    async with session_scope(request.app.state.session_factory) as session:
        # Handle name collisions by appending a counter
        name = base_name
        attempt = 0
        max_attempts = 10
        while attempt < max_attempts:
            try:
                item = await media_repo.add(
                    session,
                    guild_id=guild_id,
                    media_type=media_type,
                    external_id=f"{external_id}_{attempt}" if attempt > 0 else external_id,
                    title=f"Mock {media_type.capitalize()} Item — {name}",
                    channel_name=artist_name,
                    channel_id=channel_id,
                    thumbnail_url=None,
                    published_at=datetime.now(UTC),
                    duration_seconds=180,
                    added_by=111111111,
                    name=name,
                )
                break
            except Exception:
                await session.rollback()
                attempt += 1
                name = f"{base_name}-{attempt}"
        else:
            raise HTTPException(status_code=500, detail="Failed to insert mock media after retries")

        # Add fake metrics
        now = datetime.now(UTC)
        metric_values = {"view_count": 10000, "like_count": 500, "comment_count": 50}
        if media_type == "spotify":
            metric_values = {"popularity": 75}

        for key, val in metric_values.items():
            await media_repo.upsert_metric_cache(session, item.id, key, val, now)

        # Generate hourly snapshots going back history_days days
        history_days = max(1, min(365, int(payload.history_days)))
        hours_back = history_days * 24
        for hour_offset in range(hours_back, -1, -1):
            ts = now - timedelta(hours=hour_offset)
            mask = _compute_alignment_mask(ts)
            for key, val in metric_values.items():
                # Start at ~half the current value, grow with slight randomness
                fraction = (1 - (hour_offset / hours_back)) if hours_back > 0 else 1.0
                base = int(val * (0.3 + 0.7 * fraction))
                noise = random.randint(-max(1, base // 20), max(1, base // 20))
                await media_repo.insert_metric_snapshot(
                    session, item.id, key, base + noise, ts,
                    alignment_mask=mask,
                )

        # Ensure the latest snapshot matches the cache
        now_mask = _compute_alignment_mask(now)
        for key, val in metric_values.items():
            await media_repo.insert_metric_snapshot(session, item.id, key, val, now,
                                                    alignment_mask=now_mask)

        item.metrics_last_fetched_at = now

        # Create / update owner with historical snapshots
        owner = await media_repo.upsert_owner(
            session,
            media_type=media_type,
            external_id=channel_id,
            name=artist_name,
            external_url=f"https://{'youtube.com/channel' if media_type == 'youtube' else 'open.spotify.com/artist'}/{channel_id}",
        )
        owner_metrics = {"subscriber_count": 1000000, "total_view_count": 50000000, "video_count": 200}
        if media_type == "spotify":
            owner_metrics = {"follower_count": 500000, "popularity": 75}

        # Generate hourly owner snapshots going back history_days days
        for hour_offset in range(hours_back, -1, -1):
            ts = now - timedelta(hours=hour_offset)
            mask = _compute_alignment_mask(ts)
            for key, val in owner_metrics.items():
                # Start at ~half the current value, grow with slight randomness
                fraction = (1 - (hour_offset / hours_back)) if hours_back > 0 else 1.0
                base = int(val * (0.3 + 0.7 * fraction))
                noise = random.randint(-max(1, base // 20), max(1, base // 20))
                await media_repo.insert_owner_snapshot(
                    session, owner.id, key, base + noise, ts,
                    alignment_mask=mask,
                )

        # Ensure the latest owner snapshot matches the current value
        now_mask = _compute_alignment_mask(now)
        for key, val in owner_metrics.items():
            await media_repo.insert_owner_snapshot(session, owner.id, key, val, now,
                                                   alignment_mask=now_mask)

    return MsgPackResponse(
        {"success": True, "id": item.id, "name": name}, request, status_code=201
    )


class MockMediaMilestonePayload(BaseModel):
    guild_id: int = 123456789
    media_item_id: int
    media_type: str = "youtube"
    metric_key: str = "view_count"
    milestone_value: int = 10000
    new_value: int = 10001
    title: str = "Mock Milestone"
    channel_name: str | None = None
    thumbnail_url: str | None = None
    name: str | None = None
    external_id: str | None = None


@router.post("/media-milestone")
async def mock_media_milestone(
    request: Request,
    payload: MockMediaMilestonePayload = msgpack_body(MockMediaMilestonePayload),  # type: ignore[assignment]
) -> MsgPackResponse:
    _dev_only(request)
    from stankbot.web.ws import MSG_TYPE_MEDIA_MILESTONE, manager

    await manager.broadcast_json(
        payload.guild_id,
        {
            "t": MSG_TYPE_MEDIA_MILESTONE,
            "d": {
                "media_item_id": payload.media_item_id,
                "media_type": payload.media_type,
                "metric_key": payload.metric_key,
                "milestone_value": payload.milestone_value,
                "new_value": payload.new_value,
                "title": payload.title,
                "channel_name": payload.channel_name,
                "thumbnail_url": payload.thumbnail_url,
                "name": payload.name,
                "external_id": payload.external_id,
            },
        },
    )
    return MsgPackResponse({"broadcast": True}, request)


class MockOwnerMetricPayload(BaseModel):
    guild_id: int = 123456789
    owner_id: int
    media_type: str = "youtube"
    metric_key: str = "subscriber_count"
    value: int = 1_000_000


@router.post("/owner-metric-update")
async def mock_owner_metric_update(
    request: Request,
    payload: MockOwnerMetricPayload = msgpack_body(MockOwnerMetricPayload),  # type: ignore[assignment]
) -> MsgPackResponse:
    _dev_only(request)
    from stankbot.web.ws import MSG_TYPE_OWNER_SNAPSHOT, manager

    await manager.broadcast_json(
        payload.guild_id,
        {
            "t": MSG_TYPE_OWNER_SNAPSHOT,
            "d": {
                "owner_id": payload.owner_id,
                "media_type": payload.media_type,
                "metric_key": payload.metric_key,
                "value": payload.value,
            },
        },
    )
    return MsgPackResponse({"broadcast": True}, request)


class MockMediaMetricsPayload(BaseModel):
    guild_id: int = 123456789
    media_item_id: int
    metrics: dict[str, int | float]


@router.post("/media-metrics")
async def mock_media_metrics(
    request: Request,
    payload: MockMediaMetricsPayload = msgpack_body(MockMediaMetricsPayload),  # type: ignore[assignment]
) -> MsgPackResponse:
    _dev_only(request)
    from datetime import UTC, datetime

    async with session_scope(request.app.state.session_factory) as session:
        for key, val in payload.metrics.items():
            await media_repo.upsert_metric_cache(session, payload.media_item_id, key, int(val), datetime.now(UTC))
    return MsgPackResponse({"updated": True}, request)
