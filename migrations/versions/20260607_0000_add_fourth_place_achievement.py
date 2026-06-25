"""add fourth_place achievement + award_count on player_badges

Revision ID: f1e2d3c4b5a6
Revises: k9l0m1n2o3p4
Create Date: 2026-06-07 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f1e2d3c4b5a6"
down_revision: str | Sequence[str] | None = "k9l0m1n2o3p4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add award_count column to player_badges (default 1 for existing rows).
    with op.batch_alter_table("player_badges") as batch_op:
        batch_op.add_column(
            sa.Column(
                "award_count",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )

    # Insert the fourth_place achievement into the catalog.
    op.execute(
        "INSERT OR IGNORE INTO achievements (key, name, description, icon, "
        "rule_json, is_global, created_at) VALUES ("
        "'fourth_place', 'Fourth Place', "
        "'Finished 4th in SP earned during a session. Repeatable.', "
        "'4️⃣', '{\"impl\": \"code\", \"key\": \"fourth_place\"}', 1, "
        "datetime('now'))"
    )


def downgrade() -> None:
    with op.batch_alter_table("player_badges") as batch_op:
        batch_op.drop_column("award_count")

    op.execute("DELETE FROM achievements WHERE key = 'fourth_place'")
