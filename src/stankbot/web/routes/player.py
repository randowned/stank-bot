"""Player profile pages."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.services import achievements as achievements_svc
from stankbot.services import history_service
from stankbot.services.session_service import SessionService
from stankbot.web.deps import (
    current_user,
    get_db,
    get_guild_id,
    get_templates,
    require_login,
)

router = APIRouter(tags=["player"])


@router.get("/me", response_class=HTMLResponse)
async def my_profile(user: dict = Depends(require_login)) -> RedirectResponse:
    return RedirectResponse(f"/player/{user['id']}", status_code=303)


@router.get("/player/{user_id}", response_class=HTMLResponse)
async def player_profile(
    user_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_guild_id),
) -> HTMLResponse:
    session_svc = SessionService(session)
    current_session = await session_svc.current(guild_id)
    if current_session is None and user_id == 0:
        raise HTTPException(status_code=404, detail="no data")

    session_stats = await history_service.user_summary(
        session, guild_id, user_id, session_id=current_session
    )
    alltime = await history_service.user_summary(session, guild_id, user_id)
    badge_keys = await achievements_svc.badges_for(session, guild_id, user_id)
    badges = [achievements_svc.definition(k) for k in badge_keys]
    badges = [b for b in badges if b is not None]

    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "player.html",
        {
            "request": request,
            "user": current_user(request),
            "target_id": user_id,
            "session_stats": session_stats,
            "alltime": alltime,
            "badges": badges,
        },
    )
