"""Board renderer — turns raw state + a template into a ``discord.Embed``.

Separates two concerns:
    1. Building the variable map (player rows, chain state, records, times).
    2. Handing that map to ``template_engine.render_embed`` with the
       per-guild template dict.

Everything this module consumes is a plain Python value — it never touches
Discord objects beyond the final ``Embed`` it returns. This lets the web
dashboard's live-preview reuse the same function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import discord

from stankbot.services.template_engine import RenderContext, render_embed
from stankbot.utils.time_utils import humanize_duration

# Discord field-value hard limit.
_FIELD_VALUE_LIMIT = 1024


@dataclass(slots=True)
class PlayerRow:
    user_id: int
    display_name: str
    earned_sp: int
    punishments: int

    @property
    def net(self) -> int:
        return self.earned_sp - self.punishments


@dataclass(slots=True)
class BoardState:
    """Everything needed to render the board embed.

    Built by the cog layer (or the dashboard route) from repository queries,
    then passed to ``render_board_embed``. All counts are plain ints; no
    ORM rows cross this boundary.
    """

    guild_name: str
    stank_emoji: str
    altar_sticker_url: str
    current: int
    current_unique: int
    record: int
    record_unique: int
    alltime_record: int
    alltime_record_unique: int
    next_reset_at: datetime | None
    now: datetime
    stank_rows_limit: int
    rankings: list[PlayerRow]
    chain_starter: PlayerRow | None
    chainbreaker: PlayerRow | None
    # Free-form extras the caller can inject (e.g. session_number).
    extras: dict[str, Any] = field(default_factory=dict)


def _format_rankings_table(rows: list[PlayerRow], limit: int, *, dashboard_url: str | None = None) -> str:
    """Render the top-N players as a Discord markdown block.

    Truncates to fit Discord's 1024-char field-value limit; overflow line
    links out to the dashboard for the full board.
    """
    if not rows:
        return "_No records yet._"
    medals = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}
    lines: list[str] = []
    for i, row in enumerate(rows[:limit], start=1):
        medal = medals.get(i, "\u3000")
        lines.append(
            f"`{i}.` {medal} **{row.display_name}** \u2014 {row.net} SP"
        )
    text = "\n".join(lines)
    if len(text) > _FIELD_VALUE_LIMIT:
        # Drop trailing lines until we fit, then append the overflow notice.
        notice = (
            "\n\u2026 see dashboard for full board"
            + (f": {dashboard_url}" if dashboard_url else "")
        )
        budget = _FIELD_VALUE_LIMIT - len(notice)
        trimmed: list[str] = []
        running = 0
        for line in lines:
            if running + len(line) + 1 > budget:
                break
            trimmed.append(line)
            running += len(line) + 1
        text = "\n".join(trimmed) + notice
    return text


def build_context(
    state: BoardState, *, dashboard_url: str | None = None
) -> RenderContext:
    """Flatten ``BoardState`` into the ``{snake_case}`` variable map the
    template engine consumes.
    """
    reset_in = (
        humanize_duration((state.next_reset_at - state.now).total_seconds())
        if state.next_reset_at is not None
        else "\u2014"
    )
    starter_name = state.chain_starter.display_name if state.chain_starter else "—"
    starter_sp = state.chain_starter.net if state.chain_starter else 0
    breaker_name = state.chainbreaker.display_name if state.chainbreaker else "None"
    breaker_pp = state.chainbreaker.punishments if state.chainbreaker else 0
    breaker_sp = state.chainbreaker.earned_sp if state.chainbreaker else 0

    variables: dict[str, Any] = {
        "guild_name": state.guild_name,
        "stank_emoji": state.stank_emoji,
        "altar_sticker_url": state.altar_sticker_url,
        "current": state.current,
        "current_unique": state.current_unique,
        "record": state.record,
        "record_unique": state.record_unique,
        "alltime_record": state.alltime_record,
        "alltime_record_unique": state.alltime_record_unique,
        "next_reset_in": reset_in,
        "stank_rows_limit": state.stank_rows_limit,
        "stank_rankings_table": _format_rankings_table(
            state.rankings, state.stank_rows_limit, dashboard_url=dashboard_url
        ),
        "chain_starter_name": starter_name,
        "chain_starter_sp": starter_sp,
        "chainbreaker_name": breaker_name,
        "chainbreaker_punishments": breaker_pp,
        "chainbreaker_sp": breaker_sp,
        "board_url": dashboard_url or "",
    }
    variables.update(state.extras)
    return RenderContext(variables=variables)


def render_board_embed(
    template: dict[str, Any],
    state: BoardState,
    *,
    dashboard_url: str | None = None,
) -> discord.Embed:
    ctx = build_context(state, dashboard_url=dashboard_url)
    return render_embed(template, ctx)
