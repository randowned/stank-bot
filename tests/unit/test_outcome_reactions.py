"""Outcome reactions — every altar message gets exactly one bot reaction.

Valid stank → the altar's configured emoji; cooldown (timeout) → hourglass;
chain break / noise / duplicate → cross.
"""

from __future__ import annotations

import itertools
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from stankbot.cogs import chain_listener as cl_module
from stankbot.cogs.chain_listener import (
    INVALID_REACTION,
    TIMEOUT_REACTION,
    ChainListener,
)
from stankbot.db.models import Altar, Guild
from stankbot.services.chain_service import ChainOutcome

GUILD_ID = 900
CHANNEL_ID = 901
ALTAR_EMOJI = "🥴"

_ids = itertools.count(500_000)


def _next_id() -> int:
    return next(_ids)


class _FakeBot:
    """Minimal bot: one transactional session scope, no Gateway."""

    def __init__(self, session) -> None:  # type: ignore[no-untyped-def]
        self._session = session
        self.session_factory = None
        self.config = SimpleNamespace(oauth_redirect_uri="http://localhost:5173")
        self.user = SimpleNamespace(id=999)

    @asynccontextmanager
    async def db(self):  # type: ignore[no-untyped-def]
        yield self._session


def make_message(
    *,
    author_id: int = 7,
    sticker_name: str | None = "stank",
    content: str = "",
) -> MagicMock:
    guild = MagicMock()
    guild.id = GUILD_ID
    guild.name = "Test Guild"
    guild.get_emoji.return_value = None

    channel = MagicMock()
    channel.id = CHANNEL_ID
    channel.name = "altar"

    author = MagicMock()
    author.id = author_id
    author.bot = False
    author.roles = []
    author.guild_permissions.value = 0
    author.nick = None
    author.name = f"user{author_id}"
    author.global_name = None
    author.avatar = None
    author.display_name = f"User {author_id}"

    msg = MagicMock()
    msg.id = _next_id()
    msg.guild = guild
    msg.channel = channel
    msg.author = author
    msg.content = content
    msg.created_at = datetime.now(tz=UTC)
    msg.stickers = (
        [SimpleNamespace(id=None, name=sticker_name)] if sticker_name else []
    )
    msg.attachments = []
    msg.add_reaction = AsyncMock()
    return msg


@pytest.fixture
async def listener(session):  # type: ignore[no-untyped-def]
    session.add(Guild(id=GUILD_ID, name="Test Guild"))
    session.add(
        Altar(
            guild_id=GUILD_ID,
            channel_id=CHANNEL_ID,
            sticker_id=1,
            sticker_name_pattern="stank",
            reaction_emoji_name=ALTAR_EMOJI,
            display_name=ALTAR_EMOJI,
        )
    )
    await session.flush()
    return ChainListener(_FakeBot(session))  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def quiet_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Silence the announcement/WS side channels — only reactions matter."""
    monkeypatch.setattr(cl_module, "broadcast_to_guild", AsyncMock())
    monkeypatch.setattr(cl_module, "broadcast_rank_update", AsyncMock())
    monkeypatch.setattr(cl_module, "notify_chain_update", AsyncMock())


def reacted_with(message: MagicMock) -> list[object]:
    return [call.args[0] for call in message.add_reaction.await_args_list]


class TestOutcomeReactionDispatch:
    """Unit-level routing: outcome → emoji."""

    async def test_valid_stank_uses_altar_emoji(self, listener) -> None:  # type: ignore[no-untyped-def]
        msg = make_message()
        altar = SimpleNamespace(reaction_emoji_id=None, reaction_emoji_name=ALTAR_EMOJI)
        await listener._react_to_outcome(msg, altar, ChainOutcome.VALID_STANK)
        assert reacted_with(msg) == [ALTAR_EMOJI]

    async def test_cooldown_gets_hourglass(self, listener) -> None:  # type: ignore[no-untyped-def]
        msg = make_message()
        await listener._react_to_outcome(msg, None, ChainOutcome.COOLDOWN)
        assert reacted_with(msg) == [TIMEOUT_REACTION]

    async def test_chain_break_gets_cross(self, listener) -> None:  # type: ignore[no-untyped-def]
        msg = make_message()
        await listener._react_to_outcome(msg, None, ChainOutcome.CHAIN_BREAK)
        assert reacted_with(msg) == [INVALID_REACTION]

    async def test_noise_gets_cross(self, listener) -> None:  # type: ignore[no-untyped-def]
        msg = make_message()
        await listener._react_to_outcome(msg, None, ChainOutcome.NOISE)
        assert reacted_with(msg) == [INVALID_REACTION]

    async def test_duplicate_gets_cross(self, listener) -> None:  # type: ignore[no-untyped-def]
        msg = make_message()
        await listener._react_to_outcome(msg, None, ChainOutcome.DUPLICATE)
        assert reacted_with(msg) == [INVALID_REACTION]


class TestHandleMessageReactions:
    """End-to-end through the listener: DB → ChainService → reaction."""

    async def test_valid_stank_reacts_with_altar_emoji(self, listener) -> None:  # type: ignore[no-untyped-def]
        msg = make_message()
        await listener._handle_message(msg)
        assert reacted_with(msg) == [ALTAR_EMOJI]

    async def test_cooldown_restank_reacts_with_hourglass(self, listener) -> None:  # type: ignore[no-untyped-def]
        first = make_message(author_id=11)
        await listener._handle_message(first)
        assert reacted_with(first) == [ALTAR_EMOJI]

        restank = make_message(author_id=11)
        await listener._handle_message(restank)
        assert reacted_with(restank) == [TIMEOUT_REACTION]

    async def test_chain_break_reacts_with_cross(self, listener) -> None:  # type: ignore[no-untyped-def]
        stank = make_message(author_id=12)
        await listener._handle_message(stank)

        breaker = make_message(author_id=13, sticker_name=None, content="oops")
        await listener._handle_message(breaker)
        assert reacted_with(breaker) == [INVALID_REACTION]

    async def test_noise_reacts_with_cross(self, listener) -> None:  # type: ignore[no-untyped-def]
        noise = make_message(author_id=14, sticker_name=None, content="just chatting")
        await listener._handle_message(noise)
        assert reacted_with(noise) == [INVALID_REACTION]

    async def test_message_outside_altar_channel_gets_no_reaction(self, listener) -> None:  # type: ignore[no-untyped-def]
        msg = make_message()
        msg.channel.id = CHANNEL_ID + 1
        await listener._handle_message(msg)
        msg.add_reaction.assert_not_awaited()
