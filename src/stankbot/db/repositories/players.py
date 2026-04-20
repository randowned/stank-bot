"""Player repository — identity + last-seen tracking.

Thin module, not a heavyweight class. Callers pass an ``AsyncSession``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import Player


async def get_or_create(
    session: AsyncSession,
    guild_id: int,
    user_id: int,
    display_name: str | None = None,
) -> Player:
    player = await session.get(Player, (guild_id, user_id))
    if player is None:
        player = Player(
            guild_id=guild_id,
            user_id=user_id,
            display_name=display_name,
        )
        session.add(player)
        await session.flush()
    elif display_name and display_name != player.display_name:
        player.display_name = display_name
    return player


async def touch_last_seen(
    session: AsyncSession,
    guild_id: int,
    user_id: int,
    *,
    when: datetime | None = None,
) -> None:
    player = await session.get(Player, (guild_id, user_id))
    if player is None:
        return
    player.last_seen_at = when or datetime.now(tz=UTC)
