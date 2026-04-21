"""make_admin_users_global

Revision ID: a99d29835488
Revises: 0007
Create Date: 2026-04-21 15:13:48.309062+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'a99d29835488'
down_revision: str | Sequence[str] | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql(
        "CREATE TABLE admin_users_new AS SELECT guild_id, user_id, added_at FROM admin_users"
    )
    conn.exec_driver_sql("DROP TABLE admin_users")
    conn.exec_driver_sql(
        "CREATE TABLE admin_users ("
        "guild_id INTEGER NOT NULL DEFAULT 0, "
        "user_id INTEGER NOT NULL, "
        "added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
        "PRIMARY KEY (guild_id, user_id)"
        ")"
    )
    conn.exec_driver_sql(
        "INSERT INTO admin_users (guild_id, user_id, added_at) "
        "SELECT guild_id, user_id, added_at FROM admin_users_new"
    )
    conn.exec_driver_sql("DROP TABLE admin_users_new")


def downgrade() -> None:
    pass