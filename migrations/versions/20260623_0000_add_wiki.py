"""add wiki table

Revision ID: lkjasdjklasd
Revises: k9l0m1n2o3p4
Create Date: 2026-06-23 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "lkjasdjklasd"
down_revision: str | Sequence[str] | None = "k9l0m1n2o3p4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wiki",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            sa.ForeignKey("guilds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("wiki_channel_id", sa.BigInteger(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("guild_id", "wiki_channel_id", name="uq_wiki_double"),
    )
    op.create_index("ix_wiki_guild_enabled", "wiki", ["guild_id", "enabled"])


def downgrade() -> None:
    op.drop_table("wiki")
