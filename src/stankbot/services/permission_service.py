"""Admin permission check — same rules for slash commands and the web.

Admin if any of:
    * the member is the global bot owner (``AppConfig.owner_id``), OR
    * the member has the Discord ``Manage Guild`` permission, OR
    * the member has any role listed in ``admin_roles`` for this guild, OR
    * the member is listed in ``admin_users`` for this guild.

Framework-agnostic — takes plain inputs (ids, role ids, a ``has_manage_guild``
flag) so the same function serves both the discord.py layer and FastAPI.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import AdminRole, AdminUser


@dataclass(slots=True)
class PermissionService:
    session: AsyncSession
    owner_id: int | None = None

    async def is_admin(
        self,
        guild_id: int,
        user_id: int,
        user_role_ids: Iterable[int],
        *,
        has_manage_guild: bool,
    ) -> bool:
        if self.owner_id is not None and user_id == self.owner_id:
            return True
        if has_manage_guild:
            return True
        user_grant = await self.session.get(AdminUser, (guild_id, user_id))
        if user_grant is not None:
            return True
        role_set = set(user_role_ids)
        if not role_set:
            return False
        stmt = select(AdminRole.role_id).where(AdminRole.guild_id == guild_id)
        admin_ids = set((await self.session.execute(stmt)).scalars().all())
        return bool(admin_ids & role_set)

    async def add_admin_user(self, guild_id: int, user_id: int) -> bool:
        existing = await self.session.get(AdminUser, (guild_id, user_id))
        if existing is not None:
            return False
        self.session.add(AdminUser(guild_id=guild_id, user_id=user_id))
        return True

    async def remove_admin_user(self, guild_id: int, user_id: int) -> bool:
        existing = await self.session.get(AdminUser, (guild_id, user_id))
        if existing is None:
            return False
        await self.session.delete(existing)
        return True

    async def list_admin_users(self, guild_id: int) -> list[int]:
        stmt = select(AdminUser.user_id).where(AdminUser.guild_id == guild_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def add_admin_role(self, guild_id: int, role_id: int) -> bool:
        """Return True if the role was added, False if it was already set."""
        existing = await self.session.get(AdminRole, (guild_id, role_id))
        if existing is not None:
            return False
        self.session.add(AdminRole(guild_id=guild_id, role_id=role_id))
        return True

    async def remove_admin_role(self, guild_id: int, role_id: int) -> bool:
        existing = await self.session.get(AdminRole, (guild_id, role_id))
        if existing is None:
            return False
        await self.session.delete(existing)
        return True

    async def list_admin_roles(self, guild_id: int) -> list[int]:
        stmt = select(AdminRole.role_id).where(AdminRole.guild_id == guild_id)
        return list((await self.session.execute(stmt)).scalars().all())
