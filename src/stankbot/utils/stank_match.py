"""Pure sticker-name matching for altars (no discord.py import).

The altar ``sticker_name_pattern`` may hold several comma-separated patterns.
A sticker counts as a stank when ANY pattern is a (case-insensitive) substring
of its name. Shared by the live listener and the rebuild service so the two
can never drift — see ``chain_listener`` / ``rebuild_service``.
"""

from __future__ import annotations

from collections.abc import Iterable


def split_patterns(raw: str | None) -> list[str]:
    """Split a comma-separated pattern string into trimmed, lowercased tokens."""
    return [p.strip().lower() for p in (raw or "").split(",") if p.strip()]


def sticker_name_matches(
    raw_pattern: str | None, sticker_names: Iterable[str | None]
) -> bool:
    """True if any configured pattern is a substring of any sticker name."""
    patterns = split_patterns(raw_pattern)
    if not patterns:
        return False
    names = [(n or "").lower() for n in sticker_names]
    return any(p in n for p in patterns for n in names)


def sticker_id_matches(
    allowed_ids: list[int] | None, sticker_ids: Iterable[int]
) -> bool:
    """True if any message sticker ID is in the allowed set."""
    if not allowed_ids:
        return False
    allowed = set(allowed_ids)
    return any(sid in allowed for sid in sticker_ids)
