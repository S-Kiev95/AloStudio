"""Instagram OAuth — token exchange HTTP client (I.10).

Pure functions for the **Facebook Login** flow (host
``graph.facebook.com``). Like the rest of the IG clients they never
raise — every call returns a structured result so the connect service
can drive the handshake deterministically.

Handshake (Facebook Login):

  1. Redirect the admin to the login dialog (:func:`build_facebook_login_url`).
  2. Meta redirects back with ``?code`` → :func:`exchange_code_for_token`
     (short-lived user token).
  3. :func:`exchange_for_long_lived` → ~60-day user token.
  4. :func:`list_pages` → the Pages + their (non-expiring) page tokens +
     linked IG business account.
  5. :func:`get_page_ig_account` — fallback when the page didn't expand
     ``instagram_business_account`` inline.

App credentials come from ``settings.meta_app_id`` / ``meta_app_secret``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

# Facebook Login scopes for IG publishing + moderation (verified spec).
FACEBOOK_LOGIN_SCOPES: tuple[str, ...] = (
    "instagram_basic",
    "instagram_content_publish",
    "instagram_manage_comments",
    "instagram_manage_insights",
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_metadata",
    "business_management",
)

# Instagram Login scopes (the ``instagram_business_*`` family) — no
# Facebook Page required. DELETE media is NOT available on this flow.
INSTAGRAM_LOGIN_SCOPES: tuple[str, ...] = (
    "instagram_business_basic",
    "instagram_business_content_publish",
    "instagram_business_manage_comments",
    "instagram_business_manage_insights",
)


# ---------------------------------------------------------------------------
# Result objects
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class OAuthTokenResult:
    ok: bool
    access_token: str | None = None
    expires_in: int | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class PageInfo:
    id: str
    name: str | None
    access_token: str
    instagram_business_account_id: str | None = None


@dataclass(slots=True)
class PagesResult:
    ok: bool
    pages: list[PageInfo] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class InstagramTokenResult:
    """Instagram Login token exchange — carries the IG user id (the
    professional account id we publish to)."""

    ok: bool
    access_token: str | None = None
    user_id: str | None = None
    expires_in: int | None = None
    error_code: str | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _base() -> str:
    return f"https://graph.facebook.com/{get_settings().meta_graph_api_version}"


def _dialog_base() -> str:
    return f"https://www.facebook.com/{get_settings().meta_graph_api_version}"


def _extract_error(resp: httpx.Response) -> tuple[str | None, str | None]:
    try:
        payload = resp.json()
    except ValueError:
        return str(resp.status_code), resp.text[:500]
    err = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(err, dict):
        return str(resp.status_code), resp.text[:500]
    code = err.get("code")
    message = err.get("message", "")
    return (
        str(code) if code is not None else str(resp.status_code),
        message[:500],
    )


# ---------------------------------------------------------------------------
# Step 1 — login dialog URL
# ---------------------------------------------------------------------------
def build_facebook_login_url(*, redirect_uri: str, state: str) -> str:
    """The Facebook Login dialog URL the admin's browser is sent to."""
    settings = get_settings()
    query = urlencode(
        {
            "client_id": settings.meta_app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "scope": ",".join(FACEBOOK_LOGIN_SCOPES),
        }
    )
    return f"{_dialog_base()}/dialog/oauth?{query}"


# ---------------------------------------------------------------------------
# Step 2 — code → short-lived user token
# ---------------------------------------------------------------------------
async def exchange_code_for_token(
    *, code: str, redirect_uri: str
) -> OAuthTokenResult:
    settings = get_settings()
    params = {
        "client_id": settings.meta_app_id,
        "client_secret": settings.meta_app_secret,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    return await _token_get(f"{_base()}/oauth/access_token", params)


# ---------------------------------------------------------------------------
# Step 3 — short → long-lived user token
# ---------------------------------------------------------------------------
async def exchange_for_long_lived(*, short_token: str) -> OAuthTokenResult:
    settings = get_settings()
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": settings.meta_app_id,
        "client_secret": settings.meta_app_secret,
        "fb_exchange_token": short_token,
    }
    return await _token_get(f"{_base()}/oauth/access_token", params)


async def _token_get(url: str, params: dict[str, Any]) -> OAuthTokenResult:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        return OAuthTokenResult(
            ok=False,
            error_code="transport_error",
            # Use the exception CLASS name, never str(exc), so a secret can
            # never leak into a persisted/surfaced error (IG-2 hardening).
            error_message=type(exc).__name__,
        )
    if resp.status_code >= 400:
        code, message = _extract_error(resp)
        return OAuthTokenResult(
            ok=False, error_code=code, error_message=message
        )
    try:
        payload = resp.json()
    except ValueError:
        return OAuthTokenResult(
            ok=False, error_code="bad_json", error_message=resp.text[:500]
        )
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not token:
        return OAuthTokenResult(
            ok=False,
            error_code="no_access_token",
            error_message=str(payload)[:500],
        )
    return OAuthTokenResult(
        ok=True,
        access_token=str(token),
        expires_in=payload.get("expires_in"),
    )


# ---------------------------------------------------------------------------
# Step 4 — list pages (+ linked IG accounts)
# ---------------------------------------------------------------------------
async def list_pages(*, user_token: str) -> PagesResult:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{_base()}/me/accounts",
                params={
                    "fields": "id,name,access_token,instagram_business_account",
                    "access_token": user_token,
                },
            )
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        return PagesResult(
            ok=False,
            error_code="transport_error",
            # Use the exception CLASS name, never str(exc), so a secret can
            # never leak into a persisted/surfaced error (IG-2 hardening).
            error_message=type(exc).__name__,
        )
    if resp.status_code >= 400:
        code, message = _extract_error(resp)
        return PagesResult(ok=False, error_code=code, error_message=message)
    try:
        payload = resp.json()
    except ValueError:
        return PagesResult(
            ok=False, error_code="bad_json", error_message=resp.text[:500]
        )
    pages: list[PageInfo] = []
    for raw in (payload.get("data") or []) if isinstance(payload, dict) else []:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        iba = raw.get("instagram_business_account")
        iba_id = (
            str(iba["id"])
            if isinstance(iba, dict) and iba.get("id")
            else None
        )
        pages.append(
            PageInfo(
                id=str(raw["id"]),
                name=raw.get("name"),
                access_token=str(raw.get("access_token") or ""),
                instagram_business_account_id=iba_id,
            )
        )
    return PagesResult(ok=True, pages=pages)


# ---------------------------------------------------------------------------
# Step 5 — IG account for a page (fallback)
# ---------------------------------------------------------------------------
async def get_page_ig_account(
    *, page_id: str, page_token: str
) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_base()}/{page_id}",
                params={
                    "fields": "instagram_business_account",
                    "access_token": page_token,
                },
            )
    except (httpx.RequestError, httpx.TimeoutException):
        return None
    if resp.status_code >= 400:
        return None
    try:
        payload = resp.json()
    except ValueError:
        return None
    iba = payload.get("instagram_business_account") if isinstance(payload, dict) else None
    if isinstance(iba, dict) and iba.get("id"):
        return str(iba["id"])
    return None


# ---------------------------------------------------------------------------
# Instagram Login flow (host graph.instagram.com — no Facebook Page)
# ---------------------------------------------------------------------------
def build_instagram_login_url(*, redirect_uri: str, state: str) -> str:
    """The Instagram Login authorization URL (no Facebook Page needed)."""
    settings = get_settings()
    query = urlencode(
        {
            "client_id": settings.meta_instagram_app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "scope": ",".join(INSTAGRAM_LOGIN_SCOPES),
        }
    )
    return f"https://www.instagram.com/oauth/authorize?{query}"


async def exchange_instagram_code(
    *, code: str, redirect_uri: str
) -> InstagramTokenResult:
    """``POST https://api.instagram.com/oauth/access_token`` — code →
    short-lived token + the IG user id."""
    settings = get_settings()
    body = {
        "client_id": settings.meta_instagram_app_id,
        "client_secret": settings.meta_instagram_app_secret,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code": code,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.instagram.com/oauth/access_token", data=body
            )
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        return InstagramTokenResult(
            ok=False,
            error_code="transport_error",
            # Use the exception CLASS name, never str(exc), so a secret can
            # never leak into a persisted/surfaced error (IG-2 hardening).
            error_message=type(exc).__name__,
        )
    if resp.status_code >= 400:
        code_s, message = _extract_error(resp)
        return InstagramTokenResult(
            ok=False, error_code=code_s, error_message=message
        )
    try:
        payload = resp.json()
    except ValueError:
        return InstagramTokenResult(
            ok=False, error_code="bad_json", error_message=resp.text[:500]
        )
    # Newer API: flat ``{access_token, user_id, permissions}``.
    # Older: ``{"data": [{...}]}``.
    if (
        isinstance(payload, dict)
        and not payload.get("access_token")
        and isinstance(payload.get("data"), list)
        and payload["data"]
    ):
        payload = payload["data"][0]
    token = payload.get("access_token") if isinstance(payload, dict) else None
    user_id = payload.get("user_id") if isinstance(payload, dict) else None
    if not token or not user_id:
        return InstagramTokenResult(
            ok=False,
            error_code="no_access_token",
            error_message=str(payload)[:500],
        )
    return InstagramTokenResult(
        ok=True, access_token=str(token), user_id=str(user_id)
    )


async def exchange_instagram_long_lived(
    *, short_token: str
) -> InstagramTokenResult:
    """``GET https://graph.instagram.com/access_token`` with
    ``grant_type=ig_exchange_token`` → ~60-day token."""
    settings = get_settings()
    params = {
        "grant_type": "ig_exchange_token",
        "client_secret": settings.meta_instagram_app_secret,
        "access_token": short_token,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "https://graph.instagram.com/access_token", params=params
            )
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        return InstagramTokenResult(
            ok=False,
            error_code="transport_error",
            # Use the exception CLASS name, never str(exc), so a secret can
            # never leak into a persisted/surfaced error (IG-2 hardening).
            error_message=type(exc).__name__,
        )
    if resp.status_code >= 400:
        code_s, message = _extract_error(resp)
        return InstagramTokenResult(
            ok=False, error_code=code_s, error_message=message
        )
    try:
        payload = resp.json()
    except ValueError:
        return InstagramTokenResult(
            ok=False, error_code="bad_json", error_message=resp.text[:500]
        )
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not token:
        return InstagramTokenResult(
            ok=False,
            error_code="no_access_token",
            error_message=str(payload)[:500],
        )
    return InstagramTokenResult(
        ok=True,
        access_token=str(token),
        expires_in=payload.get("expires_in"),
    )


__all__ = [
    "FACEBOOK_LOGIN_SCOPES",
    "INSTAGRAM_LOGIN_SCOPES",
    "InstagramTokenResult",
    "OAuthTokenResult",
    "PageInfo",
    "PagesResult",
    "build_facebook_login_url",
    "build_instagram_login_url",
    "exchange_code_for_token",
    "exchange_for_long_lived",
    "exchange_instagram_code",
    "exchange_instagram_long_lived",
    "get_page_ig_account",
    "list_pages",
]
