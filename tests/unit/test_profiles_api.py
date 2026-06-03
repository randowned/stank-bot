"""E2E tests for the profile (owner/channel) API endpoints and the full
refresh → milestone → aggregate pipeline.

Uses ASGI transport to exercise the real FastAPI routes against an in-memory
SQLite database — the closest to production without a running server.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import Guild, MediaItem
from stankbot.db.repositories import media as media_repo
from stankbot.services.media_providers.base import (
    MediaProvider,
    MetricDef,
    MetricResult,
    OwnerResult,
    ResolvedMedia,
)
from stankbot.services.media_providers.registry import MediaProviderRegistry
from stankbot.services.media_service import MediaService, RefreshResult
from stankbot.web.routes.media_api import router as media_router

# ── stub provider ────────────────────────────────────────────────────────


class _StubYouTubeProvider(MediaProvider):
    media_type = "youtube"
    label = "YouTube"
    icon = "▶️"
    metrics = [
        MetricDef("view_count", "Views", "number", "👁️"),
        MetricDef("like_count", "Likes", "number", "👍"),
        MetricDef("comment_count", "Comments", "number", "💬"),
    ]
    owner_metrics = [
        MetricDef("subscriber_count", "Subscribers", "number", "📊"),
        MetricDef("video_count", "Videos", "number", "🎬"),
        MetricDef("total_view_count", "Total Views", "number", "👁️"),
        MetricDef("total_like_count", "Total Likes", "number", "👍"),
        MetricDef("total_comment_count", "Total Comments", "number", "💬"),
    ]

    def __init__(self) -> None:
        self._owner_data: OwnerResult | None = None

    def is_configured(self) -> bool:
        return True

    async def resolve(self, url_or_id: str) -> ResolvedMedia | None:
        return ResolvedMedia(external_id=url_or_id, title="Test")

    async def fetch_metrics(self, external_ids: list[str]) -> list[MetricResult]:
        metrics_map: dict[str, dict[str, int]] = {
            "vid_a": {"view_count": 200_000, "like_count": 8_000, "comment_count": 1_500},
            "vid_b": {"view_count": 150_000, "like_count": 5_000, "comment_count": 800},
            "vid_c": {"view_count": 50_000, "like_count": 2_000, "comment_count": 200},
        }
        return [
            MetricResult(
                external_id=eid,
                values=metrics_map.get(eid, {"view_count": 5000, "like_count": 100, "comment_count": 20}),
            )
            for eid in external_ids
        ]

    async def fetch_owner(self, external_id: str) -> OwnerResult | None:
        return self._owner_data

    async def health_check(self) -> bool:
        return True


# ── helpers ──────────────────────────────────────────────────────────────

GUILD_ID = 7


def _build_app(session: AsyncSession, registry: MediaProviderRegistry) -> FastAPI:
    from stankbot.web.tools import get_active_guild_id, get_db, require_guild_member

    app = FastAPI()

    async def _db() -> Any:
        yield session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[require_guild_member] = lambda: {"id": "1", "username": "tester"}
    app.dependency_overrides[get_active_guild_id] = lambda: GUILD_ID
    app.state.media_registry = registry
    app.include_router(media_router)
    return app


async def _seed(
    session: AsyncSession,
    provider: _StubYouTubeProvider,
    *,
    channel_id: str = "UC_chan",
    owner_name: str = "Test Channel",
    subscriber_count: int = 50_000,
    total_view_count: int = 500_000,
    video_count: int = 3,
) -> tuple[MediaItem, MediaItem, MediaItem]:
    """Create a guild, 3 media items, their metric caches, and an owner."""
    session.add(Guild(id=GUILD_ID))
    await session.flush()

    items: list[MediaItem] = []
    for _i, (eid, title, views, likes, comments) in enumerate([
        ("vid_a", "Song A", 200_000, 8_000, 1_500),
        ("vid_b", "Song B", 150_000, 5_000, 800),
        ("vid_c", "Song C", 50_000, 2_000, 200),
    ]):
        item = MediaItem(
            guild_id=GUILD_ID,
            media_type="youtube",
            external_id=eid,
            title=title,
            channel_id=channel_id,
            channel_name=owner_name,
            added_by=1,
        )
        session.add(item)
        await session.flush()
        now = datetime.now(UTC)
        await media_repo.upsert_metric_cache(session, item.id, "view_count", views, now)
        await media_repo.upsert_metric_cache(session, item.id, "like_count", likes, now)
        await media_repo.upsert_metric_cache(session, item.id, "comment_count", comments, now)
        items.append(item)

    provider._owner_data = OwnerResult(
        external_id=channel_id,
        name=owner_name,
        external_url=f"https://youtube.com/channel/{channel_id}",
        thumbnail_url="https://example.com/thumb.jpg",
        cover_url="https://example.com/cover.jpg",
        metrics={
            "subscriber_count": subscriber_count,
            "total_view_count": total_view_count,
            "video_count": video_count,
        },
    )

    return items[0], items[1], items[2]


@pytest.fixture
def provider() -> _StubYouTubeProvider:
    return _StubYouTubeProvider()


@pytest.fixture
def registry(provider: _StubYouTubeProvider) -> MediaProviderRegistry:
    r = MediaProviderRegistry()
    r.register(provider)
    return r


# ── profiles listing ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_profiles_listing_returns_aggregate_likes_and_comments(
    session: AsyncSession,
    provider: _StubYouTubeProvider,
    registry: MediaProviderRegistry,
) -> None:
    """GET /api/media/profiles should include total_like_count and
    total_comment_count computed from media items."""
    await _seed(session, provider)

    svc = MediaService(session=session, registry=registry)
    now = datetime.now(UTC)
    await svc._refresh_owner("youtube", "UC_chan", now, RefreshResult())

    app = _build_app(session, registry)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/media/profiles")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    profiles = data["profiles"]
    assert len(profiles) == 1

    profile = profiles[0]
    metrics_by_key = {m["key"]: m["value"] for m in profile["metrics"]}
    assert metrics_by_key["subscriber_count"] == 50_000
    assert metrics_by_key["total_like_count"] == 15_000
    assert metrics_by_key["total_comment_count"] == 2_500


@pytest.mark.asyncio
async def test_profiles_listing_media_items_count(
    session: AsyncSession,
    provider: _StubYouTubeProvider,
    registry: MediaProviderRegistry,
) -> None:
    """Profile listing should include the correct media_items_count."""
    await _seed(session, provider)

    svc = MediaService(session=session, registry=registry)
    now = datetime.now(UTC)
    await svc._refresh_owner("youtube", "UC_chan", now, RefreshResult())

    app = _build_app(session, registry)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/media/profiles")

    data = resp.json()
    assert data["profiles"][0]["media_items_count"] == 3


# ── profile detail ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_profile_detail_includes_aggregates(
    session: AsyncSession,
    provider: _StubYouTubeProvider,
    registry: MediaProviderRegistry,
) -> None:
    """GET /api/media/profile/{id} should include computed aggregate metrics."""
    await _seed(session, provider)

    svc = MediaService(session=session, registry=registry)
    now = datetime.now(UTC)
    await svc._refresh_owner("youtube", "UC_chan", now, RefreshResult())

    owner = await media_repo.get_owner(session, "youtube", "UC_chan")
    assert owner is not None

    app = _build_app(session, registry)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/media/profile/{owner.id}")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    profile = data["profile"]
    metrics_by_key = {m["key"]: m["value"] for m in profile["metrics"]}
    assert metrics_by_key["total_like_count"] == 15_000
    assert metrics_by_key["total_comment_count"] == 2_500
    assert data["items_count"] == 3


@pytest.mark.asyncio
async def test_profile_detail_items_include_metrics(
    session: AsyncSession,
    provider: _StubYouTubeProvider,
    registry: MediaProviderRegistry,
) -> None:
    """Profile detail items should have their individual metrics."""
    await _seed(session, provider)

    svc = MediaService(session=session, registry=registry)
    now = datetime.now(UTC)
    await svc._refresh_owner("youtube", "UC_chan", now, RefreshResult())

    owner = await media_repo.get_owner(session, "youtube", "UC_chan")
    assert owner is not None

    app = _build_app(session, registry)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/media/profile/{owner.id}")

    items = resp.json()["items"]
    assert len(items) == 3
    for item in items:
        assert "metrics" in item
        assert "view_count" in item["metrics"]


@pytest.mark.asyncio
async def test_profile_detail_404_for_nonexistent(
    session: AsyncSession,
    provider: _StubYouTubeProvider,
    registry: MediaProviderRegistry,
) -> None:
    """Non-existent profile ID returns 404."""
    session.add(Guild(id=GUILD_ID))
    await session.flush()

    app = _build_app(session, registry)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/media/profile/99999")

    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ── profile history ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_profile_history_returns_snapshots(
    session: AsyncSession,
    provider: _StubYouTubeProvider,
    registry: MediaProviderRegistry,
) -> None:
    """GET /api/media/profile/{id}/history returns time-series data."""
    await _seed(session, provider)

    svc = MediaService(session=session, registry=registry)
    now = datetime.now(UTC)
    await svc._refresh_owner("youtube", "UC_chan", now, RefreshResult())

    owner = await media_repo.get_owner(session, "youtube", "UC_chan")
    assert owner is not None

    app = _build_app(session, registry)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/media/profile/{owner.id}/history?metric=subscriber_count&hours=24"
        )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["owner_id"] == owner.id
    assert data["metric"] == "subscriber_count"
    assert "history" in data
    assert len(data["history"]) >= 1


# ── refresh flow → milestone spam prevention ─────────────────────────────


@pytest.mark.asyncio
async def test_refresh_all_no_milestone_spam_on_first_owner_fetch(
    session: AsyncSession,
    provider: _StubYouTubeProvider,
    registry: MediaProviderRegistry,
) -> None:
    """Full refresh_all flow: first time seeing an owner with 50K subscribers
    should NOT fire any milestones."""
    await _seed(session, provider, subscriber_count=50_000_000)

    svc = MediaService(session=session, registry=registry)
    result = await svc.refresh_all(GUILD_ID)

    assert result.refreshed == 3
    assert len(result.owner_milestones) == 0


@pytest.mark.asyncio
async def test_refresh_all_milestones_fire_on_threshold_crossing(
    session: AsyncSession,
    provider: _StubYouTubeProvider,
    registry: MediaProviderRegistry,
) -> None:
    """After baseline, crossing a threshold fires exactly the right milestones."""
    await _seed(session, provider, subscriber_count=999_000)

    svc = MediaService(session=session, registry=registry)
    r1 = await svc.refresh_all(GUILD_ID)
    assert len(r1.owner_milestones) == 0

    provider._owner_data = OwnerResult(
        external_id="UC_chan",
        name="Test Channel",
        external_url="https://youtube.com/channel/UC_chan",
        metrics={"subscriber_count": 1_001_000, "total_view_count": 500_000, "video_count": 3},
    )

    r2 = await svc.refresh_all(GUILD_ID)
    assert len(r2.owner_milestones) == 1
    assert r2.owner_milestones[0].milestone_value == 1_000_000
    assert r2.owner_milestones[0].metric_key == "subscriber_count"


@pytest.mark.asyncio
async def test_refresh_all_stores_aggregate_snapshots(
    session: AsyncSession,
    provider: _StubYouTubeProvider,
    registry: MediaProviderRegistry,
) -> None:
    """refresh_all should store total_like_count and total_comment_count as
    owner snapshots by aggregating media item metrics."""
    await _seed(session, provider)

    svc = MediaService(session=session, registry=registry)
    await svc.refresh_all(GUILD_ID)

    owner = await media_repo.get_owner(session, "youtube", "UC_chan")
    assert owner is not None
    metrics = await media_repo.get_owner_latest_metrics(session, owner.id)

    assert "total_like_count" in metrics
    assert metrics["total_like_count"]["value"] == 15_000
    assert "total_comment_count" in metrics
    assert metrics["total_comment_count"]["value"] == 2_500


@pytest.mark.asyncio
async def test_refresh_all_provider_total_view_count_not_overridden(
    session: AsyncSession,
    provider: _StubYouTubeProvider,
    registry: MediaProviderRegistry,
) -> None:
    """total_view_count from the YouTube API should NOT be replaced by the
    aggregate from items (provider knows best for views)."""
    await _seed(session, provider, total_view_count=999_999)

    svc = MediaService(session=session, registry=registry)
    await svc.refresh_all(GUILD_ID)

    owner = await media_repo.get_owner(session, "youtube", "UC_chan")
    assert owner is not None
    metrics = await media_repo.get_owner_latest_metrics(session, owner.id)

    assert metrics["total_view_count"]["value"] == 999_999


# ── refresh_single → owner refresh with aggregates ───────────────────────


@pytest.mark.asyncio
async def test_refresh_single_refreshes_owner_with_aggregates(
    session: AsyncSession,
    provider: _StubYouTubeProvider,
    registry: MediaProviderRegistry,
) -> None:
    """refresh_single should also refresh the owner and compute aggregates."""
    items = await _seed(session, provider)

    svc = MediaService(session=session, registry=registry)
    result = await svc.refresh_single(items[0].id)

    assert result.refreshed == 1
    owner = await media_repo.get_owner(session, "youtube", "UC_chan")
    assert owner is not None
    metrics = await media_repo.get_owner_latest_metrics(session, owner.id)
    assert "total_like_count" in metrics
    assert "total_comment_count" in metrics


# ── milestone dedup across refresh cycles ────────────────────────────────


@pytest.mark.asyncio
async def test_milestone_dedup_across_full_refresh_cycles(
    session: AsyncSession,
    provider: _StubYouTubeProvider,
    registry: MediaProviderRegistry,
) -> None:
    """Running refresh_all twice after a threshold is crossed should only
    announce the milestone once (DB upsert dedup)."""
    await _seed(session, provider, subscriber_count=999_000)

    svc = MediaService(session=session, registry=registry)
    await svc.refresh_all(GUILD_ID)

    provider._owner_data = OwnerResult(
        external_id="UC_chan",
        name="Test Channel",
        external_url="https://youtube.com/channel/UC_chan",
        metrics={"subscriber_count": 1_001_000, "total_view_count": 500_000, "video_count": 3},
    )

    r1 = await svc.refresh_all(GUILD_ID)
    assert len(r1.owner_milestones) == 1

    r2 = await svc.refresh_all(GUILD_ID)
    assert len(r2.owner_milestones) == 0


# ── owner refresh error logging (not swallowed silently) ─────────────────


@pytest.mark.asyncio
async def test_refresh_all_logs_owner_error_instead_of_swallowing(
    session: AsyncSession,
    provider: _StubYouTubeProvider,
    registry: MediaProviderRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When _refresh_owner raises, the error should be logged, not silently
    swallowed, and the refresh should still complete for other items."""
    await _seed(session, provider)

    real_fetch = provider.fetch_owner
    provider.fetch_owner = AsyncMock(side_effect=RuntimeError("API timeout"))  # type: ignore[assignment]

    import logging
    svc = MediaService(session=session, registry=registry)
    with caplog.at_level(logging.WARNING, logger="stankbot.services.media_service"):
        result = await svc.refresh_all(GUILD_ID)

    assert result.refreshed == 3
    assert any("owner refresh failed" in r.message for r in caplog.records)

    provider.fetch_owner = real_fetch  # type: ignore[assignment]
