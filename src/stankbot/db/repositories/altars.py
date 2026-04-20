"""Altar repository — one altar per guild.

The single altar is a (channel, sticker) binding the chain service
operates on. ``display_name`` (used for ``{stank_emoji}`` everywhere)
is derived from the reaction emoji on upsert, so boards + announcement
embeds automatically mirror whatever emoji the altar is configured to
react with.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import Altar


async def get(session: AsyncSession, altar_id: int) -> Altar | None:
    return await session.get(Altar, altar_id)


async def for_guild(
    session: AsyncSession, guild_id: int, *, enabled_only: bool = True
) -> Altar | None:
    """Return the guild's altar (or None)."""
    stmt = select(Altar).where(Altar.guild_id == guild_id)
    if enabled_only:
        stmt = stmt.where(Altar.enabled.is_(True))
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_for_guild(
    session: AsyncSession, guild_id: int, *, enabled_only: bool = True
) -> Sequence[Altar]:
    """Back-compat helper — returns the guild's altar as a 0/1-length list."""
    altar = await for_guild(session, guild_id, enabled_only=enabled_only)
    return [altar] if altar else []


async def primary(session: AsyncSession, guild_id: int) -> Altar | None:
    """Alias for :func:`for_guild` — kept for readability at call sites."""
    return await for_guild(session, guild_id)


def _stank_emoji_markup(
    reaction_emoji_id: int | None,
    reaction_emoji_name: str | None,
    reaction_emoji_animated: bool,
) -> str | None:
    """Build the ``{stank_emoji}`` markup from the altar's reaction emoji.

    - Custom emoji → ``<[a]:Name:id>`` (rendered inline in Discord).
    - Unicode glyph → the glyph itself.
    - Nothing configured → None (caller falls back to ``:Stank:``).
    """
    if reaction_emoji_id is not None and reaction_emoji_name:
        prefix = "a" if reaction_emoji_animated else ""
        return f"<{prefix}:{reaction_emoji_name}:{reaction_emoji_id}>"
    if reaction_emoji_name:
        return reaction_emoji_name
    return None


async def upsert(
    session: AsyncSession,
    *,
    guild_id: int,
    channel_id: int,
    sticker_name_pattern: str,
    reaction_emoji_id: int | None = None,
    reaction_emoji_name: str | None = None,
    reaction_emoji_animated: bool = False,
    sticker_id: int | None = None,
) -> tuple[Altar, bool]:
    """Create or update the guild's altar. Returns (altar, created).

    ``display_name`` is always re-derived from the reaction emoji so it
    stays in sync with whatever the admin just set.
    """
    display_name = _stank_emoji_markup(
        reaction_emoji_id, reaction_emoji_name, reaction_emoji_animated
    )

    altar = (
        await session.execute(select(Altar).where(Altar.guild_id == guild_id))
    ).scalar_one_or_none()
    if altar is None:
        altar = Altar(
            guild_id=guild_id,
            channel_id=channel_id,
            sticker_name_pattern=sticker_name_pattern,
            reaction_emoji_id=reaction_emoji_id,
            reaction_emoji_name=reaction_emoji_name,
            reaction_emoji_animated=reaction_emoji_animated,
            sticker_id=sticker_id,
            display_name=display_name,
        )
        session.add(altar)
        await session.flush()
        return altar, True

    altar.channel_id = channel_id
    altar.sticker_name_pattern = sticker_name_pattern
    altar.reaction_emoji_id = reaction_emoji_id
    altar.reaction_emoji_name = reaction_emoji_name
    altar.reaction_emoji_animated = reaction_emoji_animated
    if sticker_id is not None:
        altar.sticker_id = sticker_id
    altar.display_name = display_name
    await session.flush()
    return altar, False
