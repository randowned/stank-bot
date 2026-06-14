"""Per-(guild, user) tissue tally for the ``/napkin`` fun command.

Standalone counter — not part of the event-sourced scoring log.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import TissueCount


async def increment(
    session: AsyncSession, *, guild_id: int, user_id: int
) -> int:
    """Bump the user's tally by one and return the new personal count."""
    row = await session.get(TissueCount, (guild_id, user_id))
    if row is None:
        session.add(TissueCount(guild_id=guild_id, user_id=user_id, count=1))
        return 1
    row.count += 1
    return row.count


async def get_count(
    session: AsyncSession, *, guild_id: int, user_id: int
) -> int:
    """Return the user's current tally (0 if they've never grabbed one)."""
    row = await session.get(TissueCount, (guild_id, user_id))
    return row.count if row else 0
