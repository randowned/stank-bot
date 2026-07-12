"""JSON admin API for the SvelteKit dashboard.

Returns JSON (never HTML or redirects) so the SvelteKit frontend can consume
it as a conventional REST API. Every route requires ``require_guild_admin``,
writes audit-log entries, and delegates to the same services.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.repositories import altars as altars_repo
from stankbot.db.repositories import audit_log as audit_repo
from stankbot.db.repositories import guilds as guilds_repo
from stankbot.services.permission_service import PermissionService
from stankbot.services.session_service import SessionEndReason, SessionService
from stankbot.services.settings_service import LABELS, Keys, SettingsService
from stankbot.utils.emoji import emoji_to_markup, parse_reaction_emojis
from stankbot.utils.time_utils import utc_isoformat
from stankbot.web.tools import (
    get_active_guild_id,
    get_db,
    guild_name_for,
    require_guild_admin,
)
from stankbot.web.transport import MsgPackResponse, msgpack_body

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _ok(request: Request, extra: dict[str, Any] | None = None) -> MsgPackResponse:
    body: dict[str, Any] = {"success": True}
    if extra:
        body.update(extra)
    return MsgPackResponse(body, request)


# ---------------------------------------------------------------------------
# Guild switcher
# ---------------------------------------------------------------------------


@router.post("/guild")
async def api_switch_guild(
    request: Request,
    guild_id: int = Query(...),
    user: dict[str, Any] = Depends(require_guild_admin),
    session: AsyncSession = Depends(get_db),
) -> MsgPackResponse:
    """Switch the active guild for the current session."""
    config = request.app.state.config
    target_gid = guild_id

    if int(user["id"]) != int(getattr(config, "owner_id", 0) or 0):
        svc = PermissionService(session, owner_id=config.owner_id)
        is_admin = await svc.is_admin(
            target_gid,
            int(user["id"]),
            [],
            has_manage_guild=False,
        )
        if not is_admin:
            raise HTTPException(status_code=403, detail="not allowed to switch to this guild")

    request.session["guild_id"] = target_gid
    return MsgPackResponse({"success": True, "guild_id": target_gid}, request)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


_SIMPLE_INT_KEYS = (
    Keys.SP_FLAT,
    Keys.SP_POSITION_BONUS,
    Keys.SP_STARTER_BONUS,
    Keys.SP_FINISH_BONUS,
    Keys.SP_REACTION,
    Keys.SP_TEAM_PLAYER_BONUS,
    Keys.PP_BREAK_BASE,
    Keys.PP_BREAK_PER_STANK,
    Keys.RESTANK_COOLDOWN_SECONDS,
    Keys.STANK_RANKING_ROWS,
    Keys.BOARD_NAME_MAX_LEN,
)

_SETTING_BOUNDS: dict[str, tuple[int, int]] = {
    Keys.SP_FLAT: (0, 1000),
    Keys.SP_POSITION_BONUS: (0, 500),
    Keys.SP_STARTER_BONUS: (0, 1000),
    Keys.SP_FINISH_BONUS: (0, 1000),
    Keys.SP_REACTION: (0, 500),
    Keys.SP_TEAM_PLAYER_BONUS: (0, 500),
    Keys.PP_BREAK_BASE: (0, 10000),
    Keys.PP_BREAK_PER_STANK: (0, 1000),
    Keys.RESTANK_COOLDOWN_SECONDS: (0, 86400),
    Keys.STANK_RANKING_ROWS: (1, 100),
    Keys.BOARD_NAME_MAX_LEN: (3, 64),
}
_SIMPLE_BOOL_KEYS = (
    Keys.CHAIN_CONTINUES_ACROSS_SESSIONS,
    Keys.ENABLE_REACTION_BONUS,
    Keys.MAINTENANCE_MODE,
)
_SIMPLE_INT_LIST_KEYS = (Keys.RESET_HOURS_UTC, Keys.RESET_WARNING_MINUTES)


@router.get("/settings")
async def get_settings(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> MsgPackResponse:
    values = await SettingsService(session).all_for_guild(guild_id)
    labels = {k: {"title": v[0], "help": v[1]} for k, v in LABELS.items()}
    return MsgPackResponse(
        {
            "guild_id": str(guild_id),
            "guild_name": await guild_name_for(session, guild_id),
            "values": values,
            "labels": labels,
        },
        request,
    )


class SettingsPayload(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


@router.post("/settings")
async def save_settings(
    request: Request,
    payload: SettingsPayload = msgpack_body(SettingsPayload),
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict[str, Any] = Depends(require_guild_admin),
) -> MsgPackResponse:
    svc = SettingsService(session)
    for key in _SIMPLE_INT_KEYS:
        if key in payload.values and payload.values[key] is not None:
            try:
                val = int(payload.values[key])
            except (TypeError, ValueError) as err:
                raise HTTPException(status_code=400, detail=f"bad int for {key}") from err
            bounds = _SETTING_BOUNDS.get(key)
            if bounds is not None:
                lo, hi = bounds
                if not (lo <= val <= hi):
                    raise HTTPException(
                        status_code=422,
                        detail=f"{key} must be between {lo} and {hi}",
                    )
            await svc.set(guild_id, key, val)
    for key in _SIMPLE_BOOL_KEYS:
        if key in payload.values and payload.values[key] is not None:
            await svc.set(guild_id, key, bool(payload.values[key]))
    needs_reschedule = False
    for key in _SIMPLE_INT_LIST_KEYS:
        if key in payload.values and payload.values[key] is not None:
            raw = payload.values[key]
            try:
                if isinstance(raw, str):
                    parsed = [int(x.strip()) for x in raw.split(",") if x.strip()]
                else:
                    parsed = [int(x) for x in raw]
            except (TypeError, ValueError) as err:
                raise HTTPException(status_code=400, detail=f"bad list for {key}") from err
            await svc.set(guild_id, key, parsed)
            needs_reschedule = True

    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="settings.update",
        payload={"via": "web"},
    )

    # Session reset hours / warning minutes only become live cron jobs when
    # the scheduler re-syncs. Commit first so its fresh session reads the new
    # values, then resync — otherwise the change needs a bot restart.
    if needs_reschedule:
        await session.commit()
        bot = getattr(request.app.state, "bot", None)
        scheduler = getattr(bot, "scheduler", None)
        if scheduler is not None:
            await scheduler.sync_guild(guild_id)

    return _ok(request)


# ---------------------------------------------------------------------------
# Altar
# ---------------------------------------------------------------------------


def _altar_dict(altar: Any) -> dict[str, Any]:
    return {
        "id": altar.id,
        "guild_id": str(altar.guild_id),
        "channel_id": str(altar.channel_id),
        "sticker_name_pattern": altar.sticker_name_pattern,
        "sticker_id": str(altar.sticker_id) if altar.sticker_id else None,
        "sticker_ids": [str(id) for id in (altar.sticker_ids or [])],
        "reaction_emoji_id": str(altar.reaction_emoji_id) if altar.reaction_emoji_id else None,
        "reaction_emoji_name": altar.reaction_emoji_name,
        # Comma-joined <:name:id> markup (or unicode glyph) for every accepted
        # emoji — the editable field round-trips back through the parser.
        "reaction_emoji_display": ", ".join(
            emoji_to_markup(s) for s in altar.reaction_emoji_specs
        )
        or None,
        "reaction_emoji_animated": bool(altar.reaction_emoji_animated),
        "enabled": bool(getattr(altar, "enabled", True)),
    }


@router.get("/altar")
async def get_altar(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> MsgPackResponse:
    altar = await altars_repo.for_guild(session, guild_id, enabled_only=False)
    return MsgPackResponse({"altar": _altar_dict(altar) if altar else None}, request)


class AltarSetPayload(BaseModel):
    channel_id: int
    sticker_pattern: str = "stank"
    sticker_ids: list[str] | None = None
    display_sticker_id: str | None = None
    reaction_emoji: str | None = None


@router.post("/altar/set")
async def altar_set(
    request: Request,
    payload: AltarSetPayload = msgpack_body(AltarSetPayload),
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict[str, Any] = Depends(require_guild_admin),
) -> MsgPackResponse:
    # Parse the (comma-separated) emoji field into accepted-emoji specs. The
    # first is the primary (drives {stank_emoji} + auto-react); the bare name —
    # never the full <:name:id> tag — is stored in reaction_emoji_name.
    specs = parse_reaction_emojis(payload.reaction_emoji)
    primary = specs[0] if specs else {"id": None, "name": None, "animated": False}
    reaction_emojis = specs if len(specs) > 1 else None

    await guilds_repo.ensure(session, guild_id)
    converted_sticker_ids: list[int] | None = (
        [int(sid) for sid in payload.sticker_ids] if payload.sticker_ids else None
    )
    converted_display_id: int | None = (
        int(payload.display_sticker_id) if payload.display_sticker_id else None
    )
    altar_row, created = await altars_repo.upsert(
        session,
        guild_id=guild_id,
        channel_id=payload.channel_id,
        sticker_name_pattern=payload.sticker_pattern.strip().lower(),
        reaction_emoji_id=primary["id"],
        reaction_emoji_name=primary["name"],
        reaction_emoji_animated=primary["animated"],
        reaction_emojis=reaction_emojis,
        sticker_id=converted_display_id,
        sticker_ids=converted_sticker_ids,
    )
    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="altar_created" if created else "altar_updated",
        payload={
            "altar_id": altar_row.id,
            "channel_id": payload.channel_id,
            "sticker_pattern": payload.sticker_pattern,
        },
    )
    return _ok(request, {"altar": _altar_dict(altar_row), "created": created})


@router.post("/altar/remove")
async def altar_remove(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict[str, Any] = Depends(require_guild_admin),
) -> MsgPackResponse:
    altar_row = await altars_repo.for_guild(session, guild_id, enabled_only=False)
    if altar_row is None:
        return MsgPackResponse({"success": False, "error": "no altar"}, request, status_code=404)
    altar_id = altar_row.id
    await session.delete(altar_row)
    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="altar_removed",
        payload={"altar_id": altar_id},
    )
    return _ok(request, {"altar_id": altar_id})


# ---------------------------------------------------------------------------
# Guild stickers & emojis — for the visual picker in the admin dashboard
# ---------------------------------------------------------------------------


@router.get("/guild-stickers")
async def guild_stickers(
    request: Request,
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
    include_default: bool = Query(False),
) -> MsgPackResponse:
    """Fetch guild custom stickers (+ optional default Discord stickers)."""
    bot = getattr(request.app.state, "bot", None)
    guild = bot.get_guild(guild_id) if bot else None
    stickers: list[dict[str, Any]] = []

    # Custom guild stickers (from bot's in-memory cache)
    if guild:
        for s in guild.stickers:
            stickers.append({
                "id": str(s.id),
                "name": s.name,
                "image_url": str(s.url) if s.url else None,
                "type": "custom",
            })

    # Default Discord stickers (from sticker packs API)
    if include_default and bot:
        try:
            packs = await bot.fetch_sticker_packs()
            for pack in packs:
                for s in pack.stickers:
                    stickers.append({
                        "id": str(s.id),
                        "name": s.name,
                        "image_url": str(s.url) if s.url else None,
                        "type": "default",
                    })
        except Exception:
            log.warning("Failed to fetch default sticker packs", exc_info=True)

    return MsgPackResponse({"stickers": stickers}, request)


@router.get("/guild-emojis")
async def guild_emojis(
    request: Request,
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
    include_default: bool = Query(False),
) -> MsgPackResponse:
    """Fetch guild custom emojis (+ optional default Unicode emojis)."""
    bot = getattr(request.app.state, "bot", None)
    guild = bot.get_guild(guild_id) if bot else None
    emojis: list[dict[str, Any]] = []

    # Custom guild emojis (from bot's in-memory cache)
    if guild:
        for e in guild.emojis:
            emojis.append({
                "id": str(e.id),
                "name": e.name,
                "image_url": str(e.url) if e.url else None,
                "animated": e.animated,
                "type": "custom",
            })

    # Default Unicode emojis (synthetic, no IDs)
    if include_default:
        _default_emojis = [
            "😀", "😂", "🤣", "😍", "🥰", "😘", "😜", "🤩", "😎", "🤗",
            "👍", "👎", "👏", "🙌", "🔥", "💯", "🎉", "✨", "❤️", "💀",
            "😭", "😤", "🥺", "🤔", "🙄", "😬", "🤯", "🥳", "😈", "💩",
        ]
        for glyph in _default_emojis:
            emojis.append({
                "id": None,
                "name": glyph,
                "image_url": None,
                "animated": False,
                "type": "default",
            })

    return MsgPackResponse({"emojis": emojis}, request)


# ---------------------------------------------------------------------------
# Roles + admin users
# ---------------------------------------------------------------------------


@router.get("/roles")
async def get_roles(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> MsgPackResponse:

    svc = PermissionService(session)
    role_ids = await svc.list_admin_roles(guild_id)
    global_user_ids = await svc.list_admin_users()

    bot = getattr(request.app.state, "bot", None)
    discord_guild = bot.get_guild(guild_id) if bot else None

    role_names: dict[str, str] = {}
    if discord_guild:
        for rid in role_ids:
            role = discord_guild.get_role(rid)
            if role:
                role_names[str(rid)] = role.name

    user_names: dict[str, str] = {}
    avatars: dict[str, str] = {}
    if bot:
        import asyncio
        async def _fetch_name(uid: int) -> tuple[int, str | None, str | None]:
            user = bot.get_user(uid)
            if user:
                return uid, user.name, user.avatar.key if user.avatar else None
            try:
                user = await bot.fetch_user(uid)
                return uid, user.name, user.avatar.key if user.avatar else None
            except Exception:
                return uid, None, None
        results = await asyncio.gather(*(_fetch_name(uid) for uid in global_user_ids))
        user_names = {str(uid): name for uid, name, _ in results if name}
        avatars = {str(uid): av for uid, _, av in results if av}

    return MsgPackResponse(
        {
            "role_ids": [str(r) for r in role_ids],
            "role_names": role_names,
            "global_user_ids": [str(u) for u in global_user_ids],
            "names": user_names,
            "avatars": avatars,
        },
        request,
    )


class UserIdPayload(BaseModel):
    user_id: int


@router.post("/roles/users/add")
async def users_add(
    request: Request,
    payload: UserIdPayload = msgpack_body(UserIdPayload),
    session: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_guild_admin),
) -> MsgPackResponse:
    svc = PermissionService(session)
    await svc.add_admin_user(payload.user_id)
    return _ok(request, {"user_id": str(payload.user_id)})


@router.post("/roles/users/remove")
async def users_remove(
    request: Request,
    payload: UserIdPayload = msgpack_body(UserIdPayload),
    session: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_guild_admin),
) -> MsgPackResponse:
    svc = PermissionService(session)
    await svc.remove_admin_user(payload.user_id)
    return _ok(request, {"user_id": str(payload.user_id)})


class RoleIdPayload(BaseModel):
    role_id: int


@router.post("/roles/add")
async def roles_add(
    request: Request,
    payload: RoleIdPayload = msgpack_body(RoleIdPayload),
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> MsgPackResponse:
    svc = PermissionService(session)
    await svc.add_admin_role(guild_id, payload.role_id)
    return _ok(request, {"role_id": str(payload.role_id)})


@router.post("/roles/remove")
async def roles_remove(
    request: Request,
    payload: RoleIdPayload = msgpack_body(RoleIdPayload),
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> MsgPackResponse:
    svc = PermissionService(session)
    await svc.remove_admin_role(guild_id, payload.role_id)
    return _ok(request, {"role_id": str(payload.role_id)})


# ---------------------------------------------------------------------------
# Audit log (paginated)
# ---------------------------------------------------------------------------


@router.get("/audit")
async def get_audit(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    actor_id: int | None = Query(None),
) -> MsgPackResponse:
    from stankbot.db.models import AuditLog
    from stankbot.web.tools import player_names_for

    stmt = select(AuditLog).where(AuditLog.guild_id == guild_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    stmt = stmt.order_by(AuditLog.id.desc()).offset(offset).limit(limit)
    entries = list((await session.execute(stmt)).scalars().all())

    actor_ids = {e.actor_id for e in entries if e.actor_id}
    names = await player_names_for(session, guild_id, actor_ids)

    def to_dict(e: AuditLog) -> dict[str, Any]:
        return {
            "id": e.id,
            "created_at": utc_isoformat(e.created_at),
            "actor_id": str(e.actor_id) if e.actor_id else None,
            "actor_name": names.get(e.actor_id) if e.actor_id else None,
            "action": e.action,
            "payload": e.payload_json,
        }

    return MsgPackResponse(
        {"entries": [to_dict(e) for e in entries], "limit": limit, "offset": offset},
        request,
    )


# ---------------------------------------------------------------------------
# Game events log (paginated)
# ---------------------------------------------------------------------------


@router.get("/events")
async def get_events(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None),
) -> MsgPackResponse:
    from stankbot.db.models import Event
    from stankbot.web.tools import player_names_for

    stmt = select(Event).where(Event.guild_id == guild_id)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            Event.type.ilike(pattern)
            | Event.reason.ilike(pattern)
        )
    stmt = stmt.order_by(Event.id.desc()).offset(offset).limit(limit)
    entries = list((await session.execute(stmt)).scalars().all())

    user_ids = {e.user_id for e in entries if e.user_id is not None}
    names = await player_names_for(session, guild_id, user_ids)

    def to_dict(e: Event) -> dict[str, Any]:
        return {
            "id": e.id,
            "created_at": utc_isoformat(e.created_at),
            "type": e.type,
            "user_id": str(e.user_id) if e.user_id is not None else None,
            "user_name": names.get(e.user_id) if e.user_id is not None else None,
            "delta": e.delta,
            "reason": e.reason,
            "chain_id": e.chain_id,
            "message_id": str(e.message_id) if e.message_id is not None else None,
        }

    return MsgPackResponse(
        {"entries": [to_dict(e) for e in entries], "limit": limit, "offset": offset},
        request,
    )


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------


@router.get("/announcements")
async def get_announcements(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> MsgPackResponse:
    from stankbot.db.models import ChannelBinding, ChannelPurpose

    rows = (
        await session.execute(
            select(ChannelBinding.channel_id).where(
                ChannelBinding.guild_id == guild_id,
                ChannelBinding.purpose == ChannelPurpose.ANNOUNCEMENTS.value,
            )
        )
    ).scalars().all()
    return MsgPackResponse({"channel_ids": [str(r) for r in rows]}, request)


class AnnouncementPayload(BaseModel):
    channel_id: int


@router.post("/announcements")
async def announcements_add(
    request: Request,
    payload: AnnouncementPayload = msgpack_body(AnnouncementPayload),
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict[str, Any] = Depends(require_guild_admin),
) -> MsgPackResponse:
    from stankbot.db.models import ChannelBinding, ChannelPurpose

    await guilds_repo.ensure(session, guild_id)
    session.add(
        ChannelBinding(
            guild_id=guild_id,
            channel_id=payload.channel_id,
            purpose=ChannelPurpose.ANNOUNCEMENTS.value,
        )
    )
    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="announcement_added",
        payload={"channel_id": payload.channel_id},
    )
    return _ok(request, {"channel_id": str(payload.channel_id)})


@router.post("/announcements/remove")
async def announcements_remove(
    request: Request,
    payload: AnnouncementPayload = msgpack_body(AnnouncementPayload),
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict[str, Any] = Depends(require_guild_admin),
) -> MsgPackResponse:
    from stankbot.db.models import ChannelBinding, ChannelPurpose

    await session.execute(
        delete(ChannelBinding).where(
            ChannelBinding.guild_id == guild_id,
            ChannelBinding.channel_id == payload.channel_id,
            ChannelBinding.purpose == ChannelPurpose.ANNOUNCEMENTS.value,
        )
    )
    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="announcement_removed",
        payload={"channel_id": payload.channel_id},
    )
    return _ok(request, {"channel_id": str(payload.channel_id)})


# ---------------------------------------------------------------------------
# Config snapshot (read-only)
# ---------------------------------------------------------------------------


@router.get("/config")
async def get_config(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> MsgPackResponse:
    values = await SettingsService(session).all_for_guild(guild_id)
    altars = await altars_repo.list_for_guild(session, guild_id, enabled_only=False)
    labels = {k: {"title": v[0], "help": v[1]} for k, v in LABELS.items()}
    return MsgPackResponse(
        {
            "guild_id": str(guild_id),
            "guild_name": await guild_name_for(session, guild_id),
            "settings": values,
            "altars": [_altar_dict(a) for a in altars],
            "labels": labels,
        },
        request,
    )


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


@router.get("/templates")
async def list_templates(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> MsgPackResponse:
    from stankbot.services.default_templates import ALL_DEFAULTS
    from stankbot.services.template_store import all_keys, load

    keys = all_keys()
    templates = {k: await load(k, session, guild_id) for k in keys}
    return MsgPackResponse(
        {
            "keys": keys,
            "templates": templates,
            "defaults": {k: dict(v) for k, v in ALL_DEFAULTS.items()},
        },
        request,
    )


@router.get("/templates/{key}")
async def get_template(
    key: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> MsgPackResponse:
    from stankbot.services.default_templates import ALL_DEFAULTS
    from stankbot.services.template_store import load

    if key not in ALL_DEFAULTS:
        raise HTTPException(status_code=404, detail="unknown template key")
    data = await load(key, session, guild_id)
    return MsgPackResponse({"key": key, "data": data}, request)


class TemplateSavePayload(BaseModel):
    data: dict[str, Any]


@router.post("/templates/{key}")
async def save_template(
    key: str,
    request: Request,
    payload: TemplateSavePayload = msgpack_body(TemplateSavePayload),
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict[str, Any] = Depends(require_guild_admin),
) -> MsgPackResponse:
    from stankbot.services.default_templates import ALL_DEFAULTS
    from stankbot.services.template_engine import TemplateError, validate_template_variables
    from stankbot.services.template_store import save, validate

    if key not in ALL_DEFAULTS:
        raise HTTPException(status_code=404, detail="unknown template key")

    unknown = validate(payload.data)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"unknown top-level keys: {', '.join(unknown)}",
        )

    try:
        for k, v in payload.data.items():
            if isinstance(v, str):
                validate_template_variables(v)
            elif k == "fields" and isinstance(v, list):
                for field in v:
                    if not isinstance(field, dict):
                        continue
                    for fkey in ("name", "value"):
                        fv = field.get(fkey)
                        if isinstance(fv, str):
                            validate_template_variables(fv)
    except TemplateError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    await save(key, payload.data, session, guild_id)
    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="template_saved",
        payload={"key": key, "via": "web"},
    )
    return _ok(request, {"key": key})


class TemplatePreviewPayload(BaseModel):
    data: dict[str, Any]
    context_preset: str = "chain_board"


_PREVIEW_CONTEXTS: dict[str, dict[str, Any]] = {
    "chain_board": {
        "guild_name": "Acme Guild",
        "stank_emoji": ":stank:",
        "altar_sticker_url": "",
        "altar_channel_mention": "#altar",
        "board_url": "https://example.com/",
        "current": 42,
        "current_unique": 7,
        "record": 100,
        "record_unique": 12,
        "alltime_record": 256,
        "alltime_record_unique": 18,
    },
    "chain_record": {
        "guild_name": "Acme Guild",
        "length": 128,
        "unique_contributors": 20,
        "starter": "Alice",
        "previous_record": 100,
    },
    "chain_break": {
        "guild_name": "Acme Guild",
        "breaker": "Charlie",
        "punishments": 15,
        "final_length": 42,
    },
    "session_start": {
        "guild_name": "Acme Guild",
        "session_id": 5,
        "started_at": "2026-04-23T12:00:00Z",
    },
    "points": {
        "user": "Alice",
        "earned_sp": 120,
        "reason": "chain_contribution",
    },
    "cooldown": {
        "user": "Alice",
        "remaining_seconds": 45,
    },
    "tissue": {
        "target_display_name": "Alice",
        "tissue_action": "grabbed a tissue",
        "tissue_count": 7,
        "board_url": "https://example.com/",
    },
    "youtube_milestone": {
        "title": "Never Gonna Give You Up",
        "provider_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        "chart_url": "https://via.placeholder.com/1200x675/1a1d24/3b82f6?text=12h+Chart",
        "milestone_value": "10,000,000",
        "metric_label": "Views",
        "other_metrics": "\U0001f44d 1.2M  \u00b7  \U0001f4ac 45K  \u00b7  \u23f1 3m 42s",
        "board_url": "https://example.com/",
        "media_page_url": "https://example.com/media/1",
    },
    "spotify_milestone": {
        "title": "Blinding Lights",
        "provider_url": "https://open.spotify.com/track/0VjIjW4GlUZAMYd2vXMi3b",
        "thumbnail_url": "https://i.scdn.co/image/ab67616d0000b273b51a0a46c7d09c4c2b3b4c00",
        "chart_url": "https://via.placeholder.com/1200x675/1a1d24/3b82f6?text=12h+Chart",
        "milestone_value": "50,000,000",
        "metric_label": "Play Count",
        "other_metrics": "\U0001f3b5 track  \u00b7  \U0001f4c5 Jan 15, 2020",
        "board_url": "https://example.com/",
        "media_page_url": "https://example.com/media/2",
    },
}


@router.post("/templates/{key}/preview")
async def preview_template(
    key: str,
    request: Request,
    payload: TemplatePreviewPayload = msgpack_body(TemplatePreviewPayload),
    _admin: dict = Depends(require_guild_admin),
) -> MsgPackResponse:
    from stankbot.services.default_templates import ALL_DEFAULTS
    from stankbot.services.template_engine import RenderContext, TemplateError, substitute

    if key not in ALL_DEFAULTS:
        raise HTTPException(status_code=404, detail="unknown template key")
    ctx_vars = _PREVIEW_CONTEXTS.get(payload.context_preset, _PREVIEW_CONTEXTS["chain_board"])
    ctx = RenderContext(variables=ctx_vars)

    def sub(text: Any) -> Any:
        if not isinstance(text, str):
            return text
        return substitute(text, ctx)

    try:
        rendered: dict[str, Any] = {}
        for k, v in payload.data.items():
            if isinstance(v, str):
                rendered[k] = sub(v)
            elif k == "fields" and isinstance(v, list):
                rendered[k] = [
                    {
                        "name": sub(f.get("name", "")) if isinstance(f, dict) else "",
                        "value": sub(f.get("value", "")) if isinstance(f, dict) else "",
                        "inline": bool(f.get("inline", False)) if isinstance(f, dict) else False,
                    }
                    for f in v
                ]
            elif k == "author" and isinstance(v, dict):
                rendered[k] = {ak: sub(av) for ak, av in v.items()}
            else:
                rendered[k] = v
    except TemplateError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    return MsgPackResponse(
        {"rendered": rendered, "context": ctx_vars, "preset": payload.context_preset},
        request,
    )


# ---------------------------------------------------------------------------
# Session operations (destructive)
# ---------------------------------------------------------------------------


@router.post("/new-session")
async def new_session(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict[str, Any] = Depends(require_guild_admin),
) -> MsgPackResponse:
    await guilds_repo.ensure(session, guild_id)
    svc = SessionService(session)
    end_result = await svc.end_session(guild_id, reason=SessionEndReason.MANUAL)
    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="new_session",
        payload={
            "ended_session_id": end_result.ended_session_id,
            "new_session_id": end_result.new_session_id,
            "via": "web",
        },
    )
    return _ok(request, {"ended_session_id": end_result.ended_session_id, "new_session_id": end_result.new_session_id})


class ResetPayload(BaseModel):
    confirm: str


@router.post("/reset")
async def reset_guild(
    request: Request,
    payload: ResetPayload = msgpack_body(ResetPayload),
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict[str, Any] = Depends(require_guild_admin),
) -> MsgPackResponse:
    """Wipe all event/chain/cooldown/record state for the guild.

    Requires an explicit ``{"confirm": "RESET"}`` body so that a mistyped
    curl or a CSRF-style replay can't blow away the guild.
    """
    if payload.confirm != "RESET":
        raise HTTPException(status_code=400, detail="confirm must be 'RESET'")

    from stankbot.db.models import (
        Chain,
        ChainMessage,
        Cooldown,
        Event,
        PlayerBadge,
        PlayerTotal,
        ReactionAward,
        Record,
    )

    chain_ids = list(
        (await session.execute(select(Chain.id).where(Chain.guild_id == guild_id))).scalars()
    )
    if chain_ids:
        await session.execute(delete(ChainMessage).where(ChainMessage.chain_id.in_(chain_ids)))
    for model in (Event, Chain, Cooldown, ReactionAward, Record, PlayerTotal, PlayerBadge):
        await session.execute(delete(model).where(model.guild_id == guild_id))
    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="reset",
        payload={"via": "web"},
    )
    return _ok(request)


@router.post("/rebuild")
async def rebuild(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict[str, Any] = Depends(require_guild_admin),
) -> MsgPackResponse:
    from stankbot.services import rebuild_service

    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        raise HTTPException(status_code=503, detail="bot not attached")

    try:
        report = await rebuild_service.rebuild(bot, guild_id)
    except Exception as exc:
        log.exception("rebuild failed")
        await audit_repo.append(
            session,
            guild_id=guild_id,
            actor_id=int(user["id"]),
            action="rebuild_failed",
            payload={"error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="rebuild failed") from exc

    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="rebuild_from_history",
        payload={
            "altars": report.altars_scanned,
            "messages": report.messages_scanned,
            "valid_stanks": report.valid_stanks,
            "chain_breaks": report.chain_breaks,
            "reactions": report.reactions_awarded,
        },
    )
    return _ok(
        request,
        {
            "altars_scanned": report.altars_scanned,
            "messages_scanned": report.messages_scanned,
            "valid_stanks": report.valid_stanks,
            "chain_breaks": report.chain_breaks,
            "reactions_awarded": report.reactions_awarded,
        },
    )

# ---------------------------------------------------------------------------
# player_totals cache rebuild (DB-only -- fast, no Discord API calls)
# ---------------------------------------------------------------------------


@router.post("/rebuild-from-db")
async def rebuild_from_db(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict[str, Any] = Depends(require_guild_admin),
) -> MsgPackResponse:
    from stankbot.db.repositories import player_chain_totals as pct_repo
    from stankbot.db.repositories import player_totals as pt_repo

    pt_count = await pt_repo.rebuild(session, guild_id)
    pct_count = await pct_repo.rebuild(session, guild_id)
    total = pt_count + pct_count
    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="rebuild_from_db",
        payload={"player_totals": pt_count, "player_chain_totals": pct_count},
    )
    log.info(
        "Admin %s rebuilt totals for guild %d: %d pt + %d pct rows",
        user["id"],
        guild_id,
        pt_count,
        pct_count,
    )
    return _ok(request, {"rows": total})
