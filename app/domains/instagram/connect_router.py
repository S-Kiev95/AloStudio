"""Instagram connection HTTP endpoints (I.10).

Admin-only. Ships the **manual / advanced** connect path here; the OAuth
flows (Facebook Login + Instagram Login start/callback) layer on in the
follow-up commits using the same ``connect_service``.

Route map:
  * ``POST /api/v1/accounts/{id}/instagram_channels/connect_manual``
  * ``GET  /api/v1/accounts/{id}/instagram_channels/{channel_id}/settings``
"""

from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Path, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.instagram import connect_service
from app.domains.instagram.schemas import InstagramManualConnect

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/instagram_channels",
    tags=["instagram-connect"],
)

# OAuth callback is account-less (Meta redirects to one fixed URI; the
# account travels in the signed ``state``). Separate router, no prefix.
callback_router = APIRouter(tags=["instagram-connect"])


@router.post("/connect_manual", status_code=status.HTTP_200_OK)
async def connect_manual_endpoint(
    payload: InstagramManualConnect,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Create an Instagram inbox+channel from a pasted token and record
    its ``login_type`` (capabilities)."""
    return await connect_service.connect_manual(
        session,
        account=ctx.account,
        name=payload.name,
        instagram_id=payload.instagram_id,
        access_token=payload.access_token,
        login_type=payload.login_type,
        expires_at=payload.expires_at,
    )


@router.get("/connect/start")
async def connect_start(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Begin the Facebook Login OAuth — returns the dialog URL the
    admin's browser should be redirected to (with a signed state).
    Full feature set incl. delete media (requires a Facebook Page)."""
    assert ctx.account.id is not None
    authorize_url = connect_service.start_facebook_oauth(ctx.account.id)
    return {"authorize_url": authorize_url, "login_type": "facebook"}


@router.get("/connect/start_instagram")
async def connect_start_instagram(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Begin the Instagram Login OAuth — no Facebook Page required, but
    DELETE media is not available on this flow."""
    assert ctx.account.id is not None
    authorize_url = connect_service.start_instagram_oauth(ctx.account.id)
    return {"authorize_url": authorize_url, "login_type": "instagram"}


def _back_to_dashboard(account_id: int, **params: str) -> RedirectResponse:
    """303 back to the account's Instagram screen, carrying the outcome
    in the query string so the page can show a banner.

    Meta redirects the *browser* here, so JSON would leave the admin
    staring at a raw payload; ``app_base_url`` is the dashboard origin.
    """
    base = get_settings().app_base_url.rstrip("/")
    query = urlencode({k: v for k, v in params.items() if v})
    return RedirectResponse(
        f"{base}/accounts/{account_id}/instagram?{query}", status_code=303
    )


def _error_text(exc: ChatwootHTTPException) -> str:
    """Best-effort human message out of a Chatwoot-shaped error body."""
    detail = exc.detail
    if isinstance(detail, dict):
        for key in ("message", "error"):
            value = detail.get(key)
            if isinstance(value, str) and value:
                return value
    return str(detail)


@callback_router.get("/api/v1/instagram/oauth/callback")
async def oauth_callback(
    session: Annotated[AsyncSession, Depends(get_session)],
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    page_id: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> Response:
    """Meta's OAuth redirect target. The account travels in the signed
    ``state``; capability + channel creation happen here, then the
    browser is sent back to the dashboard with the outcome.

    A state we cannot verify has no account to return to, so those stay
    JSON 4xx (nobody legitimate lands there).
    """
    account_id: int | None = None
    if state:
        try:
            account_id = int(connect_service.verify_oauth_state(state)["account_id"])
        except ChatwootHTTPException:
            account_id = None

    if account_id is None:
        # Nothing verifiable to send the browser back to.
        raise ChatwootHTTPException(
            status_code=400,
            detail={"error": "missing or invalid oauth state"},
        )
    if error:
        return _back_to_dashboard(
            account_id, ig_error=f"Meta canceló la conexión ({error})."
        )
    if not code:
        return _back_to_dashboard(
            account_id, ig_error="Meta no devolvió el código de autorización."
        )

    try:
        result = await connect_service.complete_oauth(
            session, code=code, state=state, page_id=page_id
        )
    except ChatwootHTTPException as exc:
        return _back_to_dashboard(
            account_id,
            ig_error=f"No se pudo completar la conexión: {_error_text(exc)}",
        )

    return _back_to_dashboard(
        account_id,
        ig="reconnected" if result.get("reconnected") else "connected",
        ig_login=str(result.get("login_type") or ""),
        ig_user=str(result.get("username") or ""),
    )


@router.get("/{channel_id}/settings")
async def show_channel_settings(
    channel_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Connection capabilities for a channel (login_type + whether
    DELETE media is available)."""
    assert ctx.account.id is not None
    setting = await connect_service.get_channel_setting(
        session, channel_instagram_id=channel_id
    )
    if setting is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return {
        "channel_instagram_id": setting.channel_instagram_id,
        "login_type": setting.login_type,
        "connect_method": setting.connect_method,
        "page_id": setting.page_id,
        "can_delete_media": setting.login_type != "instagram",
    }


__all__ = ["callback_router", "router"]
