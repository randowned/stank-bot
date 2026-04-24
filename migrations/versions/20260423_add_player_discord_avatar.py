"""add_player_discord_avatar

Revision ID: b1a2c3d4e5f6
Revises: a99d29835488
Create Date: 2026-04-23 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'b1a2c3d4e5f6'
down_revision: str | Sequence[str] | None = 'a99d29835488'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('players', sa.Column('discord_avatar', sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column('players', 'discord_avatar')
