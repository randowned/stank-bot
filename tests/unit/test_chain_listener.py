"""Tests for chain_listener._is_stank_message — substring sticker name matching."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from stankbot.cogs.chain_listener import _is_stank_message
from stankbot.db.models import Altar


@pytest.fixture
def altar() -> Altar:
    return Altar(
        guild_id=1,
        channel_id=1,
        sticker_id=1,
        sticker_name_pattern="stank",
        display_name="test",
    )


def make_message(content: str = "", sticker_names: list[str | None] | None = None) -> Mock:
    if sticker_names is None:
        sticker_names = []
    msg = Mock()
    msg.content = content
    stickers = []
    for n in sticker_names:
        s = Mock()
        s.name = n
        stickers.append(s)
    msg.stickers = stickers
    return msg


class TestIsStankMessage:
    def test_exact_name_matches(self, altar: Altar) -> None:
        altar.sticker_name_pattern = "stank"
        msg = make_message(sticker_names=["stank"])
        assert _is_stank_message(msg, altar) is True

    def test_exact_name_case_insensitive(self, altar: Altar) -> None:
        altar.sticker_name_pattern = "stank"
        msg = make_message(sticker_names=["StAnK"])
        assert _is_stank_message(msg, altar) is True

    def test_multiword_pattern_matches_decorated_name(self, altar: Altar) -> None:
        # The reported case: a multi-word pattern matches a sticker whose
        # real name carries extra decoration.
        altar.sticker_name_pattern = "maphra wink"
        msg = make_message(sticker_names=["Maphra Wink :3"])
        assert _is_stank_message(msg, altar) is True

    def test_comma_separated_patterns_any_match(self, altar: Altar) -> None:
        altar.sticker_name_pattern = "stank, maphra wink"
        assert _is_stank_message(make_message(sticker_names=["Maphra Wink"]), altar) is True
        assert _is_stank_message(make_message(sticker_names=["a stank b"]), altar) is True
        assert _is_stank_message(make_message(sticker_names=["neither one"]), altar) is False

    def test_substring_matched(self, altar: Altar) -> None:
        altar.sticker_name_pattern = "stank"
        msg = make_message(sticker_names=["Stank Jr."])
        assert _is_stank_message(msg, altar) is True

    def test_prefix_matched(self, altar: Altar) -> None:
        altar.sticker_name_pattern = "stank"
        msg = make_message(sticker_names=["stankbot"])
        assert _is_stank_message(msg, altar) is True

    def test_suffix_matched(self, altar: Altar) -> None:
        altar.sticker_name_pattern = "stank"
        msg = make_message(sticker_names=["bigstank"])
        assert _is_stank_message(msg, altar) is True

    def test_partial_contains_matched(self, altar: Altar) -> None:
        altar.sticker_name_pattern = "stank"
        msg = make_message(sticker_names=["stanky"])
        assert _is_stank_message(msg, altar) is True

    def test_unrelated_name_not_matched(self, altar: Altar) -> None:
        altar.sticker_name_pattern = "stank"
        msg = make_message(sticker_names=["totally unrelated"])
        assert _is_stank_message(msg, altar) is False

    def test_multiple_stickers_one_match(self, altar: Altar) -> None:
        altar.sticker_name_pattern = "stank"
        msg = make_message(sticker_names=["other", "stank", "thing"])
        assert _is_stank_message(msg, altar) is True

    def test_multiple_stickers_no_match(self, altar: Altar) -> None:
        altar.sticker_name_pattern = "stank"
        msg = make_message(sticker_names=["apple", "banana"])
        assert _is_stank_message(msg, altar) is False

    def test_empty_pattern_always_false(self, altar: Altar) -> None:
        altar.sticker_name_pattern = ""
        msg = make_message(sticker_names=["stank"])
        assert _is_stank_message(msg, altar) is False

    def test_message_with_text_content_is_not_stank(self, altar: Altar) -> None:
        altar.sticker_name_pattern = "stank"
        msg = make_message(content="look at my sticker", sticker_names=["stank"])
        assert _is_stank_message(msg, altar) is False

    def test_no_stickers_is_not_stank(self, altar: Altar) -> None:
        altar.sticker_name_pattern = "stank"
        msg = make_message(sticker_names=[])
        assert _is_stank_message(msg, altar) is False

    def test_none_sticker_name_not_matched(self, altar: Altar) -> None:
        altar.sticker_name_pattern = "stank"
        msg = make_message(sticker_names=[None])
        assert _is_stank_message(msg, altar) is False
