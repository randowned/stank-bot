"""Player repository — identity + last-seen tracking.

Thin module, not a heavyweight class. Callers pass an ``AsyncSession``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import Player


async def get_or_create(
    session: AsyncSession,
    guild_id: int,
    user_id: int,
    display_name: str | None = None,
    discord_avatar: str | None = None,
) -> Player:
    player = await session.get(Player, (guild_id, user_id))
    if player is None:
        player = Player(
            guild_id=guild_id,
            user_id=user_id,
            display_name=display_name or str(user_id),
            discord_avatar=discord_avatar,
        )
        session.add(player)
        await session.flush()
    else:
        if display_name and display_name != player.display_name:
            player.display_name = display_name
        elif not player.display_name:
            player.display_name = str(user_id)
        if discord_avatar and discord_avatar != player.discord_avatar:
            player.discord_avatar = discord_avatar
    return player


async def get(session: AsyncSession, guild_id: int, user_id: int) -> Player | None:
    """Read-only fetch that guarantees a non-None ``display_name``.

    If the row exists with a missing name, the in-memory attribute is
    filled with ``str(user_id)`` so callers never have to re-apply the
    fallback themselves.
    """
    player = await session.get(Player, (guild_id, user_id))
    if player is not None and not player.display_name:
        player.display_name = str(user_id)
    return player


async def display_names(
    session: AsyncSession, guild_id: int, user_ids: Iterable[int]
) -> dict[int, str]:
    """Return ``{user_id: display_name}`` for the given users."""
    ids = [int(u) for u in user_ids if u is not None]
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(Player.user_id, Player.display_name).where(
                Player.guild_id == guild_id, Player.user_id.in_(ids)
            )
        )
    ).all()
    return {int(uid): (name or str(uid)) for uid, name in rows}


async def display_names_and_avatars(
    session: AsyncSession, guild_id: int, user_ids: Iterable[int]
) -> dict[int, tuple[str, str | None]]:
    """Return ``{user_id: (display_name, discord_avatar)}`` for the given users."""
    ids = [int(u) for u in user_ids if u is not None]
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(Player.user_id, Player.display_name, Player.discord_avatar).where(
                Player.guild_id == guild_id, Player.user_id.in_(ids)
            )
        )
    ).all()
    return {int(uid): (name or str(uid), avatar) for uid, name, avatar in rows}


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
