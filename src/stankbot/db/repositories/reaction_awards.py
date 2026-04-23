"""Reaction anti-cheat ledger.

A row in ``reaction_awards`` is a permanent claim: "we awarded SP for
(message_id, user_id, sticker_id)". Rows are NEVER deleted, even when the
user removes the reaction in Discord. Re-adding the reaction cannot
trigger a second award because the PK already exists.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import ReactionAward


async def try_claim(
    session: AsyncSession,
    *,
    guild_id: int,
    message_id: int,
    user_id: int,
    sticker_id: int,
    chain_id: int | None = None,
) -> bool:
    """Attempt to claim the reaction award. Returns ``True`` if this is
    the first claim (caller should emit the SP event); ``False`` if the
    claim already exists (caller must NOT re-award).
    """
    existing = await session.get(ReactionAward, (message_id, user_id, sticker_id))
    if existing is not None:
        return False
    session.add(
        ReactionAward(
            message_id=message_id,
            user_id=user_id,
            sticker_id=sticker_id,
            guild_id=guild_id,
            chain_id=chain_id,
        )
    )
    return True


async def count_for_chain(
    session: AsyncSession, *, guild_id: int, chain_id: int
) -> int:
    """Total reaction awards in a single chain."""
    stmt = select(func.count()).where(
        ReactionAward.guild_id == guild_id,
        ReactionAward.chain_id == chain_id,
    )
    result = await session.scalar(stmt)
    return int(result or 0)


async def count_per_user_for_chain(
    session: AsyncSession, *, guild_id: int, chain_id: int
) -> dict[int, int]:
    """Per-user reaction award counts in a chain, keyed by user_id."""
    stmt = (
        select(ReactionAward.user_id, func.count())
        .where(
            ReactionAward.guild_id == guild_id,
            ReactionAward.chain_id == chain_id,
        )
        .group_by(ReactionAward.user_id)
    )
    result = await session.execute(stmt)
    return {int(uid): int(n) for uid, n in result.all()}
