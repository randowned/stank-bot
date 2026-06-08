"""Pure parsing for Discord reaction-emoji args (no discord.py import).

Shared by the admin slash command and the web dashboard so both store the
altar reaction emoji identically — ``reaction_emoji_name`` holds the *bare*
name (``maphra_horns``), never the full ``<:maphra_horns:123>`` tag. The
full markup is re-derived as ``Altar.display_name`` on upsert.
"""

from __future__ import annotations

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
