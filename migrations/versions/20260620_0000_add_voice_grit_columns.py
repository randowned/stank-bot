"""add voice/grit columns to altars

Adds three columns to the altars table for optional voice message
stank detection and the "grit" easter egg bonus:

- ``voice_keywords`` (nullable JSON list of strings) — phrases that
  count as a stank when spoken in a voice message.
- ``voice_grit_bonus`` (int, default 0) — bonus SP awarded when the
  delivery exceeds the grit threshold.
- ``voice_grit_threshold`` (float, default 0.6) — minimum grit score
  (0.0–1.0) to award the bonus.

Revision ID: a1b2c3d4e5f6
Revises: 56cd584ed945
Create Date: 2026-06-20 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "5a40b876294cf9"
down_revision: str | Sequence[str] | None = "56cd584ed945"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("altars") as batch_op:
        batch_op.add_column(sa.Column("voice_keywords", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "voice_grit_bonus",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "voice_grit_threshold",
                sa.Float(),
                nullable=False,
                server_default=sa.text("0.6"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("altars") as batch_op:
        batch_op.drop_column("voice_grit_threshold")
        batch_op.drop_column("voice_grit_bonus")
        batch_op.drop_column("voice_keywords")
