"""Admin dashboard pages — settings, altars, roles, audit.

Embed templates are code-managed (see ``services/default_templates.py``)
and no longer editable from the dashboard; admins preview them via
``/stank-admin preview`` in Discord.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import AdminUser, ChannelBinding, ChannelPurpose, Guild
from stankbot.db.repositories import altars as altars_repo
from stankbot.db.repositories import audit_log as audit_repo
from stankbot.db.repositories import guilds as guilds_repo
from stankbot.services.permission_service import PermissionService
from stankbot.services.session_service import SessionService
from stankbot.services.settings_service import LABELS, Keys, SettingsService
from stankbot.config import AppConfig
from stankbot.web.deps import (
    current_user,
    get_active_guild_id,
    get_db,
    get_guild_id,
    get_templates,
    guild_name_for,
    player_names_for,
    require_guild_admin,
    require_login,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/guilds/select")
async def select_guild(
    request: Request,
    guild_id: int = Query(...),
    user: dict = Depends(require_login),
) -> RedirectResponse:
    """Switch the active guild for this admin session. Owner can switch to any bot guild."""
    from stankbot.web.deps import _is_owner

    config: AppConfig = request.app.state.config
    bot_guilds = getattr(request.app.state, "bot_guilds", [])
    user_id = int(user["id"])
    allowed = _is_owner(request)
    if not allowed:
        from stankbot.services.permission_service import PermissionService

        user_guild_ids = {int(g["id"]) for g in request.session.get("guilds", [])}
        allowed = guild_id in user_guild_ids
        if allowed:
            async with request.app.state.session_factory() as session:
                svc = PermissionService(session, owner_id=config.owner_id)
                perms = next((g["permissions"] for g in request.session.get("guilds", []) if int(g["id"]) == guild_id), 0)
                allowed = await svc.is_admin(guild_id, user_id, [], has_manage_guild=bool(perms & 0x20))
    if not allowed:
        raise HTTPException(status_code=403, detail="not allowed to switch to this guild")
    request.session["guild"] = guild_id
    return RedirectResponse("/admin/settings", status_code=303)


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
async def admin_index() -> RedirectResponse:
    return RedirectResponse(url="/admin/settings", status_code=302)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> HTMLResponse:
    svc = SettingsService(session)
    values = await svc.all_for_guild(guild_id)
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "admin/settings.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
            "settings": values,
            "labels": LABELS,
            "saved": request.query_params.get("saved") == "1",
        },
    )


@router.post("/settings")
async def settings_save(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict = Depends(require_guild_admin),
) -> RedirectResponse:
    form = await request.form()
    svc = SettingsService(session)

    for key in (
        Keys.SP_FLAT,
        Keys.SP_POSITION_BONUS,
        Keys.SP_STARTER_BONUS,
        Keys.SP_FINISH_BONUS,
        Keys.SP_REACTION,
        Keys.PP_BREAK_BASE,
        Keys.PP_BREAK_PER_STANK,
        Keys.RESTANK_COOLDOWN_SECONDS,
        Keys.STANK_RANKING_ROWS,
        Keys.BOARD_NAME_MAX_LEN,
    ):
        raw = form.get(str(key))
        if raw is not None and str(raw).strip():
            await svc.set(guild_id, key, int(raw))
    for key in (
        Keys.CHAIN_CONTINUES_ACROSS_SESSIONS,
        Keys.ENABLE_REACTION_BONUS,
        Keys.MAINTENANCE_MODE,
    ):
        await svc.set(guild_id, key, form.get(str(key)) == "on")
    hours = form.get(str(Keys.RESET_HOURS_UTC))
    if hours:
        await svc.set(
            guild_id,
            Keys.RESET_HOURS_UTC,
            [int(h.strip()) for h in str(hours).split(",") if h.strip()],
        )
    warns = form.get(str(Keys.RESET_WARNING_MINUTES))
    if warns:
        await svc.set(
            guild_id,
            Keys.RESET_WARNING_MINUTES,
            [int(m.strip()) for m in str(warns).split(",") if m.strip()],
        )
    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="settings.update",
        payload={"via": "web"},
    )
    return RedirectResponse("/admin/settings?saved=1", status_code=303)


@router.get("/altar", response_class=HTMLResponse)
async def altar_page(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> HTMLResponse:
    altar = await altars_repo.for_guild(session, guild_id, enabled_only=False)
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "admin/altar.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
            "altar": altar,
        },
    )


@router.get("/roles", response_class=HTMLResponse)
async def roles_page(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> HTMLResponse:
    svc = PermissionService(session)
    role_ids = await svc.list_admin_roles(guild_id)
    global_user_ids = await svc.list_admin_users()
    all_user_ids = set(global_user_ids)
    names = await player_names_for(session, guild_id, all_user_ids)
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "admin/roles.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
            "role_ids": role_ids,
            "global_user_ids": global_user_ids,
            "names": names,
        },
    )


@router.get("/audit", response_class=HTMLResponse)
async def audit_page(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> HTMLResponse:
    entries = await audit_repo.recent(session, guild_id, limit=200)
    actor_ids = {e.actor_id for e in entries if e.actor_id}
    names = await player_names_for(session, guild_id, actor_ids)
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "admin/audit.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
            "entries": entries,
            "names": names,
        },
    )


@router.get("/announcements", response_class=HTMLResponse)
async def announcements_list_page(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> HTMLResponse:
    rows = (
        await session.execute(
            select(ChannelBinding.channel_id).where(
                ChannelBinding.guild_id == guild_id,
                ChannelBinding.purpose == ChannelPurpose.ANNOUNCEMENTS.value,
            )
        )
    ).scalars().all()
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "admin/announcements.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
            "channel_ids": list(rows),
        },
    )


@router.post("/announcements/add")
async def announcements_add(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict = Depends(require_guild_admin),
) -> RedirectResponse:
    form = await request.form()
    channel_id = int(form.get("channel_id") or 0)
    if channel_id:
        await guilds_repo.ensure(session, guild_id)
        session.add(
            ChannelBinding(
                guild_id=guild_id,
                channel_id=channel_id,
                purpose=ChannelPurpose.ANNOUNCEMENTS.value,
            )
        )
        await audit_repo.append(
            session,
            guild_id=guild_id,
            actor_id=int(user["id"]),
            action="announcement_added",
            payload={"channel_id": channel_id},
        )
    return RedirectResponse("/admin/announcements", status_code=303)


@router.post("/announcements/remove")
async def announcements_remove(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict = Depends(require_guild_admin),
) -> RedirectResponse:
    form = await request.form()
    channel_id = int(form.get("channel_id") or 0)
    if channel_id:
        await session.execute(
            delete(ChannelBinding).where(
                ChannelBinding.guild_id == guild_id,
                ChannelBinding.channel_id == channel_id,
                ChannelBinding.purpose == ChannelPurpose.ANNOUNCEMENTS.value,
            )
        )
        await audit_repo.append(
            session,
            guild_id=guild_id,
            actor_id=int(user["id"]),
            action="announcement_removed",
            payload={"channel_id": channel_id},
        )
    return RedirectResponse("/admin/announcements", status_code=303)


@router.get("/maintenance", response_class=HTMLResponse)
async def maintenance_page(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> HTMLResponse:
    svc = SettingsService(session)
    values = await svc.all_for_guild(guild_id)
    enabled = values.get(Keys.MAINTENANCE_MODE, False)
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "admin/maintenance.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
            "maintenance_enabled": enabled,
        },
    )


@router.post("/maintenance")
async def maintenance_toggle(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict = Depends(require_guild_admin),
) -> RedirectResponse:
    form = await request.form()
    enabled = form.get("enabled") == "true"
    await SettingsService(session).set(guild_id, Keys.MAINTENANCE_MODE, enabled)
    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="maintenance_mode",
        payload={"enabled": enabled, "via": "web"},
    )
    return RedirectResponse("/admin/maintenance?saved=1", status_code=303)


@router.get("/config", response_class=HTMLResponse)
async def config_view_page(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> HTMLResponse:
    svc = SettingsService(session)
    values = await svc.all_for_guild(guild_id)
    altars = await altars_repo.list_for_guild(session, guild_id, enabled_only=False)
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "admin/config.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
            "settings": values,
            "altars": altars,
            "labels": LABELS,
        },
    )


@router.get("/new-session", response_class=HTMLResponse)
async def new_session_page(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> HTMLResponse:
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "admin/new-session.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
        },
    )


@router.post("/new-session")
async def new_session_action(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict = Depends(require_guild_admin),
) -> RedirectResponse:
    from stankbot.db.models import SessionEndReason

    await guilds_repo.ensure(session, guild_id)
    svc = SessionService(session)
    ended, new_id = await svc.end_session(guild_id, reason=SessionEndReason.MANUAL)
    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="new_session",
        payload={"ended_session_id": ended, "new_session_id": new_id, "via": "web"},
    )
    return RedirectResponse("/admin/new-session?done=1", status_code=303)


@router.get("/reset", response_class=HTMLResponse)
async def reset_page(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> HTMLResponse:
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "admin/reset.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
            "done": request.query_params.get("done") == "1",
        },
    )


@router.post("/reset")
async def reset_action(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict = Depends(require_guild_admin),
) -> RedirectResponse:
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
        (
            await session.execute(select(Chain.id).where(Chain.guild_id == guild_id))
        ).scalars()
    )
    if chain_ids:
        await session.execute(
            delete(ChainMessage).where(ChainMessage.chain_id.in_(chain_ids))
        )
    for model in (
        Event,
        Chain,
        Cooldown,
        ReactionAward,
        Record,
        PlayerTotal,
        PlayerBadge,
    ):
        await session.execute(
            delete(model).where(model.guild_id == guild_id)
        )
    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="reset",
        payload={"via": "web"},
    )
    return RedirectResponse("/admin/reset?done=1", status_code=303)


@router.get("/rebuild", response_class=HTMLResponse)
async def rebuild_page(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> HTMLResponse:
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "admin/rebuild.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
        },
    )


@router.post("/rebuild")
async def rebuild_action(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict = Depends(require_guild_admin),
) -> RedirectResponse:
    from stankbot.services import rebuild_service

    try:
        bot = getattr(request.app.state, "bot", None)
        if bot is None:
            return RedirectResponse("/admin/rebuild?error=1", status_code=303)
        report = await rebuild_service.rebuild(bot, guild_id)
    except Exception as exc:
        await audit_repo.append(
            session,
            guild_id=guild_id,
            actor_id=int(user["id"]),
            action="rebuild_failed",
            payload={"error": str(exc)},
        )
        return RedirectResponse("/admin/rebuild?error=1", status_code=303)

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
    return RedirectResponse("/admin/rebuild?done=1", status_code=303)


@router.post("/altar/set")
async def altar_set(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict = Depends(require_guild_admin),
) -> RedirectResponse:
    form = await request.form()
    channel_id = int(form.get("channel_id") or 0)
    sticker_pattern = str(form.get("sticker_pattern") or "stank").strip().lower()
    reaction_emoji_name = str(form.get("reaction_emoji") or "") or None
    emoji_id: int | None = None
    emoji_animated = False
    if reaction_emoji_name:
        import re

        m = re.match(r"<a?:[A-Za-z0-9_~]+:(\d+)>", reaction_emoji_name)
        if m:
            emoji_id = int(m.group(1))
            emoji_animated = reaction_emoji_name.startswith("<a:")

    await guilds_repo.ensure(session, guild_id)
    altar_row, created = await altars_repo.upsert(
        session,
        guild_id=guild_id,
        channel_id=channel_id,
        sticker_name_pattern=sticker_pattern,
        reaction_emoji_id=emoji_id,
        reaction_emoji_name=reaction_emoji_name,
        reaction_emoji_animated=emoji_animated,
    )
    await audit_repo.append(
        session,
        guild_id=guild_id,
        actor_id=int(user["id"]),
        action="altar_created" if created else "altar_updated",
        payload={
            "altar_id": altar_row.id,
            "channel_id": channel_id,
            "sticker_pattern": sticker_pattern,
        },
    )
    return RedirectResponse("/admin/altar", status_code=303)


@router.post("/altar/remove")
async def altar_remove(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_active_guild_id),
    user: dict = Depends(require_guild_admin),
) -> RedirectResponse:
    altar_row = await altars_repo.for_guild(session, guild_id, enabled_only=False)
    if altar_row:
        altar_id = altar_row.id
        await session.delete(altar_row)
        await audit_repo.append(
            session,
            guild_id=guild_id,
            actor_id=int(user["id"]),
            action="altar_removed",
            payload={"altar_id": altar_id},
        )
    return RedirectResponse("/admin/altar", status_code=303)


@router.post("/users/add")
async def users_add(
    request: Request,
    session: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_guild_admin),
) -> RedirectResponse:
    form = await request.form()
    user_id = int(form.get("user_id") or 0)
    if user_id:
        svc = PermissionService(session)
        await svc.add_admin_user(user_id)
    return RedirectResponse("/admin/roles", status_code=303)


@router.post("/users/remove")
async def users_remove(
    request: Request,
    session: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_guild_admin),
) -> RedirectResponse:
    form = await request.form()
    user_id = int(form.get("user_id") or 0)
    if user_id:
        svc = PermissionService(session)
        await svc.remove_admin_user(user_id)
    return RedirectResponse("/admin/roles", status_code=303)


@router.get("/templates", response_class=HTMLResponse)
async def templates_page(
    request: Request,
    _admin: dict = Depends(require_guild_admin),
) -> HTMLResponse:
    from stankbot.services.default_templates import ALL_DEFAULTS
    from stankbot.services.template_store import list_templates, load

    keys = list_templates() or list(ALL_DEFAULTS.keys())
    current = request.query_params.get("key") or "board_embed"
    if current not in ALL_DEFAULTS:
        current = "board_embed"
    data = load(current)
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "admin/templates.html",
        {
            "request": request,
            "user": current_user(request),
            "keys": keys,
            "current_key": current,
            "current_data": data,
        },
    )


@router.post("/templates")
async def templates_save(
    request: Request,
    _admin: dict = Depends(require_guild_admin),
) -> RedirectResponse:
    form = await request.form()
    key = str(form.get("key") or "")
    json_str = str(form.get("data") or "{}")
    import json

    try:
        data = json.loads(json_str)
    except Exception:
        return RedirectResponse(f"/admin/templates?key={key}&error=1", status_code=303)
    from stankbot.services.template_store import save

    save(key, data)
    return RedirectResponse(f"/admin/templates?key={key}&saved=1", status_code=303)
