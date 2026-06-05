"""MangaDex OAuth2 (personal client) login + follows sync.

Flow: the user registers a personal client at mangadex.org (Settings -> API
Clients) and supplies its client id/secret plus their account login. We do the
password grant **once**, then keep only the refresh token + client credentials
in the OS keychain and refresh access tokens silently (they live 15 min).

Used only for account features (reading your follows). Image downloads never
carry these tokens.
"""

from __future__ import annotations

import time

import httpx

from app.providers.base import MangaSummary
from app.providers.mangadex import API_BASE, summary_from_item
from app.services import secrets

AUTH_URL = "https://auth.mangadex.org/realms/mangadex/protocol/openid-connect/token"

# Keychain keys.
_K_CLIENT_ID = "md_client_id"
_K_CLIENT_SECRET = "md_client_secret"
_K_REFRESH = "md_refresh_token"
_K_USERNAME = "md_username"

# In-memory access-token cache (never persisted; access tokens are short-lived).
_access: dict = {"token": None, "exp": 0.0}


class AuthError(Exception):
    """Raised when login/refresh fails, with a user-friendly message."""


def is_logged_in() -> bool:
    return secrets.get_secret(_K_REFRESH) is not None


def username() -> str | None:
    return secrets.get_secret(_K_USERNAME)


def logout() -> None:
    for key in (_K_CLIENT_ID, _K_CLIENT_SECRET, _K_REFRESH, _K_USERNAME):
        secrets.delete_secret(key)
    _access["token"] = None
    _access["exp"] = 0.0


def _store_tokens(payload: dict) -> None:
    _access["token"] = payload["access_token"]
    # Refresh ~30s early to avoid using a token that expires mid-request.
    _access["exp"] = time.time() + float(payload.get("expires_in", 900)) - 30
    if payload.get("refresh_token"):
        secrets.set_secret(_K_REFRESH, payload["refresh_token"])


def _friendly_error(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        desc = body.get("error_description") or body.get("error") or resp.text
    except Exception:
        desc = resp.text
    if resp.status_code in (400, 401):
        return f"MangaDex rejected the credentials ({desc}). Check the client id/secret and login."
    return f"MangaDex auth failed ({resp.status_code}): {desc}"


async def login(
    client_id: str, client_secret: str, username_: str, password: str, *, user_agent: str
) -> None:
    """Password grant (run once). Stores refresh token + client creds; the
    password is used here and never persisted."""
    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": user_agent}) as c:
        resp = await c.post(
            AUTH_URL,
            data={
                "grant_type": "password",
                "username": username_,
                "password": password,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
    if resp.status_code != 200:
        raise AuthError(_friendly_error(resp))
    secrets.set_secret(_K_CLIENT_ID, client_id)
    secrets.set_secret(_K_CLIENT_SECRET, client_secret)
    secrets.set_secret(_K_USERNAME, username_)
    _store_tokens(resp.json())


async def get_access_token(*, user_agent: str) -> str | None:
    """Return a valid access token, refreshing via the stored refresh token if
    needed. Returns None if not logged in or the refresh has expired."""
    if not is_logged_in():
        return None
    if _access["token"] and time.time() < _access["exp"]:
        return _access["token"]
    client_id = secrets.get_secret(_K_CLIENT_ID)
    client_secret = secrets.get_secret(_K_CLIENT_SECRET)
    refresh = secrets.get_secret(_K_REFRESH)
    if not (client_id and client_secret and refresh):
        return None
    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": user_agent}) as c:
        resp = await c.post(
            AUTH_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
    if resp.status_code != 200:
        return None  # refresh expired -> caller should prompt re-login
    _store_tokens(resp.json())
    return _access["token"]


async def fetch_follows(access_token: str, *, user_agent: str) -> list[MangaSummary]:
    """All manga the authenticated user follows (paginated)."""
    results: list[MangaSummary] = []
    offset = 0
    limit = 100
    async with httpx.AsyncClient(
        base_url=API_BASE,
        timeout=30.0,
        headers={"Authorization": f"Bearer {access_token}", "User-Agent": user_agent},
        follow_redirects=True,
    ) as c:
        while True:
            resp = await c.get(
                "/user/follows/manga",
                params={"limit": limit, "offset": offset, "includes[]": ["cover_art"]},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", [])
            results.extend(summary_from_item(item) for item in items)
            offset += limit
            if not items or offset >= data.get("total", 0):
                break
    return results
