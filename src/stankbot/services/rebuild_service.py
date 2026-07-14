"""Rebuild-from-history — wipe per-guild state and replay altar channels.

Idempotent by construction: every run deletes the derived tables
(events, chains, chain_messages, cooldowns, reaction_awards, records,
player_totals, player_badges) for the target guild first, so re-running
produces the same end-state.

Settings, altars, admin roles, and channel bindings are preserved.

Exposes:
    * ``wipe_guild_state(session, guild_id)`` — deletion half, reusable
      by ``/stank-admin reset``.
    * ``rebuild(bot, guild_id, progress=...)`` — wipe + replay. Needs a
      live discord.py client to read channel history.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import (
    Chain,
    ChainMessage,
    Cooldown,
    Event,
    PlayerBadge,
    PlayerChainTotal,
    PlayerTotal,
    ReactionAward,
    Record,
)
from stankbot.db.repositories import altars as altars_repo
from stankbot.db.repositories import guilds as guilds_repo
from stankbot.services.chain_service import ChainService, StankInput
from stankbot.services.session_service import SessionService
from stankbot.services.settings_service import SettingsService
from stankbot.utils.emoji import emoji_specs_match
from stankbot.utils.stank_match import sticker_id_matches, sticker_name_matches

if TYPE_CHECKING:
    from stankbot.bot import StankBot
    from stankbot.db.models import Altar

log = logging.getLogger(__name__)

ProgressCallback = Callable[[str], Awaitable[None]] | None


@dataclass(slots=True)
class RebuildReport:
    guild_id: int
    altars_scanned: int
    messages_scanned: int
    valid_stanks: int
    chain_breaks: int
    reactions_awarded: int


async def wipe_guild_state(session: AsyncSession, guild_id: int) -> None:
    """Delete derived per-guild rows. Safe to call on a fresh guild."""
    chain_ids = list(
        (
            await session.execute(select(Chain.id).where(Chain.guild_id == guild_id))
        ).scalars()
    )
    if chain_ids:
        await session.execute(
            delete(ChainMessage).where(ChainMessage.chain_id.in_(chain_ids))
        )
    for model in (
        Event,
        Chain,
        Cooldown,
        ReactionAward,
        Record,
        PlayerTotal,
        PlayerBadge,
        PlayerChainTotal,
    ):
        await session.execute(
            delete(model).where(model.guild_id == guild_id),
        )


def _is_stank_message(message: discord.Message, altar: Altar) -> bool:
    """Mirror of ``chain_listener._is_stank_message`` — shares the matcher in
    ``utils.stank_match`` so live scoring and rebuild can't diverge.
    """
    if message.content and message.content.strip():
        return False
    if not message.stickers:
        return False
    # ID-based match first (primary path post-migration)
    if sticker_id_matches(altar.sticker_ids, [s.id for s in message.stickers]):
        return True
    # Fallback: substring name match (deprecated, removed after PROD migration)
    return sticker_name_matches(
        altar.sticker_name_pattern, [s.name for s in message.stickers]
    )


async def _is_stank_voice_rebuild(
    message: discord.Message, altar: Altar
) -> bool:
    """Best-effort voice stank detection for rebuild replay.

    Voice message attachments may have expired CDN URLs, so this is
    wrapped in try/except at the call site. No grit analysis during
    rebuild — just keyword detection.
    """
    keywords = altar.voice_keywords
    if not keywords:
        return False
    if not message.attachments:
        return False
    if not getattr(message.attachments[0], "is_voice_message", False):
        return False
    att = message.attachments[0]
    audio_bytes = await att.read()
    if not audio_bytes:
        return False
    from stankbot.services.voice_service import analyze as analyze_voice

    result = await analyze_voice(
        audio_bytes,
        altar,
        keywords=keywords,
        grit_bonus=0,  # no grit bonus during rebuild
    )
    return result.is_stank


def _reaction_matches(reaction: discord.Reaction, altar: Altar) -> bool:
    emoji = reaction.emoji
    if isinstance(emoji, str):
        return emoji_specs_match(
            altar.reaction_emoji_specs, event_id=None, event_name=emoji
        )
    return emoji_specs_match(
        altar.reaction_emoji_specs,
        event_id=getattr(emoji, "id", None),
        event_name=getattr(emoji, "name", None),
    )


async def _replay_altar(
    bot: StankBot,
    altar: Altar,
    guild: discord.Guild,
    progress: ProgressCallback,
) -> tuple[int, int, int, int]:
    """Replay one altar channel's entire history. Returns
    (messages, valid_stanks, chain_breaks, reactions).
    """
    channel = guild.get_channel(altar.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(altar.channel_id)  # type: ignore[assignment]
        except (discord.NotFound, discord.Forbidden):
            log.warning(
                "rebuild: altar %d channel %d unreachable; skipping",
                altar.id,
                altar.channel_id,
            )
            return 0, 0, 0, 0
    if not isinstance(channel, discord.TextChannel):
        log.warning("rebuild: altar %d channel is not a TextChannel", altar.id)
        return 0, 0, 0, 0

    msg_count = valid = breaks = reactions = 0

    # oldest_first=True so the chain is rebuilt in causal order.
    async for message in channel.history(limit=None, oldest_first=True):
        if message.author.bot:
            continue
        async with bot.db() as db:
            await guilds_repo.ensure(db, guild.id, guild.name)
            settings = SettingsService(db)
            session_svc = SessionService(db)
            chain_svc = ChainService(db, session_id_provider=session_svc)

            await session_svc.ensure_started(guild.id, when=message.created_at)
            config = await settings.effective_scoring(guild.id, altar)

            is_stank = _is_stank_message(message, altar)
            if not is_stank and altar.voice_keywords and not message.content.strip():
                try:
                    is_stank = await _is_stank_voice_rebuild(message, altar)
                except Exception:
                    log.warning(
                        "rebuild: voice detection failed for msg %d, treating as non-stank",
                        message.id,
                    )

            result = await chain_svc.process(
                StankInput(
                    guild_id=guild.id,
                    altar=altar,
                    message_id=message.id,
                    author_id=message.author.id,
                    author_display_name=message.author.display_name,
                    is_stank=is_stank,
                    created_at=message.created_at,
                ),
                config,
            )
            msg_count += 1
            if result.outcome.value == "valid_stank":
                valid += 1
            elif result.outcome.value == "chain_break":
                breaks += 1

            # Replay reactions for SP_REACTION awards (idempotent).
            for reaction in message.reactions:
                if not _reaction_matches(reaction, altar):
                    continue
                emoji_id = getattr(reaction.emoji, "id", None)
                sticker_key = emoji_id or -abs(
                    hash(getattr(reaction.emoji, "name", "") or str(reaction.emoji))
                ) % (10**12)
                async for user in reaction.users():
                    if user.bot:
                        continue
                    awarded = await chain_svc.award_reaction_bonus(
                        guild_id=guild.id,
                        altar=altar,
                        message_id=message.id,
                        user_id=user.id,
                        sticker_id=sticker_key,
                        config=config,
                        created_at=message.created_at,
                        user_display_name=(
                            getattr(user, "display_name", None)
                            or getattr(user, "name", None)
                        ),
                    )
                    if awarded:
                        reactions += 1

        if progress is not None and msg_count % 100 == 0:
            await progress(
                f"altar {altar.id}: scanned {msg_count} messages "
                f"({valid} stanks, {breaks} breaks)"
            )

    return msg_count, valid, breaks, reactions


async def rebuild(
    bot: StankBot,
    guild_id: int,
    *,
    progress: ProgressCallback = None,
) -> RebuildReport:
    """Wipe derived state for ``guild_id`` and replay all altar channels."""
    guild = bot.get_guild(guild_id)
    if guild is None:
        guild = await bot.fetch_guild(guild_id)
    if guild is None:
        raise RuntimeError(f"bot is not in guild {guild_id}")

    async with bot.db() as db:
        altar = await altars_repo.for_guild(db, guild_id)
        await wipe_guild_state(db, guild_id)

    if altar is None:
        log.warning("rebuild: guild %d has no altar configured", guild_id)
        return RebuildReport(
            guild_id=guild_id,
            altars_scanned=0,
            messages_scanned=0,
            valid_stanks=0,
            chain_breaks=0,
            reactions_awarded=0,
        )

    if progress is not None:
        await progress(f"replaying altar {altar.id} (<#{altar.channel_id}>)")
    msgs, valid, breaks, reactions = await _replay_altar(
        bot, altar, guild, progress
    )

    return RebuildReport(
        guild_id=guild_id,
        altars_scanned=1,
        messages_scanned=msgs,
        valid_stanks=valid,
        chain_breaks=breaks,
        reactions_awarded=reactions,
    )
