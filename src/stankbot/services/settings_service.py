"""Per-guild settings — typed get/set over the ``guild_settings`` table.

All runtime-tunable knobs (scoring overrides, cooldowns, reset hours,
template bodies, feature toggles) live here. Env-level secrets stay in
``AppConfig`` and are NOT routed through this service.

Contract:
    * ``Keys`` is the canonical list of setting keys — adding a new key
      means adding a member here plus a default in ``DEFAULTS``.
    * ``get`` returns the per-guild value if set, else the default.
    * ``set`` validates (JSON-serializable, snake_case-safe for templates)
      and writes; caller is responsible for wrapping in a session scope.
    * Per-altar overrides are resolved separately — see
      ``effective_scoring(altar, guild_settings)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import Altar, GuildSetting
from stankbot.services.scoring_service import (
    DEFAULT_PP_BREAK_BASE,
    DEFAULT_PP_BREAK_PER_STANK,
    DEFAULT_RESTANK_COOLDOWN_SECONDS,
    DEFAULT_SP_FINISH_BONUS,
    DEFAULT_SP_FLAT,
    DEFAULT_SP_POSITION_BONUS,
    DEFAULT_SP_REACTION,
    DEFAULT_SP_STARTER_BONUS,
    ScoringConfig,
)


class Keys(StrEnum):
    # Scoring
    SP_FLAT = "sp_flat"
    SP_POSITION_BONUS = "sp_position_bonus"
    SP_STARTER_BONUS = "sp_starter_bonus"
    SP_FINISH_BONUS = "sp_finish_bonus"
    SP_REACTION = "sp_reaction"
    PP_BREAK_BASE = "pp_break_base"
    PP_BREAK_PER_STANK = "pp_break_per_stank"
    RESTANK_COOLDOWN_SECONDS = "restank_cooldown_seconds"
    # Sessions
    RESET_HOURS_UTC = "reset_hours_utc"
    RESET_WARNING_MINUTES = "reset_warning_minutes"
    CHAIN_CONTINUES_ACROSS_SESSIONS = "chain_continues_across_sessions"
    # Display
    STANK_RANKING_ROWS = "stank_ranking_rows"
    # Templates (full embed descriptors — code-managed, not user-editable)
    BOARD_EMBED = "board_embed"
    RECORD_EMBED = "record_embed"
    CHAIN_BREAK_EMBED = "chain_break_embed"
    NEW_SESSION_EMBED = "new_session_embed"
    COOLDOWN_EMBED = "cooldown_embed"
    POINTS_EMBED = "points_embed"
    # Features
    ENABLE_REACTION_BONUS = "enable_reaction_bonus"
    MAINTENANCE_MODE = "maintenance_mode"


DEFAULTS: dict[str, Any] = {
    Keys.SP_FLAT: DEFAULT_SP_FLAT,
    Keys.SP_POSITION_BONUS: DEFAULT_SP_POSITION_BONUS,
    Keys.SP_STARTER_BONUS: DEFAULT_SP_STARTER_BONUS,
    Keys.SP_FINISH_BONUS: DEFAULT_SP_FINISH_BONUS,
    Keys.SP_REACTION: DEFAULT_SP_REACTION,
    Keys.PP_BREAK_BASE: DEFAULT_PP_BREAK_BASE,
    Keys.PP_BREAK_PER_STANK: DEFAULT_PP_BREAK_PER_STANK,
    Keys.RESTANK_COOLDOWN_SECONDS: DEFAULT_RESTANK_COOLDOWN_SECONDS,
    Keys.RESET_HOURS_UTC: [7, 15, 23],
    Keys.RESET_WARNING_MINUTES: [30, 5],
    Keys.CHAIN_CONTINUES_ACROSS_SESSIONS: True,
    Keys.STANK_RANKING_ROWS: 5,
    Keys.ENABLE_REACTION_BONUS: True,
    Keys.MAINTENANCE_MODE: False,
    # Embed templates are seeded per guild on install (see
    # `SettingsService.seed_defaults`) rather than inlined here; default
    # dicts live in `services/default_templates.py`.
}


@dataclass(slots=True)
class SettingsService:
    session: AsyncSession

    async def get(self, guild_id: int, key: str | Keys, default: Any = None) -> Any:
        """Return the per-guild value, or the registered default, or ``default``."""
        key_str = str(key)
        row = await self.session.get(GuildSetting, (guild_id, key_str))
        if row is not None:
            return row.value_json
        if key_str in DEFAULTS:
            return DEFAULTS[key_str]
        return default

    async def set(self, guild_id: int, key: str | Keys, value: Any) -> None:
        key_str = str(key)
        row = await self.session.get(GuildSetting, (guild_id, key_str))
        if row is None:
            row = GuildSetting(guild_id=guild_id, key=key_str, value_json=value)
            self.session.add(row)
        else:
            row.value_json = value

    async def delete(self, guild_id: int, key: str | Keys) -> None:
        row = await self.session.get(GuildSetting, (guild_id, str(key)))
        if row is not None:
            await self.session.delete(row)

    async def all_for_guild(self, guild_id: int) -> dict[str, Any]:
        """Return the effective settings map (defaults + overrides) for a guild.
        Used by the dashboard "config view" page and the slash-command
        ``/stank-admin config view`` snapshot.
        """
        result = dict(DEFAULTS)
        stmt = select(GuildSetting).where(GuildSetting.guild_id == guild_id)
        rows = (await self.session.execute(stmt)).scalars().all()
        for row in rows:
            result[row.key] = row.value_json
        return result

    async def effective_scoring(self, guild_id: int, altar: Altar) -> ScoringConfig:
        """Resolve scoring config with altar overrides taking precedence
        over guild settings, which take precedence over v1 defaults.
        """

        async def resolve(key: Keys, override: int | None, default_val: int) -> int:
            if override is not None:
                return override
            raw = await self.get(guild_id, key, default_val)
            return int(raw)

        return ScoringConfig(
            sp_flat=await resolve(Keys.SP_FLAT, altar.sp_flat_override, DEFAULT_SP_FLAT),
            sp_position_bonus=await resolve(
                Keys.SP_POSITION_BONUS,
                altar.sp_position_bonus_override,
                DEFAULT_SP_POSITION_BONUS,
            ),
            sp_starter_bonus=await resolve(
                Keys.SP_STARTER_BONUS,
                altar.sp_starter_bonus_override,
                DEFAULT_SP_STARTER_BONUS,
            ),
            sp_finish_bonus=await resolve(
                Keys.SP_FINISH_BONUS,
                altar.sp_finish_bonus_override,
                DEFAULT_SP_FINISH_BONUS,
            ),
            sp_reaction=await resolve(
                Keys.SP_REACTION, altar.sp_reaction_override, DEFAULT_SP_REACTION
            ),
            pp_break_base=await resolve(
                Keys.PP_BREAK_BASE,
                altar.pp_break_base_override,
                DEFAULT_PP_BREAK_BASE,
            ),
            pp_break_per_stank=await resolve(
                Keys.PP_BREAK_PER_STANK,
                altar.pp_break_per_stank_override,
                DEFAULT_PP_BREAK_PER_STANK,
            ),
            cooldown_seconds=await resolve(
                Keys.RESTANK_COOLDOWN_SECONDS,
                altar.cooldown_seconds_override,
                DEFAULT_RESTANK_COOLDOWN_SECONDS,
            ),
        )
