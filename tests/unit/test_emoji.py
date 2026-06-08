"""Tests for the shared reaction-emoji parser."""

from __future__ import annotations

import pytest

from stankbot.utils.emoji import (
    emoji_specs_match,
    emoji_to_markup,
    parse_reaction_emoji,
    parse_reaction_emojis,
)


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


class TestParseReactionEmojis:
    def test_single(self) -> None:
        assert parse_reaction_emojis("<:a:1>") == [
            {"id": 1, "name": "a", "animated": False}
        ]

    def test_multiple_mixed(self) -> None:
        assert parse_reaction_emojis("<:a:1>, 🔥, <a:b:2>") == [
            {"id": 1, "name": "a", "animated": False},
            {"id": None, "name": "🔥", "animated": False},
            {"id": 2, "name": "b", "animated": True},
        ]

    def test_skips_unparseable_and_dedupes(self) -> None:
        assert parse_reaction_emojis("<:a:1>, :junk:, <:a:1>") == [
            {"id": 1, "name": "a", "animated": False}
        ]

    def test_empty(self) -> None:
        assert parse_reaction_emojis("") == []
        assert parse_reaction_emojis(None) == []


class TestEmojiToMarkup:
    def test_custom(self) -> None:
        assert emoji_to_markup({"id": 1, "name": "a", "animated": False}) == "<:a:1>"

    def test_animated(self) -> None:
        assert emoji_to_markup({"id": 2, "name": "b", "animated": True}) == "<a:b:2>"

    def test_glyph(self) -> None:
        assert emoji_to_markup({"id": None, "name": "🔥", "animated": False}) == "🔥"


class TestEmojiSpecsMatch:
    SPECS = [
        {"id": 1, "name": "a", "animated": False},
        {"id": None, "name": "🔥", "animated": False},
    ]

    def test_match_by_id(self) -> None:
        assert emoji_specs_match(self.SPECS, event_id=1, event_name="a") is True

    def test_custom_emoji_matches_by_id_not_name(self) -> None:
        # A custom-emoji spec only matches on id, never on a coincidental name.
        assert emoji_specs_match(self.SPECS, event_id=999, event_name="a") is False

    def test_match_glyph_by_name(self) -> None:
        assert emoji_specs_match(self.SPECS, event_id=None, event_name="🔥") is True

    def test_no_match(self) -> None:
        assert emoji_specs_match(self.SPECS, event_id=2, event_name="nope") is False

    def test_empty_specs(self) -> None:
        assert emoji_specs_match([], event_id=1, event_name="a") is False
