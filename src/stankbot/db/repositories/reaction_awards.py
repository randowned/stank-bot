"""Reaction anti-cheat ledger.

A row in ``reaction_awards`` is a permanent claim: "we awarded SP for
(message_id, user_id, sticker_id)". Rows are NEVER deleted, even when the
user removes the reaction in Discord. Re-adding the reaction cannot
trigger a second award because the PK already exists.
"""

from __future__ import annotations

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
