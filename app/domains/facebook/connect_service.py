"""Connecting a Facebook Page by logging in with Facebook.

Same handshake as the Instagram channel (``instagram.oauth``), with the Page
permissions: code → long-lived user token → the Pages that user granted, each
with its own non-expiring Page token. One Page connects right away. Several
wait in Redis for ten minutes, tokens included, until the admin picks one, so
no token ever reaches the browser or a URL.

Reconnecting a Page refreshes its tokens on the same inbox. A Page connected
to another account stays an error, because the inbound webhook resolves a Page
by its id alone.
"""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any

from redis import asyncio as redis_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException
from app.core.oauth_state import sign_oauth_state, verify_oauth_state
from app.domains.accounts.models import Account
from app.domains.inboxes.models import CHANNEL_TYPE_FACEBOOK, FacebookPage, Inbox
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram import oauth

log = logging.getLogger(__name__)

FLOW = "facebook_page"
PENDING_SECONDS = 600


def _unprocessable(message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=422, detail={"message": message})


def _pending_key(account_id: int, nonce: str) -> str:
    return f"facebook_pages:{account_id}:{nonce}"


def _redis() -> Any:
    return redis_asyncio.from_url(get_settings().redis_url, decode_responses=True)


def start_page_oauth(account_id: int) -> str:
    """The Facebook dialog URL for connecting Pages. 422 when the
    installation is missing settings."""
    settings = get_settings()
    named = (
        ("META_APP_ID", settings.meta_app_id),
        ("META_APP_SECRET", settings.meta_app_secret),
        ("META_OAUTH_REDIRECT_URI", settings.meta_oauth_redirect_uri),
    )
    missing = [name for name, value in named if not value]
    if missing:
        raise _unprocessable(
            f"Falta configurar Facebook Login: {', '.join(missing)}. "
            "Cargalos en Ajustes → Instalación."
        )
    return oauth.build_facebook_login_url(
        redirect_uri=settings.meta_oauth_redirect_uri,
        state=sign_oauth_state(account_id, flow=FLOW),
        scopes=oauth.FACEBOOK_PAGE_SCOPES,
    )


async def _connect_page(
    session: AsyncSession,
    *,
    account_id: int,
    page_id: str,
    name: str | None,
    page_token: str,
    user_token: str,
) -> dict[str, Any]:
    pages = (
        await session.exec(select(FacebookPage).where(FacebookPage.page_id == page_id))
    ).all()
    if any(page.account_id != account_id for page in pages):
        raise _unprocessable(
            "Esa Página ya está conectada en otra cuenta de AloStudio. "
            "Desconectala de allí primero."
        )
    reconnected = bool(pages)
    if pages:
        page = pages[0]
        page.page_access_token = page_token
        page.user_access_token = user_token
        session.add(page)
        await session.flush()
        inbox = (
            await session.exec(
                select(Inbox).where(
                    Inbox.channel_type == CHANNEL_TYPE_FACEBOOK,
                    Inbox.channel_id == page.id,
                )
            )
        ).first()
    else:
        account = await session.get(Account, account_id)
        if account is None:
            raise ChatwootHTTPException(
                status_code=404, detail={"error": "Resource could not be found"}
            )
        inbox = (
            await InboxBuilder(
                session,
                InboxBuilderParams(
                    account=account,
                    name=name or "Facebook",
                    channel_type="facebook",
                    channel_params={
                        "page_id": page_id,
                        "page_access_token": page_token,
                        "user_access_token": user_token,
                    },
                ),
            ).perform()
        ).inbox
    # Best-effort: a failure leaves a Page that publishes but receives no
    # messages, which an admin can fix by connecting again.
    subscribed, error = await oauth.subscribe_page_webhooks(
        page_id=page_id, page_token=page_token
    )
    if not subscribed:
        log.warning("facebook.subscribe_page_failed page_id=%s err=%s", page_id, error)
    return {
        "inbox_id": inbox.id if inbox else None,
        "page_id": page_id,
        "name": name,
        "reconnected": reconnected,
        "subscribed": subscribed,
    }


async def complete_page_oauth(
    session: AsyncSession, *, code: str, state: str
) -> dict[str, Any]:
    """Finish the handshake: the Page connected (``inbox_id``), or ``pick``
    with the nonce of the Pages waiting for the admin's choice."""
    payload = verify_oauth_state(state)
    if payload.get("flow") != FLOW:
        raise ChatwootHTTPException(
            status_code=401, detail={"error": "oauth flow mismatch"}
        )
    account_id = int(payload["account_id"])
    short = await oauth.exchange_code_for_token(
        code=code, redirect_uri=get_settings().meta_oauth_redirect_uri
    )
    if not short.ok or not short.access_token:
        raise _unprocessable(short.error_message or "Meta rechazó el código de autorización.")
    long = await oauth.exchange_for_long_lived(short_token=short.access_token)
    if not long.ok or not long.access_token:
        raise _unprocessable(long.error_message or "Meta no renovó el acceso.")
    listed = await oauth.list_pages(user_token=long.access_token)
    if not listed.ok:
        raise _unprocessable(listed.error_message or "No se pudieron leer las Páginas.")
    pages = [page for page in listed.pages if page.access_token]
    if not pages:
        raise _unprocessable(
            "Meta no devolvió ninguna Página. Volvé a conectar y elegí al menos "
            "una en la pantalla de Facebook."
        )
    if len(pages) == 1:
        return await _connect_page(
            session,
            account_id=account_id,
            page_id=pages[0].id,
            name=pages[0].name,
            page_token=pages[0].access_token,
            user_token=long.access_token,
        )
    nonce = secrets.token_urlsafe(16)
    client = _redis()
    try:
        await client.set(
            _pending_key(account_id, nonce),
            json.dumps(
                {
                    "user_token": long.access_token,
                    "pages": [
                        {"id": p.id, "name": p.name, "token": p.access_token} for p in pages
                    ],
                }
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
        raise _unprocessable("La elección venció. Volvé a conectar con Facebook.")
    return json.loads(raw)


async def pending_pages(*, account_id: int, nonce: str) -> list[dict[str, Any]]:
    """The Pages waiting for the admin's choice, without their tokens."""
    pending = await _pending(account_id, nonce)
    return [{"id": page["id"], "name": page["name"]} for page in pending["pages"]]


async def connect_pending_page(
    session: AsyncSession, *, account_id: int, nonce: str, page_id: str
) -> dict[str, Any]:
    pending = await _pending(account_id, nonce)
    page = next((p for p in pending["pages"] if p["id"] == page_id), None)
    if page is None:
        raise _unprocessable("Esa Página no está entre las que autorizaste.")
    result = await _connect_page(
        session,
        account_id=account_id,
        page_id=page["id"],
        name=page["name"],
        page_token=page["token"],
        user_token=pending["user_token"],
    )
    client = _redis()
    try:
        await client.delete(_pending_key(account_id, nonce))
    finally:
        await client.aclose()
    return result


__all__ = [
    "FLOW",
    "complete_page_oauth",
    "connect_pending_page",
    "pending_pages",
    "start_page_oauth",
]
