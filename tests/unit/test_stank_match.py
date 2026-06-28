"""Tests for the shared sticker-name matcher (comma-separated patterns)."""

from __future__ import annotations

from stankbot.utils.stank_match import (
    split_patterns,
    sticker_id_matches,
    sticker_name_matches,
)


class TestSplitPatterns:
    def test_single(self) -> None:
        assert split_patterns("stank") == ["stank"]

    def test_comma_separated_trimmed_lowercased(self) -> None:
        assert split_patterns("Stank,  Maphra Wink ") == ["stank", "maphra wink"]

    def test_blanks_dropped(self) -> None:
        assert split_patterns("stank, ,,  ") == ["stank"]

    def test_empty(self) -> None:
        assert split_patterns("") == []
        assert split_patterns(None) == []


class TestStickerNameMatches:
    def test_single_substring(self) -> None:
        assert sticker_name_matches("stank", ["Stank Jr."]) is True

    def test_case_insensitive(self) -> None:
        assert sticker_name_matches("STANK", ["stank"]) is True

    def test_any_of_several_patterns(self) -> None:
        assert sticker_name_matches("stank, maphra wink", ["Maphra Wink :3"]) is True
        assert sticker_name_matches("stank, maphra wink", ["plain stank"]) is True

    def test_no_match(self) -> None:
        assert sticker_name_matches("stank, maphra wink", ["totally other"]) is False

    def test_multiple_stickers_one_matches(self) -> None:
        assert sticker_name_matches("maphra wink", ["nope", "a maphra wink b"]) is True

    def test_empty_pattern_never_matches(self) -> None:
        assert sticker_name_matches("", ["stank"]) is False
        assert sticker_name_matches(None, ["stank"]) is False

    def test_none_sticker_name(self) -> None:
        assert sticker_name_matches("stank", [None]) is False


class TestStickerIdMatches:
    def test_single_match(self) -> None:
        assert sticker_id_matches([123, 456], [123]) is True

    def test_no_match(self) -> None:
        assert sticker_id_matches([123, 456], [789]) is False

    def test_empty_allowed_ids(self) -> None:
        assert sticker_id_matches([], [123]) is False
        assert sticker_id_matches(None, [123]) is False

    def test_multiple_sticker_ids_one_matches(self) -> None:
        assert sticker_id_matches([123], [456, 123]) is True

    def test_multiple_stickers_all_match(self) -> None:
        assert sticker_id_matches([123, 456], [123, 456]) is True
