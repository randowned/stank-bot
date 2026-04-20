"""Audit log repository — every admin mutation gets a row.

Appends are cheap; reads are by guild ordered newest-first and used by
the admin cog's log-tail + the dashboard's audit page.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import AuditLog


async def append(
    session: AsyncSession,
    *,
    guild_id: int,
    actor_id: int,
    action: str,
    payload: dict[str, Any] | list[Any] | None = None,
) -> AuditLog:
    row = AuditLog(
        guild_id=guild_id,
        actor_id=actor_id,
        action=action,
        payload_json=payload,
    )
    session.add(row)
    await session.flush()
    return row


async def recent(
    session: AsyncSession, guild_id: int, *, limit: int = 50
) -> Sequence[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.guild_id == guild_id)
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )
    return (await session.execute(stmt)).scalars().all()
