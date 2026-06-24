"""Wiki repository — one per guild.

The single wiki is a (channel) binding the wiki service
operates on. 
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import Wiki


async def get(session: AsyncSession, wiki_id: int) -> Wiki | None:
    return await session.get(Wiki, wiki_id)


async def for_guild(
    session: AsyncSession, guild_id: int, *, enabled_only: bool = True
) -> Wiki | None:
    """Return the guild's wiki (or None)."""
    stmt = select(Wiki).where(Wiki.guild_id == guild_id)
    if enabled_only:
        stmt = stmt.where(Wiki.enabled.is_(True))
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_for_guild(
    session: AsyncSession, guild_id: int, *, enabled_only: bool = True
) -> Sequence[Wiki]:
    """Back-compat helper — returns the guild's wiki as a 0/1-length list."""
    wiki = await for_guild(session, guild_id, enabled_only=enabled_only)
    return [wiki] if wiki else []


async def primary(session: AsyncSession, guild_id: int) -> Wiki | None:
    """Alias for :func:`for_guild` — kept for readability at call sites."""
    return await for_guild(session, guild_id)



async def upsert(
    session: AsyncSession,
    *,
    guild_id: int,
    wiki_channel_id: int,
    wiki_watch_channel_ids: list[int] | None = None,
) -> tuple[Wiki, bool]:
    """Create or update the guild's wiki. Returns (wiki, created).
    """
    wiki = (
        await session.execute(select(Wiki).where(Wiki.guild_id == guild_id))
    ).scalar_one_or_none()
    if wiki is None:
        wiki = Wiki(
            guild_id=guild_id,
            wiki_channel_id=wiki_channel_id,
            wiki_watch_channel_ids=wiki_watch_channel_ids,
        )
        session.add(wiki)
        await session.flush()
        return wiki, True

    wiki.wiki_channel_id = wiki_channel_id
    wiki.wiki_watch_channel_ids = wiki_watch_channel_ids
    await session.flush()
    return wiki, False
