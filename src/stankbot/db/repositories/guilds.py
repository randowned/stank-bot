"""Guild repository — install-time registration."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import Guild


async def ensure(
    session: AsyncSession, guild_id: int, name: str | None = None
) -> Guild:
    """Idempotent upsert — called on guild join and lazily the first time
    we see a guild.
    """
    guild = await session.get(Guild, guild_id)
    if guild is None:
        guild = Guild(id=guild_id, name=name)
        session.add(guild)
        await session.flush()
    elif name and guild.name != name:
        guild.name = name
    return guild


async def get(session: AsyncSession, guild_id: int) -> Guild | None:
    return await session.get(Guild, guild_id)
