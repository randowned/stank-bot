"""Track whether altar reaction emoji is animated.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-20 01:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("altars") as batch:
        batch.add_column(
            sa.Column(
                "reaction_emoji_animated",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("altars") as batch:
        batch.drop_column("reaction_emoji_animated")
