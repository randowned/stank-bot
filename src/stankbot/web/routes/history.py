"""Chain + session history browse."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.models import Chain, Event, EventType
from stankbot.services import history_service
from stankbot.web.deps import (
    current_user,
    get_db,
    get_guild_id,
    get_templates,
    guild_name_for,
    player_names_for,
)

router = APIRouter(tags=["history"])


@router.get("/history/chains", response_class=HTMLResponse)
async def chains_index(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_guild_id),
    limit: int = 50,
) -> HTMLResponse:
    stmt = (
        select(Chain)
        .where(Chain.guild_id == guild_id)
        .order_by(Chain.id.desc())
        .limit(limit)
    )
    chains = list((await session.execute(stmt)).scalars().all())
    starter_ids = {c.starter_user_id for c in chains if c.starter_user_id}
    names = await player_names_for(session, guild_id, starter_ids)
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "chains.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
            "chains": chains,
            "names": names,
        },
    )


@router.get("/history/chain/{chain_id}", response_class=HTMLResponse)
async def chain_detail(
    chain_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_guild_id),
) -> HTMLResponse:
    summary = await history_service.chain_summary(session, guild_id, chain_id)
    uids: set[int] = set()
    if summary is not None:
        uids.update(uid for uid, _ in summary.contributors)
    names = await player_names_for(session, guild_id, uids)
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "chain_detail.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
            "summary": summary,
            "names": names,
        },
    )


@router.get("/history/sessions", response_class=HTMLResponse)
async def sessions_index(
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_guild_id),
    limit: int = 50,
) -> HTMLResponse:
    stmt = (
        select(Event.id, Event.created_at)
        .where(
            Event.guild_id == guild_id, Event.type == EventType.SESSION_START
        )
        .order_by(Event.id.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    sessions = [{"id": int(r[0]), "started_at": r[1]} for r in rows]
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "sessions.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
            "sessions": sessions,
        },
    )


@router.get("/history/session/{session_id}", response_class=HTMLResponse)
async def session_detail(
    session_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    guild_id: int = Depends(get_guild_id),
) -> HTMLResponse:
    summary = await history_service.session_summary(session, guild_id, session_id)
    uids: set[int] = set()
    if summary is not None:
        if summary.top_earner:
            uids.add(summary.top_earner[0])
        if summary.top_breaker:
            uids.add(summary.top_breaker[0])
    names = await player_names_for(session, guild_id, uids)
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "session_detail.html",
        {
            "request": request,
            "user": current_user(request),
            "guild_name": await guild_name_for(session, guild_id),
            "summary": summary,
            "names": names,
        },
    )
