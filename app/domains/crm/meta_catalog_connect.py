"""Connecting the Meta catalogue by logging in with Facebook (F11).

Same handshake as connecting a Facebook Page (``facebook.connect_service``),
with the catalogue permissions: code → long-lived user token → the
catalogues of the businesses that user granted. One catalogue connects right
away. Several wait in Redis for ten minutes, token included, until the admin
picks one, so no token ever reaches the browser or a URL.

The user token lasts about 60 days; when Meta stops accepting it, the
background sync keeps the error and the panel asks to connect again. Pasting
a system user's token (``meta_catalog.connect``) stays as the manual way.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from typing import Any

from redis import asyncio as redis_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.oauth_state import sign_oauth_state, verify_oauth_state
from app.domains.crm import meta_catalog as catalog
from app.domains.instagram import oauth
from app.domains.integrations.models import IntegrationsHook

FLOW = "meta_catalog"
PENDING_SECONDS = 600
# ``business_management`` lists the catalogues of the user's businesses.
SCOPES: tuple[str, ...] = ("catalog_management", "business_management")


def _pending_key(account_id: int, nonce: str) -> str:
    return f"meta_catalogs:{account_id}:{nonce}"


def _redis() -> Any:
    return redis_asyncio.from_url(get_settings().redis_url, decode_responses=True)


def start_oauth(account_id: int) -> str:
    """The Facebook dialog URL for connecting the catalogue."""
    if not catalog.login_available():
        raise catalog.CatalogError("login_unavailable")
    return oauth.build_facebook_login_url(
        redirect_uri=get_settings().meta_oauth_redirect_uri,
        state=sign_oauth_state(account_id, flow=FLOW),
        scopes=SCOPES,
    )


async def list_catalogs(user_token: str) -> list[dict[str, Any]]:
    """The catalogues the user can manage, from every business they granted."""
    body = await catalog._graph(
        "GET",
        "me/businesses",
        token=user_token,
        params={
            "fields": "id,name,owned_product_catalogs{id,name},client_product_catalogs{id,name}",
            "limit": "100",
        },
    )
    found: dict[str, dict[str, Any]] = {}
    for business in body.get("data") or []:
        if not isinstance(business, dict):
            continue
        for edge in ("owned_product_catalogs", "client_product_catalogs"):
            rows = (business.get(edge) or {}).get("data") or []
            for row in rows:
                if isinstance(row, dict) and row.get("id"):
                    found.setdefault(
                        str(row["id"]),
                        {
                            "id": str(row["id"]),
                            "name": row.get("name"),
                            "business": business.get("name"),
                        },
                    )
    return list(found.values())


async def _connect(
    session: AsyncSession,
    *,
    account_id: int,
    catalog_id: str,
    user_token: str,
    expires_at: int | None,
) -> IntegrationsHook:
    return await catalog.connect(
        session,
        account_id=account_id,
        catalog_id=catalog_id,
        access_token=user_token,
        login={"via": "facebook", "expires_at": expires_at},
    )


async def complete_oauth(session: AsyncSession, *, code: str, state: str) -> dict[str, Any]:
    """Finish the handshake: ``{"connected": True}``, or ``pick`` with the
    nonce of the catalogues waiting for the admin's choice."""
    payload = verify_oauth_state(state)
    if payload.get("flow") != FLOW:
        raise catalog.CatalogError("refused")
    account_id = int(payload["account_id"])
    redirect_uri = get_settings().meta_oauth_redirect_uri
    short = await oauth.exchange_code_for_token(code=code, redirect_uri=redirect_uri)
    if not short.ok or not short.access_token:
        raise catalog.CatalogError("refused", short.error_message)
    long = await oauth.exchange_for_long_lived(short_token=short.access_token)
    if not long.ok or not long.access_token:
        raise catalog.CatalogError("refused", long.error_message)
    expires_at = (
        int(datetime.now(UTC).timestamp()) + int(long.expires_in) if long.expires_in else None
    )
    catalogs = await list_catalogs(long.access_token)
    if not catalogs:
        raise catalog.CatalogError("no_catalogs")
    if len(catalogs) == 1:
        await _connect(
            session,
            account_id=account_id,
            catalog_id=catalogs[0]["id"],
            user_token=long.access_token,
            expires_at=expires_at,
        )
        return {"connected": True}
    nonce = secrets.token_urlsafe(16)
    client = _redis()
    try:
        await client.set(
            _pending_key(account_id, nonce),
            json.dumps(
                {"user_token": long.access_token, "expires_at": expires_at, "catalogs": catalogs}
            ),
            ex=PENDING_SECONDS,
        )
    finally:
        await client.aclose()
    return {"pick": nonce}


async def _pending(account_id: int, nonce: str) -> dict[str, Any]:
    client = _redis()
    try:
        raw = await client.get(_pending_key(account_id, nonce))
    finally:
        await client.aclose()
    if not raw:
        raise catalog.CatalogError("pick_expired")
    return json.loads(raw)


async def pending_catalogs(*, account_id: int, nonce: str) -> list[dict[str, Any]]:
    """The catalogues waiting for the admin's choice, without the token."""
    return (await _pending(account_id, nonce))["catalogs"]


async def connect_pending(
    session: AsyncSession, *, account_id: int, nonce: str, catalog_id: str
) -> IntegrationsHook:
    pending = await _pending(account_id, nonce)
    if not any(row["id"] == catalog_id for row in pending["catalogs"]):
        raise catalog.CatalogError("catalog_id")
    hook = await _connect(
        session,
        account_id=account_id,
        catalog_id=catalog_id,
        user_token=pending["user_token"],
        expires_at=pending.get("expires_at"),
    )
    client = _redis()
    try:
        await client.delete(_pending_key(account_id, nonce))
    finally:
        await client.aclose()
    return hook


__all__ = [
    "FLOW",
    "SCOPES",
    "complete_oauth",
    "connect_pending",
    "list_catalogs",
    "pending_catalogs",
    "start_oauth",
]
