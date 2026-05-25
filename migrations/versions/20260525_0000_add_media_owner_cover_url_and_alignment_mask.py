"""add cover_url to media_owners and alignment_mask to media_owner_snapshots

Revision ID: g5h6i7j8k9l0
Revises: f4g5h6i7j8k9
Create Date: 2026-05-25 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "g5h6i7j8k9l0"
down_revision: str | Sequence[str] | None = "f4g5h6i7j8k9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "media_owners",
        sa.Column("cover_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "media_owner_snapshots",
        sa.Column("alignment_mask", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_owner_snapshots_id_key_align_time",
        "media_owner_snapshots",
        ["media_owner_id", "metric_key", "alignment_mask", "fetched_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_owner_snapshots_id_key_align_time", table_name="media_owner_snapshots")
    op.drop_column("media_owner_snapshots", "alignment_mask")
    op.drop_column("media_owners", "cover_url")
