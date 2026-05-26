"""add partial unique index on chains to prevent duplicate active chains

Revision ID: h6i7j8k9l0m1
Revises: g5h6i7j8k9l0
Create Date: 2026-05-26 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "h6i7j8k9l0m1"
down_revision: str | Sequence[str] | None = "g5h6i7j8k9l0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_chains_guild_altar_active",
        "chains",
        ["guild_id", "altar_id"],
        unique=True,
        postgresql_where="broken_at IS NULL",
        sqlite_where="broken_at IS NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_chains_guild_altar_active", table_name="chains")
