"""repair altar reaction_emoji_name corrupted by the dashboard

The web dashboard used to store the full ``<:name:id>`` tag in
``altars.reaction_emoji_name`` (the slash command correctly stored the bare
name). That made ``display_name`` — used for ``{stank_emoji}`` — double-wrapped
garbage and broke the auto-react fallback. This data migration extracts the
bare name and recomputes ``display_name`` for any affected rows. Idempotent:
rows that already hold a bare name (or a unicode glyph) are left untouched.

Revision ID: i7j8k9l0m1n2
Revises: h6i7j8k9l0m1
Create Date: 2026-06-09 00:00:00.000000+00:00
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "i7j8k9l0m1n2"
down_revision: str | Sequence[str] | None = "h6i7j8k9l0m1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Mirrors stankbot.utils.emoji._CUSTOM_EMOJI_RE — inlined so the migration
# stays a frozen snapshot independent of app code.
_TAG_RE = re.compile(r"<(a?):([A-Za-z0-9_~]+):(\d+)>")


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        text(
            "SELECT id, reaction_emoji_id, reaction_emoji_name "
            "FROM altars WHERE reaction_emoji_id IS NOT NULL"
        )
    ).mappings().all()

    for row in rows:
        name = (row["reaction_emoji_name"] or "").strip()
        m = _TAG_RE.fullmatch(name)
        if not m:
            continue  # already a bare name (or unparseable) — leave it
        animated = m.group(1) == "a"
        bare = m.group(2)
        emoji_id = row["reaction_emoji_id"]
        display = f"<{'a' if animated else ''}:{bare}:{emoji_id}>"
        conn.execute(
            text(
                "UPDATE altars SET reaction_emoji_name = :name, "
                "reaction_emoji_animated = :animated, display_name = :display "
                "WHERE id = :id"
            ),
            {"name": bare, "animated": animated, "display": display, "id": row["id"]},
        )


def downgrade() -> None:
    # Data-only repair — re-corrupting the names on downgrade would serve no
    # purpose, so this is intentionally a no-op.
    pass
