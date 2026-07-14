"""Tests for chain_listener._is_stank_message — substring sticker name matching."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from stankbot.cogs.chain_listener import _is_stank_message, _is_stank_voice
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


# ---------------------------------------------------------------------------
# Voice message stank detection
# ---------------------------------------------------------------------------


@pytest.fixture
def altar_with_voice(altar: Altar) -> Altar:
    altar.voice_keywords = ["stank"]
    altar.voice_grit_bonus = 2
    altar.voice_grit_threshold = 0.6
    return altar


def make_voice_message(
    *,
    is_voice: bool = True,
    audio_bytes: bytes = b"mock-audio-data",
) -> Mock:
    msg = Mock()
    msg.content = ""
    msg.stickers = []
    msg.id = 12345
    author = Mock()
    author.id = 98765
    msg.author = author
    msg.type = Mock()
    if is_voice:
        att = Mock()
        att.is_voice_message = True
        att.read = AsyncMock(return_value=audio_bytes)
        msg.attachments = [att]
    else:
        msg.attachments = []
    return msg


@pytest.fixture
def mock_voice_pipeline(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Replace the voice_service.analyze function with a controllable mock."""
    import stankbot.cogs.chain_listener as cl

    mock_result = Mock()
    mock_result.is_stank = False
    mock_result.bonus_sp = 0
    mock_result.text = ""
    mock_result.grit_score = 0.0

    cl.analyze_voice = Mock(return_value=mock_result)

    yield mock_result

    # Restore after test
    from stankbot.services.voice_service import analyze as real_analyze

    cl.analyze_voice = real_analyze


class TestIsStankVoice:
    """Tests for _is_stank_voice — voice message keyword + grit detection."""

    async def test_no_keywords_disabled(self, altar: Altar) -> None:
        """When voice_keywords is None, voice messages are not checked."""
        altar.voice_keywords = None
        msg = make_voice_message()
        is_stank, bonus = await _is_stank_voice(msg, altar)
        assert is_stank is False
        assert bonus == 0

    async def test_empty_keywords_disabled(self, altar: Altar) -> None:
        """When voice_keywords is [], voice messages are not checked."""
        altar.voice_keywords = []
        msg = make_voice_message()
        is_stank, bonus = await _is_stank_voice(msg, altar)
        assert is_stank is False
        assert bonus == 0

    async def test_not_a_voice_message(self, altar_with_voice: Altar) -> None:
        """A regular text message with no attachments is not checked."""
        msg = make_voice_message(is_voice=False)
        is_stank, bonus = await _is_stank_voice(msg, altar_with_voice)
        assert is_stank is False
        assert bonus == 0

    async def test_keyword_matches(self, altar_with_voice: Altar, monkeypatch: pytest.MonkeyPatch) -> None:
        """When transcription contains the keyword, is_stank=True."""
        from stankbot.services.voice_service import VoiceResult
        async def fake_analyze(*args, **kwargs) -> VoiceResult:
            return VoiceResult(is_stank=True, text="stank", grit_score=0.5, bonus_sp=0)
        monkeypatch.setattr(
            "stankbot.services.voice_service.analyze",
            fake_analyze,
        )
        is_stank, bonus = await _is_stank_voice(make_voice_message(), altar_with_voice)
        assert is_stank is True
        assert bonus == 0

    async def test_keyword_no_match(self, altar_with_voice: Altar, monkeypatch: pytest.MonkeyPatch) -> None:
        """When transcription doesn't match, is_stank=False."""
        from stankbot.services.voice_service import VoiceResult
        async def fake_analyze(*args, **kwargs) -> VoiceResult:
            return VoiceResult(is_stank=False, text="hello world", grit_score=0.3, bonus_sp=0)
        monkeypatch.setattr(
            "stankbot.services.voice_service.analyze",
            fake_analyze,
        )
        is_stank, bonus = await _is_stank_voice(make_voice_message(), altar_with_voice)
        assert is_stank is False
        assert bonus == 0

    async def test_grit_bonus_awarded(self, altar_with_voice: Altar, monkeypatch: pytest.MonkeyPatch) -> None:
        """Grit bonus awarded when grit_score >= threshold."""
        from stankbot.services.voice_service import VoiceResult
        async def fake_analyze(*args, **kwargs) -> VoiceResult:
            return VoiceResult(is_stank=True, text="stank", grit_score=0.85, bonus_sp=2)
        monkeypatch.setattr(
            "stankbot.services.voice_service.analyze",
            fake_analyze,
        )
        is_stank, bonus = await _is_stank_voice(make_voice_message(), altar_with_voice)
        assert is_stank is True
        assert bonus == 2

    async def test_grit_bonus_below_threshold(self, altar_with_voice: Altar, monkeypatch: pytest.MonkeyPatch) -> None:
        """No bonus when grit_score < threshold."""
        from stankbot.services.voice_service import VoiceResult
        async def fake_analyze(*args, **kwargs) -> VoiceResult:
            return VoiceResult(is_stank=True, text="stank", grit_score=0.3, bonus_sp=0)
        monkeypatch.setattr(
            "stankbot.services.voice_service.analyze",
            fake_analyze,
        )
        is_stank, bonus = await _is_stank_voice(make_voice_message(), altar_with_voice)
        assert is_stank is True
        assert bonus == 0

    async def test_download_failure_graceful(self, altar_with_voice: Altar) -> None:
        """Failed attachment download doesn't crash — returns False."""
        msg = make_voice_message()
        msg.attachments[0].read = AsyncMock(side_effect=Exception("network error"))
        is_stank, bonus = await _is_stank_voice(msg, altar_with_voice)
        assert is_stank is False
        assert bonus == 0

    async def test_voice_failure_graceful(self, altar_with_voice: Altar, monkeypatch: pytest.MonkeyPatch) -> None:
        """Failed voice pipeline doesn't crash — returns False."""
        async def _broken(*args, **kwargs):
            raise Exception("whisper error")
        monkeypatch.setattr(
            "stankbot.services.voice_service.analyze",
            _broken,
        )
        is_stank, bonus = await _is_stank_voice(make_voice_message(), altar_with_voice)
        assert is_stank is False
        assert bonus == 0
