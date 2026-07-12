"""FastAPI app factory.

The web layer shares the same SQLAlchemy models + services as the bot.
When launched from ``__main__``, the FastAPI app runs on the same event
loop as the Discord client; the sessionmaker is passed in so every
request opens its own DB session via the ``session_scope`` helper.

Auth is Discord OAuth2 (identify + guilds). Admin routes additionally
check :func:`stankbot.services.permission_service.is_admin` against the
authenticated user's Discord roles for the requested guild.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from collections import defaultdict
from importlib.metadata import version as pkg_version
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from starlette.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from stankbot.bot import StankBot
from stankbot.config import AppConfig
from stankbot.web import ws
from stankbot.web.routes import admin, api, auth, media_admin, media_api
from stankbot.web.tools import _LoginRedirect, _NotInGuild

log = logging.getLogger(__name__)
WEB_DIR = Path(os.environ.get("WEB_DIR", str(Path(__file__).parent / "frontend")))


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: type[Request]) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


class _RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-process sliding-window rate limiter keyed by session user_id."""

    def __init__(self, app, *, api_rpm: int = 120, admin_rpm: int = 30) -> None:
        super().__init__(app)
        self._api_rpm = api_rpm
        self._admin_rpm = admin_rpm
        self._windows: dict[str, list[float]] = defaultdict(list)

    def _check(self, key: str, limit: int) -> bool:
        now = time.monotonic()
        window = self._windows[key]
        window[:] = [t for t in window if now - t < 60.0]
        if len(window) >= limit:
            return False
        window.append(now)
        return True

    async def dispatch(self, request: Request, call_next: type[Request]) -> Response:
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        user = request.session.get("user")
        uid = str(user["id"]) if user else request.client.host if request.client else "anon"
        is_admin = path.startswith("/api/admin/")
        limit = self._admin_rpm if is_admin else self._api_rpm
        prefix = "admin" if is_admin else "api"
        if not self._check(f"{prefix}:{uid}", limit):
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        return await call_next(request)


class _SPAStaticFiles(StaticFiles):
    """Serve index.html for any unmatched path (SPA fallback)."""

    async def get_response(self, path: str, scope: dict[str, object]) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("", scope)
            raise

def build_app(
    config: AppConfig,
    engine: AsyncEngine,
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
    *,
    bot: StankBot | None = None,
) -> FastAPI:
    app = FastAPI(title="StankBot", docs_url=None, redoc_url=None)

    secret = (
        config.web_secret_key.get_secret_value()
        if config.web_secret_key is not None
        else secrets.token_urlsafe(32)
    )
    # Starlette middleware is LIFO: last added = outermost.
    # Execution order: SecurityHeaders → Session → RateLimit → app
    if config.env != "dev-mock":
        app.add_middleware(_RateLimitMiddleware, api_rpm=120, admin_rpm=30)
    app.add_middleware(SessionMiddleware, secret_key=secret, same_site="lax")
    app.add_middleware(_SecurityHeadersMiddleware)

    try:
        app.state.app_version = pkg_version("stankbot")
    except Exception:
        app.state.app_version = "0.0.0"

    app.state.config = config
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.bot = bot
    if bot is not None:
        app.state.bot_guilds = bot._bot_guilds
    else:
        app.state.bot_guilds = []

    app.include_router(ws.router)
    app.include_router(api.router)
    app.include_router(admin.router)
    app.include_router(auth.router)
    app.include_router(media_api.router)
    app.include_router(media_admin.router)

    # Share the media registry from the bot (if available).
    # In dev-mock mode, always use mock providers regardless.
    if config.env == "dev-mock":
        from stankbot.services.media_providers import MediaProviderRegistry
        from stankbot.services.media_providers.mock_providers import (
            MockSpotifyProvider,
            MockYouTubeProvider,
        )

        registry = MediaProviderRegistry()
        registry.register(MockYouTubeProvider())
        registry.register(MockSpotifyProvider())
        app.state.media_registry = registry
        log.info("Mock media providers registered (dev-mock)")
    elif bot is not None and hasattr(bot, "media_registry"):
        app.state.media_registry = bot.media_registry
    else:
        from stankbot.services.media_providers import MediaProviderRegistry

        app.state.media_registry = MediaProviderRegistry()

    @app.get("/healthz", include_in_schema=False)
    async def _healthz() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get("/api/version", include_in_schema=False)
    async def _version() -> JSONResponse:
        return JSONResponse({"version": app.state.app_version})

    if config.env == "dev-mock":
        from stankbot.web.routes import mock_events, mock_media

        app.include_router(mock_events.router)
        app.include_router(mock_media.router)
        log.info("Mock event API mounted at /api/mock")

    @app.exception_handler(_LoginRedirect)
    async def _login_redirect_handler(_: Request, exc: _LoginRedirect) -> Response:
        return exc.response

    @app.exception_handler(_NotInGuild)
    async def _not_in_guild_handler(_: Request, exc: _NotInGuild) -> Response:
        return exc.response

    build_dir = WEB_DIR / "build"
    if build_dir.is_dir() and (build_dir / "index.html").is_file():
        app.mount("/", _SPAStaticFiles(directory=str(build_dir), html=True), name="static")

    return app
