"""Admin dashboard pages — settings, altars, roles, audit.

Embed templates are code-managed (see ``services/default_templates.py``)
and no longer editable from the dashboard; admins preview them via
``/stank-admin preview`` in Discord.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.repositories import altars as altars_repo
from stankbot.db.repositories import audit_log as audit_repo
from stankbot.services.permission_service import PermissionService
from stankbot.services.settings_service import LABELS, Keys, SettingsService
from stankbot.web.deps import (
    current_user,
    get_db,
    get_guild_id,
    get_templates,
    guild_name_for,
    player_names_for,
    require_guild_admin,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
async def admin_index() -> RedirectResponse:
    return RedirectResponse(url="/admin/settings", status_code=302)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_guild_id),
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
    guild_id: int = Depends(get_guild_id),
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
    guild_id: int = Depends(get_guild_id),
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
    guild_id: int = Depends(get_guild_id),
    _admin: dict = Depends(require_guild_admin),
) -> HTMLResponse:
    svc = PermissionService(session)
    role_ids = await svc.list_admin_roles(guild_id)
    user_ids = await svc.list_admin_users(guild_id)
    names = await player_names_for(session, guild_id, user_ids)
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "admin/roles.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
            "role_ids": role_ids,
            "user_ids": user_ids,
            "names": names,
        },
    )


@router.get("/audit", response_class=HTMLResponse)
async def audit_page(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_guild_id),
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
