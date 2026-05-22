"""Instagram connection service (I.10).

Connection capability tracking + the manual ("paste a token") connect
path. The OAuth flows (Facebook Login + Instagram Login) layer their
token-exchange on top of :func:`record_connection` once they have a
page/IG token.

Capability model: a ``channel_instagram`` row gets a 1:1
``instagram_channel_settings`` row recording ``login_type``. DELETE media
is only available on Facebook Login (verified against Meta docs), so the
delete path gates on :func:`can_delete_media`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException
from app.domains.instagram.models import (
    INSTAGRAM_CONNECT_METHODS,
    INSTAGRAM_LOGIN_TYPES,
    InstagramChannelSetting,
)


async def get_channel_setting(
    session: AsyncSession, *, channel_instagram_id: int
) -> InstagramChannelSetting | None:
    return (
        await session.exec(
            select(InstagramChannelSetting).where(
                InstagramChannelSetting.channel_instagram_id
                == channel_instagram_id
            )
        )
    ).first()


async def record_connection(
    session: AsyncSession,
    *,
    channel_instagram_id: int,
    login_type: str,
    connect_method: str = "manual",
    page_id: str | None = None,
) -> InstagramChannelSetting:
    """Upsert the settings row for a channel (idempotent on
    channel_instagram_id)."""
    if login_type not in INSTAGRAM_LOGIN_TYPES:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    f"login_type must be one of "
                    f"{', '.join(INSTAGRAM_LOGIN_TYPES)}"
                )
            },
        )
    if connect_method not in INSTAGRAM_CONNECT_METHODS:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "invalid connect_method"},
        )
    existing = await get_channel_setting(
        session, channel_instagram_id=channel_instagram_id
    )
    if existing is not None:
        existing.login_type = login_type
        existing.connect_method = connect_method
        if page_id is not None:
            existing.page_id = page_id
        session.add(existing)
        await session.flush()
        await session.refresh(existing)
        return existing
    row = InstagramChannelSetting(
        channel_instagram_id=channel_instagram_id,
        login_type=login_type,
        connect_method=connect_method,
        page_id=page_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def can_delete_media(
    session: AsyncSession, *, channel_instagram_id: int
) -> bool:
    """True when the channel's connection supports DELETE media.

    Facebook Login → yes. Instagram Login → no (Meta API limitation).
    A channel with no settings row (legacy / pre-I.10) defaults to
    *allowed* — those were created via the Phase 5e Facebook-page path.
    """
    setting = await get_channel_setting(
        session, channel_instagram_id=channel_instagram_id
    )
    if setting is None:
        return True
    return setting.login_type != "instagram"


async def connect_manual(
    session: AsyncSession,
    *,
    account: Any,
    name: str,
    instagram_id: str,
    access_token: str,
    login_type: str,
    expires_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Advanced/manual connect: create an Instagram inbox + channel from
    a pasted token (e.g. a permanent System User token) and record the
    ``login_type``.

    Returns ``{inbox_id, channel_instagram_id, instagram_id,
    login_type}``.
    """
    if login_type not in INSTAGRAM_LOGIN_TYPES:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    f"login_type must be one of "
                    f"{', '.join(INSTAGRAM_LOGIN_TYPES)}"
                )
            },
        )
    from app.domains.inboxes.service import (
        InboxBuilder,
        InboxBuilderParams,
    )

    channel_params: dict[str, Any] = {
        "instagram_id": instagram_id,
        "access_token": access_token,
    }
    if expires_at is not None:
        channel_params["expires_at"] = (
            expires_at.isoformat()
            if isinstance(expires_at, datetime)
            else expires_at
        )
    result = await InboxBuilder(
        session,
        InboxBuilderParams(
            account=account,
            name=name,
            channel_type="instagram",
            channel_params=channel_params,
        ),
    ).perform()

    await record_connection(
        session,
        channel_instagram_id=result.channel.id,
        login_type=login_type,
        connect_method="manual",
    )
    return {
        "inbox_id": result.inbox.id,
        "channel_instagram_id": result.channel.id,
        "instagram_id": result.channel.instagram_id,
        "login_type": login_type,
    }


# ---------------------------------------------------------------------------
# OAuth — signed state (CSRF + carries the account through the callback)
# ---------------------------------------------------------------------------
def _state_secret() -> bytes:
    return get_settings().secret_key.encode()


def sign_oauth_state(account_id: int, *, flow: str) -> str:
    """Sign ``{account_id, flow, nonce, ts}`` so the (account-less)
    callback can trust it. HMAC-SHA256 over the base64 payload with the
    app secret key."""
    payload = {
        "account_id": account_id,
        "flow": flow,
        "nonce": secrets.token_hex(8),
        "ts": int(time.time()),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    b = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    sig = hmac.new(
        _state_secret(), b.encode(), hashlib.sha256
    ).hexdigest()[:32]
    return f"{b}.{sig}"


def verify_oauth_state(state: str, *, max_age_seconds: int = 600) -> dict[str, Any]:
    """Verify the signed state → its payload, or 401."""
    try:
        b, sig = state.split(".", 1)
    except (ValueError, AttributeError):
        raise ChatwootHTTPException(
            status_code=401, detail={"error": "invalid oauth state"}
        ) from None
    expected = hmac.new(
        _state_secret(), b.encode(), hashlib.sha256
    ).hexdigest()[:32]
    if not hmac.compare_digest(expected, sig):
        raise ChatwootHTTPException(
            status_code=401, detail={"error": "invalid oauth state"}
        )
    try:
        raw = base64.urlsafe_b64decode(b + "=" * (-len(b) % 4))
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        raise ChatwootHTTPException(
            status_code=401, detail={"error": "invalid oauth state"}
        ) from None
    if int(time.time()) - int(payload.get("ts", 0)) > max_age_seconds:
        raise ChatwootHTTPException(
            status_code=401, detail={"error": "oauth state expired"}
        )
    return payload


# ---------------------------------------------------------------------------
# OAuth — Facebook Login flow
# ---------------------------------------------------------------------------
def start_facebook_oauth(account_id: int) -> str:
    """Build the Facebook Login dialog URL (with signed state) the admin
    is redirected to. 422 if Meta OAuth isn't configured."""
    from app.domains.instagram import oauth

    settings = get_settings()
    if not (settings.meta_app_id and settings.meta_oauth_redirect_uri):
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    "Meta OAuth not configured "
                    "(META_APP_ID / META_OAUTH_REDIRECT_URI)"
                )
            },
        )
    state = sign_oauth_state(account_id, flow="facebook")
    return oauth.build_facebook_login_url(
        redirect_uri=settings.meta_oauth_redirect_uri, state=state
    )


async def complete_facebook_oauth(
    session: AsyncSession,
    *,
    code: str,
    state: str,
    page_id: str | None = None,
) -> dict[str, Any]:
    """Finish the Facebook Login handshake: verify state, exchange the
    code for a (non-expiring) page token + IG id, create the inbox +
    channel, and record the connection.

    ``page_id`` optionally selects which Page when the user manages
    several; otherwise the first Page with a linked IG account wins.
    """
    from app.domains.accounts.models import Account
    from app.domains.instagram import oauth

    payload = verify_oauth_state(state)
    if payload.get("flow") != "facebook":
        raise ChatwootHTTPException(
            status_code=401, detail={"error": "oauth flow mismatch"}
        )
    account_id = int(payload["account_id"])
    account = await session.get(Account, account_id)
    if account is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )

    redirect_uri = get_settings().meta_oauth_redirect_uri

    short = await oauth.exchange_code_for_token(
        code=code, redirect_uri=redirect_uri
    )
    if not short.ok or not short.access_token:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": short.error_message or "code exchange failed",
                "code": short.error_code,
            },
        )
    long = await oauth.exchange_for_long_lived(
        short_token=short.access_token
    )
    if not long.ok or not long.access_token:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": long.error_message or "long-lived exchange failed",
                "code": long.error_code,
            },
        )
    pages = await oauth.list_pages(user_token=long.access_token)
    if not pages.ok:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": pages.error_message or "could not list pages",
                "code": pages.error_code,
            },
        )

    chosen = None
    if page_id:
        chosen = next((p for p in pages.pages if p.id == page_id), None)
    if chosen is None:
        chosen = next(
            (p for p in pages.pages if p.instagram_business_account_id),
            None,
        )
    if chosen is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    "no Facebook Page with a linked Instagram business "
                    "account was found"
                )
            },
        )

    ig_id = chosen.instagram_business_account_id
    if not ig_id:
        ig_id = await oauth.get_page_ig_account(
            page_id=chosen.id, page_token=chosen.access_token
        )
    if not ig_id:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": "selected Page has no linked Instagram account"
            },
        )

    from app.domains.inboxes.service import (
        InboxBuilder,
        InboxBuilderParams,
    )

    result = await InboxBuilder(
        session,
        InboxBuilderParams(
            account=account,
            name=chosen.name or "Instagram",
            channel_type="instagram",
            channel_params={
                "instagram_id": ig_id,
                "access_token": chosen.access_token,
            },
        ),
    ).perform()
    await record_connection(
        session,
        channel_instagram_id=result.channel.id,
        login_type="facebook",
        connect_method="oauth",
        page_id=chosen.id,
    )
    return {
        "inbox_id": result.inbox.id,
        "channel_instagram_id": result.channel.id,
        "instagram_id": ig_id,
        "login_type": "facebook",
        "page_id": chosen.id,
    }


# ---------------------------------------------------------------------------
# OAuth — Instagram Login flow (no Facebook Page; host graph.instagram.com)
# ---------------------------------------------------------------------------
def start_instagram_oauth(account_id: int) -> str:
    """Build the Instagram Login authorization URL (signed state).
    422 if the Instagram app isn't configured."""
    from app.domains.instagram import oauth

    settings = get_settings()
    if not (
        settings.meta_instagram_app_id and settings.meta_oauth_redirect_uri
    ):
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    "Instagram Login not configured "
                    "(META_INSTAGRAM_APP_ID / META_OAUTH_REDIRECT_URI)"
                )
            },
        )
    state = sign_oauth_state(account_id, flow="instagram")
    return oauth.build_instagram_login_url(
        redirect_uri=settings.meta_oauth_redirect_uri, state=state
    )


async def complete_instagram_oauth(
    session: AsyncSession, *, code: str, state: str
) -> dict[str, Any]:
    """Finish the Instagram Login handshake: code → IG user id +
    long-lived token → create the inbox + channel (login_type=instagram,
    so the delete path is gated off)."""
    from app.domains.accounts.models import Account
    from app.domains.instagram import oauth

    payload = verify_oauth_state(state)
    if payload.get("flow") != "instagram":
        raise ChatwootHTTPException(
            status_code=401, detail={"error": "oauth flow mismatch"}
        )
    account_id = int(payload["account_id"])
    account = await session.get(Account, account_id)
    if account is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    redirect_uri = get_settings().meta_oauth_redirect_uri

    short = await oauth.exchange_instagram_code(
        code=code, redirect_uri=redirect_uri
    )
    if not short.ok or not short.access_token or not short.user_id:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": short.error_message or "code exchange failed",
                "code": short.error_code,
            },
        )
    long = await oauth.exchange_instagram_long_lived(
        short_token=short.access_token
    )
    if not long.ok or not long.access_token:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": long.error_message or "long-lived exchange failed",
                "code": long.error_code,
            },
        )

    from app.domains.inboxes.service import (
        InboxBuilder,
        InboxBuilderParams,
    )

    result = await InboxBuilder(
        session,
        InboxBuilderParams(
            account=account,
            name="Instagram",
            channel_type="instagram",
            channel_params={
                "instagram_id": short.user_id,
                "access_token": long.access_token,
            },
        ),
    ).perform()
    await record_connection(
        session,
        channel_instagram_id=result.channel.id,
        login_type="instagram",
        connect_method="oauth",
    )
    return {
        "inbox_id": result.inbox.id,
        "channel_instagram_id": result.channel.id,
        "instagram_id": short.user_id,
        "login_type": "instagram",
    }


# ---------------------------------------------------------------------------
# OAuth — flow dispatcher (the account-less callback delegates here)
# ---------------------------------------------------------------------------
async def complete_oauth(
    session: AsyncSession,
    *,
    code: str,
    state: str,
    page_id: str | None = None,
) -> dict[str, Any]:
    """Verify the state, read its ``flow``, and run the matching
    completion. Used by the OAuth callback endpoint."""
    payload = verify_oauth_state(state)
    flow = payload.get("flow")
    if flow == "facebook":
        return await complete_facebook_oauth(
            session, code=code, state=state, page_id=page_id
        )
    if flow == "instagram":
        return await complete_instagram_oauth(
            session, code=code, state=state
        )
    raise ChatwootHTTPException(
        status_code=401, detail={"error": "unknown oauth flow"}
    )


__all__ = [
    "can_delete_media",
    "complete_facebook_oauth",
    "complete_instagram_oauth",
    "complete_oauth",
    "connect_manual",
    "get_channel_setting",
    "record_connection",
    "sign_oauth_state",
    "start_facebook_oauth",
    "start_instagram_oauth",
    "verify_oauth_state",
]
