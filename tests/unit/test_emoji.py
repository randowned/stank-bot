"""Tests for the shared reaction-emoji parser."""

from __future__ import annotations

import pytest

from stankbot.utils.emoji import parse_reaction_emoji


class TestParseReactionEmoji:
    def test_custom_emoji(self) -> None:
        assert parse_reaction_emoji("<:maphra_horns:1506076360647377007>") == (
            1506076360647377007,
            "maphra_horns",
            False,
        )

    def test_custom_emoji_preserves_full_snowflake(self) -> None:
        # The id is a 64-bit snowflake — must survive intact (Python int).
        emoji_id, _name, _animated = parse_reaction_emoji(
            "<:x:1506076360647377007>"
        )
        assert emoji_id == 1506076360647377007

    def test_animated_custom_emoji(self) -> None:
        assert parse_reaction_emoji("<a:party:123>") == (123, "party", True)

    def test_unicode_glyph(self) -> None:
        assert parse_reaction_emoji("🔥") == (None, "🔥", False)

    def test_surrounding_whitespace_trimmed(self) -> None:
        assert parse_reaction_emoji("  <:s:9>  ") == (9, "s", False)

    @pytest.mark.parametrize("raw", ["", "   ", None])
    def test_empty_is_none(self, raw: str | None) -> None:
        assert parse_reaction_emoji(raw) is None

    def test_literal_colon_name_is_none(self) -> None:
        # A bare ``:name:`` (Discord didn't expand it) is unparseable.
        assert parse_reaction_emoji(":stank:") is None

    def test_long_plain_text_is_none(self) -> None:
        assert parse_reaction_emoji("not an emoji at all") is None
