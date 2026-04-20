"""Discord OAuth2 login flow.

Scopes requested: ``identify`` (so we know who logged in) + ``guilds``
(so we can tell which servers they're in, and which they admin).

On callback we stash a compact profile + the guild list into the
signed Starlette session cookie. Admin checks in :mod:`web.deps` read
the permissions integer out of that cached guild list.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from stankbot.web.deps import get_config

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger(__name__)


def _is_safe_redirect(url: str) -> bool:
    """Return True only for relative paths with no scheme or host component.

    Rejects protocol-relative URLs like ``//evil.com`` that start with ``/``
    but resolve to an external host.
    """
    parsed = urlparse(url)
    return url.startswith("/") and not parsed.scheme and not parsed.netloc

_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
_TOKEN_URL = "https://discord.com/api/oauth2/token"
_API_BASE = "https://discord.com/api/v10"


@router.get("/login")
async def login(
    request: Request,
    next: str | None = None,
    config=Depends(get_config),
) -> RedirectResponse:
    if config.oauth_client_secret is None:
        raise HTTPException(
            status_code=503,
            detail="OAuth not configured — set OAUTH_CLIENT_SECRET.",
        )
    state = secrets.token_urlsafe(24)
    request.session["oauth_state"] = state
    if next and _is_safe_redirect(next):
        request.session["oauth_next"] = next
    params = {
        "client_id": str(config.discord_app_id),
        "redirect_uri": config.oauth_redirect_uri,
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
        "prompt": "none",
    }
    return RedirectResponse(f"{_AUTHORIZE_URL}?{urlencode(params)}")


@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    config=Depends(get_config),
) -> RedirectResponse:
    expected = request.session.pop("oauth_state", None)
    if not state or state != expected:
        raise HTTPException(status_code=400, detail="state mismatch")
    if code is None:
        raise HTTPException(status_code=400, detail="missing code")
    if config.oauth_client_secret is None:
        raise HTTPException(status_code=503, detail="OAuth not configured")

    data = {
        "client_id": str(config.discord_app_id),
        "client_secret": config.oauth_client_secret.get_secret_value(),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.oauth_redirect_uri,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        tok = await client.post(
            _TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if tok.status_code != 200:
            log.warning("oauth token exchange failed: %s %s", tok.status_code, tok.text)
            raise HTTPException(status_code=400, detail="token exchange failed")
        access_token = tok.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        me_resp = await client.get(f"{_API_BASE}/users/@me", headers=headers)
        guilds_resp = await client.get(f"{_API_BASE}/users/@me/guilds", headers=headers)

    if me_resp.status_code != 200 or guilds_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="failed fetching profile")

    me: dict[str, Any] = me_resp.json()
    guilds: list[dict[str, Any]] = guilds_resp.json()

    request.session["user"] = {
        "id": int(me["id"]),
        "username": me.get("global_name") or me.get("username") or str(me["id"]),
        "avatar": me.get("avatar"),
    }
    request.session["guilds"] = [
        {
            "id": int(g["id"]),
            "name": g.get("name", ""),
            "icon": g.get("icon"),
            "permissions": int(g.get("permissions", 0)),
        }
        for g in guilds
    ]
    target = request.session.pop("oauth_next", None) or "/"
    return RedirectResponse(target, status_code=303)


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/", status_code=303)
