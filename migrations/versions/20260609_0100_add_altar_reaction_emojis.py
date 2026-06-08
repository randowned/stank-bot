"""add altars.reaction_emojis and widen sticker_name_pattern

Supports multiple accepted reaction emojis (JSON list, primary first) and
multiple comma-separated sticker patterns (wider column).

Revision ID: j8k9l0m1n2o3
Revises: i7j8k9l0m1n2
Create Date: 2026-06-09 01:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "j8k9l0m1n2o3"
down_revision: str | Sequence[str] | None = "i7j8k9l0m1n2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("altars") as batch:
        batch.add_column(sa.Column("reaction_emojis", sa.JSON(), nullable=True))
        batch.alter_column(
            "sticker_name_pattern",
            existing_type=sa.String(length=120),
            type_=sa.String(length=255),
            existing_nullable=False,
            existing_server_default="stank",
        )


def downgrade() -> None:
    with op.batch_alter_table("altars") as batch:
        batch.alter_column(
            "sticker_name_pattern",
            existing_type=sa.String(length=255),
            type_=sa.String(length=120),
            existing_nullable=False,
            existing_server_default="stank",
        )
        batch.drop_column("reaction_emojis")
