"""seed voice stank achievements

Adds two new achievements to the global achievements catalog:

- ``voice_stank`` (Vocal Stank) — submitted a stank via voice message
- ``gritty_voice`` (Grit Master) — delivered a gritty voice stank with bonus SP

Revision ID: b3c4d5e6f7g8
Revises: 5a40b876294cf9
Create Date: 2026-07-14 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b3c4d5e6f7g8"
down_revision: str | Sequence[str] | None = "5a40b876294cf9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACHIEVEMENTS = sa.table(
    "achievements",
    sa.column("key", sa.String()),
    sa.column("name", sa.String()),
    sa.column("description", sa.String()),
    sa.column("icon", sa.String()),
    sa.column("rule_json", sa.JSON()),
    sa.column("is_global", sa.Boolean()),
)


def upgrade() -> None:
    op.execute(
        "INSERT OR IGNORE INTO achievements (key, name, description, icon, "
        "rule_json, is_global, created_at) VALUES ("
        "'voice_stank', 'Vocal Stank', "
        "'Submitted a stank via voice message.', "
        "'🎤', '{\"impl\": \"code\", \"key\": \"voice_stank\"}', 1, "
        "datetime('now'))"
    )
    op.execute(
        "INSERT OR IGNORE INTO achievements (key, name, description, icon, "
        "rule_json, is_global, created_at) VALUES ("
        "'gritty_voice', 'Grit Master', "
        "'Delivered a gritty voice stank with bonus SP.', "
        "'🔥', '{\"impl\": \"code\", \"key\": \"gritty_voice\"}', 1, "
        "datetime('now'))"
    )


def downgrade() -> None:
    op.execute(
        _ACHIEVEMENTS.delete().where(
            _ACHIEVEMENTS.c.key.in_(["voice_stank", "gritty_voice"])
        )
    )
