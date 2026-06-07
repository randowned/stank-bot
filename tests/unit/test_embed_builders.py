"""Embed builder tests — milestone embed, progress bar, media embed progress."""

from __future__ import annotations

from typing import Any

import discord

from stankbot.services.embed_builders import (
    _fmt_compact,
    _milestone_progress_bar,
    build_media_milestone_embed,
)
from stankbot.services.media_service import MilestoneInfo


class TestFmtCompact:
    def test_thousands(self) -> None:
        assert _fmt_compact(5_000) == "5K"

    def test_millions(self) -> None:
        assert _fmt_compact(5_000_000) == "5M"

    def test_billions(self) -> None:
        assert _fmt_compact(1_500_000_000) == "1.5B"

    def test_small(self) -> None:
        assert _fmt_compact(42) == "42"

    def test_zero(self) -> None:
        assert _fmt_compact(0) == "0"

    def test_1m_exact(self) -> None:
        assert _fmt_compact(1_000_000) == "1M"


class TestMilestoneProgressBar:
    def test_mid_progress(self) -> None:
        bar = _milestone_progress_bar(5_000_000, 10_000_000)
        assert "50%" in bar
        assert "to 10M" in bar

    def test_full_progress(self) -> None:
        bar = _milestone_progress_bar(10_000_000, 10_000_000)
        assert "100%" in bar

    def test_zero_progress(self) -> None:
        bar = _milestone_progress_bar(0, 1_000_000)
        assert "0%" in bar

    def test_no_milestone_remaining(self) -> None:
        bar = _milestone_progress_bar(2_000_000_000, None)
        assert bar == "No milestones remaining"

    def test_target_zero(self) -> None:
        bar = _milestone_progress_bar(0, 0)
        assert bar == "No milestones remaining"

    def test_almost_done(self) -> None:
        bar = _milestone_progress_bar(999_000, 1_000_000)
        assert "99%" in bar

    def test_segment_based_progress(self) -> None:
        """3.1M between 3M→4M milestone = 10% progress."""
        bar = _milestone_progress_bar(3_100_000, 4_000_000, previous=3_000_000)
        assert "10%" in bar
        assert "to 4M" in bar

    def test_segment_mid_progress(self) -> None:
        """3.5M between 3M→4M = 50% progress."""
        bar = _milestone_progress_bar(3_500_000, 4_000_000, previous=3_000_000)
        assert "50%" in bar


class TestBuildMediaMilestoneEmbed:
    """Integration test — builds a real embed via the template engine.

    Requires the ``session`` fixture because ``template_store.load`` reads
    from the DB before falling back to ``ALL_DEFAULTS``.
    """

    async def test_youtube_milestone_embed_structure(self, session: Any) -> None:
        minfo = MilestoneInfo(
            media_item_id=1,
            media_type="youtube",
            metric_key="view_count",
            milestone_value=10_000_000,
            new_value=10_000_001,
            title="Never Gonna Give You Up",
            channel_name="Rick Astley",
            thumbnail_url="https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
            name="test-video",
            external_id="dQw4w9WgXcQ",
        )
        embed = await build_media_milestone_embed(
            info=minfo,
            other_metrics="\U0001f44d 1.2M  \u00b7  \U0001f4ac 45K",
            chart_url="https://example.com/chart.png",
            guild_id=1,
            session=session,
            base_url="https://stank.bot",
        )

        assert isinstance(embed, discord.Embed)
        # Title is the video title
        assert embed.title == "Never Gonna Give You Up"
        # URL is the YouTube link
        assert embed.url == "https://youtube.com/watch?v=dQw4w9WgXcQ"
        # Thumbnail is the video thumbnail
        assert embed.thumbnail.url == "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
        # Image is the chart URL
        assert embed.image.url == "https://example.com/chart.png"
        # Footer contains the stank.bot link
        assert "stank.bot" in embed.footer.text
        # Color is gold
        assert embed.color == discord.Color(0xFFD700)
        # Has the milestone value field
        assert any("10,000,000" in f.value for f in embed.fields)
        # Has the other metrics field
        assert any("1.2M" in f.value for f in embed.fields)
        # Has the metric label field
        assert any("Views" in f.name for f in embed.fields)

    async def test_spotify_milestone_embed_structure(self, session: Any) -> None:
        minfo = MilestoneInfo(
            media_item_id=2,
            media_type="spotify",
            metric_key="playcount",
            milestone_value=50_000_000,
            new_value=50_000_001,
            title="Blinding Lights",
            channel_name="The Weeknd",
            thumbnail_url="https://i.scdn.co/image/ab67616d0000b273b51a0a46c7d09c4c2b3b4c00",
            name="test-track",
            external_id="0VjIjW4GlUZAMYd2vXMi3b",
        )
        embed = await build_media_milestone_embed(
            info=minfo,
            other_metrics="\U0001f3b5 track",
            chart_url="https://example.com/chart.png",
            guild_id=1,
            session=session,
            base_url="https://stank.bot",
        )

        assert isinstance(embed, discord.Embed)
        assert embed.title == "Blinding Lights"
        assert embed.url == "https://open.spotify.com/spotify/0VjIjW4GlUZAMYd2vXMi3b"
        assert embed.color == discord.Color(0xFFD700)
        assert any("Play Count" in f.name for f in embed.fields)
        assert any("50,000,000" in f.value for f in embed.fields)

    async def test_no_thumbnail_ok(self, session: Any) -> None:
        """Embed should render without a thumbnail if none is provided."""
        minfo = MilestoneInfo(
            media_item_id=3,
            media_type="youtube",
            metric_key="view_count",
            milestone_value=1_000_000,
            new_value=1_000_001,
            title="No Thumb Video",
            channel_name=None,
            thumbnail_url=None,
            name=None,
            external_id="no_thumb",
        )
        embed = await build_media_milestone_embed(
            info=minfo,
            other_metrics="\u2014",
            chart_url="https://example.com/chart.png",
            guild_id=1,
            session=session,
            base_url="",
        )

        assert embed.thumbnail.url is None
        assert "1,000,000" in embed.fields[0].value

    async def test_no_base_url_falls_back_to_provider_url(self, session: Any) -> None:
        minfo = MilestoneInfo(
            media_item_id=4,
            media_type="youtube",
            metric_key="view_count",
            milestone_value=1_000_000,
            new_value=1_000_001,
            title="No Base Test",
            channel_name=None,
            thumbnail_url=None,
            name="test",
            external_id="abc",
        )
        embed = await build_media_milestone_embed(
            info=minfo,
            other_metrics="\u2014",
            chart_url="https://example.com/chart.png",
            guild_id=1,
            session=session,
            base_url="",
        )

        assert embed.url == "https://youtube.com/watch?v=abc"
        assert "https://youtube.com/watch?v=abc" in embed.footer.text


class TestBuildFourthPlaceEmbed:
    """Integration test — builds a real 4th-place embed via the template engine."""

    async def test_fourth_place_embed_structure(self, session: Any) -> None:
        from stankbot.services.embed_builders import (
            FourthPlaceVars,
            build_fourth_place_embed,
        )

        vars_ = FourthPlaceVars(
            user_name="TestPlayer",
            sp_earned=40,
            net_sp=35,
            flat_sp=50,
            chain_length=12,
            award_count=3,
            session_number=7,
        )
        embed = await build_fourth_place_embed(
            altar=None,
            guild=None,
            vars_=vars_,
            board_url="https://stank.bot",
            session=session,
            guild_id=1,
        )

        assert isinstance(embed, discord.Embed)
        assert embed.title is not None and "Fourth Place" in embed.title
        assert embed.color == discord.Color(0xF97316)
        # Description should mention user, SP awarded, and the breakdown
        assert "TestPlayer" in embed.description
        assert "+62 SP" in embed.description  # 50 + 12
        assert "flat 50" in embed.description
        assert "chain 12" in embed.description
        # Achievement field should show award count
        assert any("× **3**" in f.value for f in embed.fields)
        # Footer has session number
        assert embed.footer is not None
        assert "Session #7" in embed.footer.text

    async def test_fourth_place_embed_first_award(self, session: Any) -> None:
        """First award — count is 1."""
        from stankbot.services.embed_builders import (
            FourthPlaceVars,
            build_fourth_place_embed,
        )

        vars_ = FourthPlaceVars(
            user_name="NewPlayer",
            sp_earned=20,
            net_sp=20,
            flat_sp=50,
            chain_length=5,
            award_count=1,
            session_number=1,
        )
        embed = await build_fourth_place_embed(
            altar=None,
            guild=None,
            vars_=vars_,
            board_url="",
            session=session,
            guild_id=1,
        )
        assert any("× **1**" in f.value for f in embed.fields)
        assert "+55 SP" in embed.description  # 50 + 5

    async def test_fourth_place_per_player_chain_length(self, session: Any) -> None:
        """chain_length is per-player stank count, not shared guild chain length.

        Two players with different stank counts get different SP awards.
        """
        from stankbot.services.embed_builders import (
            FourthPlaceVars,
            build_fourth_place_embed,
        )

        # Player A: 15 stanks in the session
        vars_a = FourthPlaceVars(
            user_name="PlayerA",
            sp_earned=60,
            net_sp=55,
            flat_sp=50,
            chain_length=15,
            award_count=2,
            session_number=3,
        )
        embed_a = await build_fourth_place_embed(
            altar=None, guild=None, vars_=vars_a, board_url="",
            session=session, guild_id=1,
        )

        # Player B: 8 stanks in the session
        vars_b = FourthPlaceVars(
            user_name="PlayerB",
            sp_earned=30,
            net_sp=28,
            flat_sp=50,
            chain_length=8,
            award_count=1,
            session_number=3,
        )
        embed_b = await build_fourth_place_embed(
            altar=None, guild=None, vars_=vars_b, board_url="",
            session=session, guild_id=1,
        )

        # SP = flat_sp + chain_length (per-player)
        assert "+65 SP" in embed_a.description   # 50 + 15
        assert "chain 15" in embed_a.description
        assert "+58 SP" in embed_b.description   # 50 + 8
        assert "chain 8" in embed_b.description
