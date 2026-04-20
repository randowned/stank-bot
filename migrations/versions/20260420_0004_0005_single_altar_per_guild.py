"""Enforce a single altar per guild.

Collapses any duplicate altars for the same guild_id down to the
lowest-id row, retargets dependent foreign keys, deletes the extras,
then swaps the (guild_id, channel_id) unique constraint for one on
guild_id alone.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-20 05:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Pick the surviving altar (lowest id) per guild.
    survivors = conn.execute(
        sa.text(
            "SELECT guild_id, MIN(id) AS keep_id FROM altars GROUP BY guild_id"
        )
    ).fetchall()
    for guild_id, keep_id in survivors:
        dup_ids = [
            row[0]
            for row in conn.execute(
                sa.text(
                    "SELECT id FROM altars WHERE guild_id = :gid AND id != :kid"
                ),
                {"gid": guild_id, "kid": keep_id},
            ).fetchall()
        ]
        if not dup_ids:
            continue
        # Retarget dependents so deletes don't cascade away historical rows.
        for table in ("chains", "events", "records", "cooldowns"):
            conn.execute(
                sa.text(
                    f"UPDATE {table} SET altar_id = :kid "
                    f"WHERE altar_id IN ({','.join(str(i) for i in dup_ids)})"
                ),
                {"kid": keep_id},
            )
        conn.execute(
            sa.text(
                f"DELETE FROM altars WHERE id IN "
                f"({','.join(str(i) for i in dup_ids)})"
            )
        )

    with op.batch_alter_table("altars") as batch:
        batch.drop_constraint("uq_altar_channel", type_="unique")
        batch.create_unique_constraint("uq_altar_guild", ["guild_id"])


def downgrade() -> None:
    with op.batch_alter_table("altars") as batch:
        batch.drop_constraint("uq_altar_guild", type_="unique")
        batch.create_unique_constraint(
            "uq_altar_channel", ["guild_id", "channel_id"]
        )
