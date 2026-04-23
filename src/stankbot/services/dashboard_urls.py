"""Dashboard URL resolver shared by bot embeds and web redirects.

The bot's embeds reference dashboard URLs (board, player profile, chain
detail). During the legacy → v2 SvelteKit migration, both dashboards are
mounted in the same process; this helper picks which family of URLs to
emit based on ``AppConfig.dashboard_frontend``.

Pure function. No FastAPI / discord.py imports — safe to call from cogs,
template rendering, and services alike.
"""

from __future__ import annotations

from typing import Literal

Kind = Literal[
    "board",
    "player",
    "chain",
    "session",
    "admin",
    "admin_settings",
    "admin_altar",
    "admin_roles",
    "admin_audit",
    "admin_announcements",
    "admin_maintenance",
    "admin_config",
    "admin_templates",
    "admin_guild_select",
]


def dashboard_url_for(
    kind: Kind,
    *,
    base_url: str,
    frontend: str = "legacy",
    user_id: int | None = None,
    chain_id: int | None = None,
    session_id: int | None = None,
) -> str:
    """Build an absolute URL to a dashboard page.

    ``base_url`` is the origin (e.g. ``https://bot.example.com``).
    ``frontend`` is ``"v2"`` or ``"legacy"`` — any other value falls back
    to ``legacy`` to avoid breaking embeds on a typo'd env var.
    """
    base = base_url.rstrip("/")
    v2 = frontend == "v2"

    if kind == "board":
        return f"{base}/v2/" if v2 else f"{base}/"
    if kind == "player":
        if user_id is None:
            raise ValueError("player URL requires user_id")
        return f"{base}/v2/player/{user_id}" if v2 else f"{base}/player/{user_id}"
    if kind == "chain":
        if chain_id is None:
            raise ValueError("chain URL requires chain_id")
        return (
            f"{base}/v2/chain/{chain_id}"
            if v2
            else f"{base}/history/chain/{chain_id}"
        )
    if kind == "session":
        if session_id is None:
            raise ValueError("session URL requires session_id")
        return (
            f"{base}/v2/session/{session_id}"
            if v2
            else f"{base}/history/session/{session_id}"
        )
    if kind == "admin":
        return f"{base}/v2/admin" if v2 else f"{base}/admin"
    if kind == "admin_settings":
        return f"{base}/v2/admin/settings" if v2 else f"{base}/admin/settings"
    if kind == "admin_altar":
        return f"{base}/v2/admin/altar" if v2 else f"{base}/admin/altar"
    if kind == "admin_roles":
        return f"{base}/v2/admin/roles" if v2 else f"{base}/admin/roles"
    if kind == "admin_audit":
        return f"{base}/v2/admin/audit" if v2 else f"{base}/admin/audit"
    if kind == "admin_announcements":
        return (
            f"{base}/v2/admin/announcements"
            if v2
            else f"{base}/admin/announcements"
        )
    if kind == "admin_maintenance":
        return (
            f"{base}/v2/admin/maintenance"
            if v2
            else f"{base}/admin/maintenance"
        )
    if kind == "admin_config":
        return f"{base}/v2/admin/config" if v2 else f"{base}/admin/config"
    if kind == "admin_templates":
        return f"{base}/v2/admin/templates" if v2 else f"{base}/admin/templates"
    if kind == "admin_guild_select":
        # Guild-switch: v2 uses POST /v2/api/admin/guild, legacy uses the
        # HTML GET redirect. Callers that need a plain link (e.g. fallback
        # navigation) get the legacy form either way so the browser can
        # follow it without JS.
        return f"{base}/admin/guilds/select"

    raise ValueError(f"unknown dashboard URL kind: {kind!r}")
