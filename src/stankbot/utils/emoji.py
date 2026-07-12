"""Pure parsing for Discord reaction-emoji args (no discord.py import).

Shared by the admin slash command and the web dashboard so both store the
altar reaction emoji identically — ``reaction_emoji_name`` holds the *bare*
name (``maphra_horns``), never the full ``<:maphra_horns:123>`` tag. The
full markup is re-derived as ``Altar.display_name`` on upsert.
"""

from __future__ import annotations

from typing import Any

import re

_CUSTOM_EMOJI_RE = re.compile(r"<(a?):([A-Za-z0-9_~]+):(\d+)>")


def parse_reaction_emoji(raw: str | None) -> tuple[int | None, str | None, bool] | None:
    """Parse a reaction-emoji arg into ``(id, name, animated)``.

    - ``<:Name:123>``  -> ``(123, "Name", False)``
    - ``<a:Name:123>`` -> ``(123, "Name", True)``
    - unicode glyph ``"🔥"`` -> ``(None, "🔥", False)``
    - empty / unparseable (e.g. a literal ``:name:``) -> ``None``
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    m = _CUSTOM_EMOJI_RE.fullmatch(raw)
    if m:
        return int(m.group(3)), m.group(2), m.group(1) == "a"
    if len(raw) <= 8 and not raw.startswith(":"):
        return None, raw, False
    return None


def parse_reaction_emojis(raw: str | None) -> list[dict[str, Any]]:
    """Parse a comma-separated emoji arg into a list of ``{id, name, animated}``.

    Unparseable entries are skipped; duplicates (same id, or same glyph name)
    are dropped, preserving order. Custom-emoji tags and unicode glyphs never
    contain commas, so splitting on ``,`` is safe.
    """
    specs: list[dict[str, Any]] = []
    seen: set[tuple[int | None, str | None]] = set()
    for part in (raw or "").split(","):
        parsed = parse_reaction_emoji(part)
        if parsed is None:
            continue
        emoji_id, name, animated = parsed
        key = (emoji_id, None if emoji_id is not None else name)
        if key in seen:
            continue
        seen.add(key)
        specs.append({"id": emoji_id, "name": name, "animated": animated})
    return specs


def emoji_to_markup(spec: dict[str, Any]) -> str:
    """Render one ``{id, name, animated}`` spec as Discord markup / glyph."""
    emoji_id = spec.get("id")
    name = spec.get("name") or ""
    if emoji_id is not None and name:
        prefix = "a" if spec.get("animated") else ""
        return f"<{prefix}:{name}:{emoji_id}>"
    return name


def emoji_specs_match(
    specs: list[dict[str, Any]], *, event_id: int | None, event_name: str | None
) -> bool:
    """True if an incoming reaction (event_id/event_name) matches any spec."""
    for spec in specs:
        spec_id = spec.get("id")
        if spec_id is not None:
            if event_id is not None and event_id == spec_id:
                return True
        elif spec.get("name") and event_name == spec.get("name"):
            return True
    return False
