"""Public routes — board is the landing page (single-guild dashboard)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.repositories import altars as altars_repo
from stankbot.db.repositories import guilds as guilds_repo
from stankbot.services.board_service import build_board_state
from stankbot.web.deps import current_user, get_db, get_guild_id, get_templates

router = APIRouter(tags=["public"])


@router.get("/", response_class=HTMLResponse)
async def board(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_guild_id),
) -> HTMLResponse:
    guild = await guilds_repo.get(session, guild_id)
    altar = await altars_repo.primary(session, guild_id)
    if altar is None:
        raise HTTPException(status_code=404, detail="no altar configured")
    state = await build_board_state(
        session,
        guild_id=guild_id,
        guild_name=(guild.name if guild else f"Guild {guild_id}"),
        altar=altar,
    )
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "board.html",
        {
            "request": request,
            "user": current_user(request),
            "state": state,
        },
    )
