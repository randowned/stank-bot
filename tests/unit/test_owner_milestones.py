"""Tests for owner milestone spam prevention and aggregate metric computation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from stankbot.db.models import Guild, MediaItem
from stankbot.db.repositories import media as media_repo
from stankbot.services.media_providers.base import MetricDef, OwnerResult
from stankbot.services.media_providers.registry import MediaProviderRegistry
from stankbot.services.media_service import (
    _ITEM_TO_OWNER_AGG,
    MediaService,
    RefreshResult,
)

# ── helpers ─────────────────────────────────────────────────────────────────


async def _guild(session: Any, guild_id: int = 1) -> None:
    session.add(Guild(id=guild_id))
    await session.flush()


async def _media_item(
    session: Any,
    guild_id: int = 1,
    media_type: str = "youtube",
    external_id: str = "vid_001",
    title: str = "Test Video",
    channel_id: str | None = "UC_test",
) -> MediaItem:
    item = MediaItem(
        guild_id=guild_id,
        media_type=media_type,
        external_id=external_id,
        title=title,
        added_by=100,
        channel_id=channel_id,
    )
    session.add(item)
    await session.flush()
    return item


def _fake_registry(
    media_type: str = "youtube",
    owner_result: OwnerResult | None = None,
) -> MediaProviderRegistry:
    provider = AsyncMock()
    provider.media_type = media_type
    provider.label = "YouTube"
    provider.icon = "▶️"
    provider.metrics = [
        MetricDef(key="view_count", label="Views"),
        MetricDef(key="like_count", label="Likes"),
        MetricDef(key="comment_count", label="Comments"),
    ]
    provider.owner_metrics = [
        MetricDef(key="subscriber_count", label="Subscribers", icon="📊"),
        MetricDef(key="total_view_count", label="Total Views", icon="👁️"),
        MetricDef(key="total_like_count", label="Total Likes", icon="👍"),
        MetricDef(key="total_comment_count", label="Total Comments", icon="💬"),
        MetricDef(key="video_count", label="Videos", icon="🎬"),
    ]
    provider.fetch_owner = AsyncMock(return_value=owner_result)
    provider.is_configured.return_value = True

    registry = MediaProviderRegistry()
    registry._providers = {media_type: provider}
    return registry


# ── owner milestone spam prevention ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_milestones_on_first_seen_owner(session: Any) -> None:
    """When an owner is seen for the first time, no milestones should fire."""
    await _guild(session)

    owner_data = OwnerResult(
        external_id="UC_test",
        name="Big Channel",
        external_url="https://youtube.com/channel/UC_test",
        thumbnail_url=None,
        metrics={
            "subscriber_count": 10_000_000,
            "total_view_count": 500_000_000,
            "video_count": 100,
        },
    )
    registry = _fake_registry(owner_result=owner_data)
    svc = MediaService(session=session, registry=registry)

    result = RefreshResult()
    now = datetime.now(UTC)
    await svc._refresh_owner("youtube", "UC_test", now, result)

    assert len(result.owner_milestones) == 0


@pytest.mark.asyncio
async def test_milestones_fire_on_subsequent_refresh(session: Any) -> None:
    """After baseline is established, crossing a threshold should fire milestones."""
    await _guild(session)

    initial_data = OwnerResult(
        external_id="UC_test",
        name="Growing Channel",
        external_url="https://youtube.com/channel/UC_test",
        thumbnail_url=None,
        metrics={"subscriber_count": 999_000, "total_view_count": 50_000},
    )
    registry = _fake_registry(owner_result=initial_data)
    svc = MediaService(session=session, registry=registry)

    now = datetime.now(UTC)
    result1 = RefreshResult()
    await svc._refresh_owner("youtube", "UC_test", now, result1)
    assert len(result1.owner_milestones) == 0

    updated_data = OwnerResult(
        external_id="UC_test",
        name="Growing Channel",
        external_url="https://youtube.com/channel/UC_test",
        thumbnail_url=None,
        metrics={"subscriber_count": 1_001_000, "total_view_count": 50_000},
    )
    registry._providers["youtube"].fetch_owner = AsyncMock(return_value=updated_data)

    result2 = RefreshResult()
    await svc._refresh_owner("youtube", "UC_test", now, result2)
    assert len(result2.owner_milestones) == 1
    assert result2.owner_milestones[0].milestone_value == 1_000_000
    assert result2.owner_milestones[0].metric_key == "subscriber_count"


@pytest.mark.asyncio
async def test_milestones_dedup_across_refreshes(session: Any) -> None:
    """Same milestone should not fire twice even if threshold is still crossed."""
    await _guild(session)

    initial = OwnerResult(
        external_id="UC_dedup",
        name="Dedup Channel",
        external_url="https://youtube.com/channel/UC_dedup",
        metrics={"subscriber_count": 999_000},
    )
    registry = _fake_registry(owner_result=initial)
    svc = MediaService(session=session, registry=registry)

    now = datetime.now(UTC)
    await svc._refresh_owner("youtube", "UC_dedup", now, RefreshResult())

    crossed = OwnerResult(
        external_id="UC_dedup",
        name="Dedup Channel",
        external_url="https://youtube.com/channel/UC_dedup",
        metrics={"subscriber_count": 1_001_000},
    )
    registry._providers["youtube"].fetch_owner = AsyncMock(return_value=crossed)

    r1 = RefreshResult()
    await svc._refresh_owner("youtube", "UC_dedup", now, r1)
    assert len(r1.owner_milestones) == 1

    r2 = RefreshResult()
    await svc._refresh_owner("youtube", "UC_dedup", now, r2)
    assert len(r2.owner_milestones) == 0


# ── aggregate metric computation ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_aggregate_metrics_stored_as_snapshots(session: Any) -> None:
    """When item metrics are passed, aggregates are stored as owner snapshots."""
    await _guild(session)

    item1 = await _media_item(session, external_id="vid_001", channel_id="UC_agg")
    item2 = await _media_item(session, external_id="vid_002", channel_id="UC_agg")

    now = datetime.now(UTC)
    await media_repo.upsert_metric_cache(session, item1.id, "view_count", 1000, now)
    await media_repo.upsert_metric_cache(session, item1.id, "like_count", 50, now)
    await media_repo.upsert_metric_cache(session, item1.id, "comment_count", 10, now)
    await media_repo.upsert_metric_cache(session, item2.id, "view_count", 2000, now)
    await media_repo.upsert_metric_cache(session, item2.id, "like_count", 100, now)
    await media_repo.upsert_metric_cache(session, item2.id, "comment_count", 20, now)

    owner_data = OwnerResult(
        external_id="UC_agg",
        name="Agg Channel",
        external_url="https://youtube.com/channel/UC_agg",
        metrics={"subscriber_count": 5000, "total_view_count": 3000, "video_count": 2},
    )
    registry = _fake_registry(owner_result=owner_data)
    svc = MediaService(session=session, registry=registry)

    item_metrics = await media_repo.get_metrics_for_items(
        session, [item1.id, item2.id],
    )
    await svc._refresh_owner(
        "youtube", "UC_agg", now, RefreshResult(),
        item_metrics=item_metrics,
        owner_item_ids=[item1.id, item2.id],
    )

    owner = await media_repo.get_owner(session, "youtube", "UC_agg")
    assert owner is not None
    metrics = await media_repo.get_owner_latest_metrics(session, owner.id)

    assert metrics["subscriber_count"]["value"] == 5000
    assert metrics["total_view_count"]["value"] == 3000
    assert metrics["total_like_count"]["value"] == 150
    assert metrics["total_comment_count"]["value"] == 30
    assert metrics["video_count"]["value"] == 2


@pytest.mark.asyncio
async def test_aggregate_does_not_override_provider_values(session: Any) -> None:
    """If the provider already returns a metric, the aggregate should not replace it."""
    await _guild(session)

    item = await _media_item(session, external_id="vid_001", channel_id="UC_noover")
    now = datetime.now(UTC)
    await media_repo.upsert_metric_cache(session, item.id, "view_count", 500, now)

    owner_data = OwnerResult(
        external_id="UC_noover",
        name="NoOverride Channel",
        external_url="https://youtube.com/channel/UC_noover",
        metrics={"subscriber_count": 1000, "total_view_count": 99999},
    )
    registry = _fake_registry(owner_result=owner_data)
    svc = MediaService(session=session, registry=registry)

    item_metrics = await media_repo.get_metrics_for_items(session, [item.id])
    await svc._refresh_owner(
        "youtube", "UC_noover", now, RefreshResult(),
        item_metrics=item_metrics,
        owner_item_ids=[item.id],
    )

    owner = await media_repo.get_owner(session, "youtube", "UC_noover")
    assert owner is not None
    metrics = await media_repo.get_owner_latest_metrics(session, owner.id)
    assert metrics["total_view_count"]["value"] == 99999


@pytest.mark.asyncio
async def test_get_owner_detail_includes_aggregates(session: Any) -> None:
    """get_owner_detail should fill in aggregate metrics from media items."""
    await _guild(session)

    item = await _media_item(session, external_id="vid_det", channel_id="UC_det")
    now = datetime.now(UTC)
    await media_repo.upsert_metric_cache(session, item.id, "view_count", 7000, now)
    await media_repo.upsert_metric_cache(session, item.id, "like_count", 200, now)
    await media_repo.upsert_metric_cache(session, item.id, "comment_count", 50, now)

    owner_data = OwnerResult(
        external_id="UC_det",
        name="Detail Channel",
        external_url="https://youtube.com/channel/UC_det",
        metrics={"subscriber_count": 3000},
    )
    registry = _fake_registry(owner_result=owner_data)
    svc = MediaService(session=session, registry=registry)

    await svc._refresh_owner("youtube", "UC_det", now, RefreshResult())

    detail = await svc.get_owner_detail(owner.id if (owner := await media_repo.get_owner(session, "youtube", "UC_det")) else 0, guild_id=1)
    assert detail is not None
    profile_metrics = {m["key"]: m["value"] for m in detail["profile"]["metrics"]}
    assert profile_metrics["total_like_count"] == 200
    assert profile_metrics["total_comment_count"] == 50


@pytest.mark.asyncio
async def test_item_to_owner_agg_mapping() -> None:
    """Verify the mapping constants are correct."""
    assert _ITEM_TO_OWNER_AGG["view_count"] == "total_view_count"
    assert _ITEM_TO_OWNER_AGG["like_count"] == "total_like_count"
    assert _ITEM_TO_OWNER_AGG["comment_count"] == "total_comment_count"
    assert _ITEM_TO_OWNER_AGG["playcount"] == "total_playcount"
