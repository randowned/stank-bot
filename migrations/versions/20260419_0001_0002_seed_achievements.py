"""Seed the global achievements catalog.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-19 00:01:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from stankbot.services.achievements import catalog_rows

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_achievements = sa.table(
    "achievements",
    sa.column("key", sa.String()),
    sa.column("name", sa.String()),
    sa.column("description", sa.String()),
    sa.column("icon", sa.String()),
    sa.column("rule_json", sa.JSON()),
    sa.column("is_global", sa.Boolean()),
)


def upgrade() -> None:
    rows = catalog_rows()
    if rows:
        op.bulk_insert(_achievements, rows)


def downgrade() -> None:
    keys = [r["key"] for r in catalog_rows()]
    if keys:
        op.execute(
            _achievements.delete().where(_achievements.c.key.in_(keys))
        )
