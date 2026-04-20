"""Shared FastAPI dependencies — DB sessions, Jinja templates, auth."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stankbot.db.engine import session_scope
from stankbot.db.models import Guild, Player

if TYPE_CHECKING:
    from stankbot.config import AppConfig


def get_templates(request: Request) -> Jinja2Templates:
    templates = getattr(request.app.state, "_templates", None)
    if templates is None:
        templates = Jinja2Templates(directory=str(request.app.state.templates_dir))
        request.app.state._templates = templates
    return templates


def get_config(request: Request) -> AppConfig:
    return request.app.state.config


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    factory = request.app.state.session_factory
    async with session_scope(factory) as session:
        yield session


def current_user(request: Request) -> dict[str, Any] | None:
    """Returns ``{"id": int, "username": str, "avatar": str}`` or ``None``.

    Populated by :mod:`stankbot.web.routes.auth` after successful OAuth.
    """
    user = request.session.get("user")
    if user is None:
        return None
    return dict(user)


class _LoginRedirect(HTTPException):
    """Carries a RedirectResponse so the app's exception handler can
    send a browser-friendly 302 instead of a JSON 401.
    """

    def __init__(self, response: RedirectResponse) -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="login required")
        self.response = response


class _NotInGuild(HTTPException):
    """Carries a 403 TemplateResponse for users who are not guild members."""

    def __init__(self, response: Any) -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail="not in guild")
        self.response = response


def _is_guild_member(request: Request, guild_id: int) -> bool:
    """Return True if the session user is a member of the given guild."""
    guilds = request.session.get("guilds", [])
    return any(int(g.get("id", 0)) == guild_id for g in guilds)


def require_login(request: Request) -> dict[str, Any]:
    user = current_user(request)
    if user is None:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            next_url = str(request.url.path)
            if request.url.query:
                next_url += f"?{request.url.query}"
            raise _LoginRedirect(
                RedirectResponse(
                    url=f"/auth/login?next={quote(next_url)}", status_code=302
                )
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="login required"
        )
    return user


def require_guild_member(request: Request) -> dict[str, Any]:
    """Dependency for public dashboard routes.

    Redirects unauthenticated visitors to ``/`` (which shows the login UI).
    Raises ``_NotInGuild`` (rendered as ``unauthorized.html``) for users who
    are logged in but not a member of the configured guild.
    """
    user = current_user(request)
    if user is None:
        next_url = str(request.url.path)
        if request.url.query:
            next_url += f"?{request.url.query}"
        raise _LoginRedirect(
            RedirectResponse(url=f"/auth/login?next={quote(next_url)}", status_code=302)
        )
    config: AppConfig = request.app.state.config
    if not _is_guild_member(request, config.default_guild_id):
        templates = get_templates(request)
        raise _NotInGuild(
            templates.TemplateResponse(
                request,
                "unauthorized.html",
                {"request": request, "user": user},
                status_code=403,
            )
        )
    return user


async def guild_name_for(session: AsyncSession, guild_id: int) -> str:
    name = (
        await session.execute(select(Guild.name).where(Guild.id == guild_id))
    ).scalar_one_or_none()
    return name or f"Guild {guild_id}"


async def player_names_for(
    session: AsyncSession, guild_id: int, user_ids: Iterable[int]
) -> dict[int, str]:
    ids = [int(u) for u in user_ids if u is not None]
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(Player.user_id, Player.display_name).where(
                Player.guild_id == guild_id, Player.user_id.in_(ids)
            )
        )
    ).all()
    return {int(uid): (name or str(uid)) for uid, name in rows}


def get_guild_id(request: Request) -> int:
    """The configured default guild for the single-guild dashboard."""
    config: AppConfig = request.app.state.config
    return config.default_guild_id


async def require_guild_admin(
    request: Request,
    session: AsyncSession = Depends(get_db),
    user: dict[str, Any] = Depends(require_login),
) -> dict[str, Any]:
    """Verify the session-user is an admin of the configured guild.

    Uses :class:`stankbot.services.permission_service.PermissionService`
    with the role list cached in the user's session (populated at login
    time from Discord's ``/users/@me/guilds`` response — which includes
    ``permissions``). Server-side role lookup would require a full
    member fetch through the bot, which is overkill for the dashboard.
    """
    from stankbot.services.permission_service import PermissionService

    config: AppConfig = request.app.state.config
    guild_id = config.default_guild_id

    guilds = request.session.get("guilds", [])
    def _unauthorized() -> _NotInGuild:
        templates = get_templates(request)
        return _NotInGuild(
            templates.TemplateResponse(
                request,
                "unauthorized.html",
                {"request": request, "user": user},
                status_code=403,
            )
        )

    match = next((g for g in guilds if int(g.get("id", 0)) == guild_id), None)
    if match is None:
        raise _unauthorized()

    perms = int(match.get("permissions", 0))
    has_manage_guild = bool(perms & 0x20)

    svc = PermissionService(session, owner_id=config.owner_id)
    is_admin = await svc.is_admin(
        guild_id,
        int(user["id"]),
        [],
        has_manage_guild=has_manage_guild,
    )
    if not is_admin:
        raise _unauthorized()
    return user
