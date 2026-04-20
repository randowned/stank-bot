"""Altar name-based sticker matching + reaction emoji; drop command channels.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-20 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("altars") as batch:
        batch.drop_constraint("uq_altar_triple", type_="unique")
        batch.alter_column("sticker_id", existing_type=sa.BigInteger(), nullable=True)
        batch.add_column(
            sa.Column(
                "sticker_name_pattern",
                sa.String(length=120),
                nullable=False,
                server_default="stank",
            )
        )
        batch.add_column(
            sa.Column("reaction_emoji_id", sa.BigInteger(), nullable=True)
        )
        batch.add_column(
            sa.Column("reaction_emoji_name", sa.String(length=120), nullable=True)
        )
        batch.create_unique_constraint(
            "uq_altar_channel", ["guild_id", "channel_id"]
        )

    op.execute(
        "DELETE FROM channel_bindings WHERE purpose = 'commands'"
    )


def downgrade() -> None:
    with op.batch_alter_table("altars") as batch:
        batch.drop_constraint("uq_altar_channel", type_="unique")
        batch.drop_column("reaction_emoji_name")
        batch.drop_column("reaction_emoji_id")
        batch.drop_column("sticker_name_pattern")
        batch.alter_column("sticker_id", existing_type=sa.BigInteger(), nullable=False)
        batch.create_unique_constraint(
            "uq_altar_triple", ["guild_id", "channel_id", "sticker_id"]
        )
