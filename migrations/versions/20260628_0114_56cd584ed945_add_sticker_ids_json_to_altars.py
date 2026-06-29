"""add sticker_ids JSON to altars

Revision ID: 56cd584ed945
Revises: f1e2d3c4b5a6
Create Date: 2026-06-28 01:14:13.203703+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '56cd584ed945'
down_revision: str | Sequence[str] | None = 'f1e2d3c4b5a6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('altars', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sticker_ids', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('altars', schema=None) as batch_op:
        batch_op.drop_column('sticker_ids')
