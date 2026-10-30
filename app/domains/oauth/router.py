"""OAuth HTTP endpoints.

Dashboard (session of the panel):
  * ``GET    /api/v1/accounts/{account_id}/oauth_apps`` (+ POST) — admins
  * ``PATCH  /api/v1/accounts/{account_id}/oauth_apps/{app_id}`` (+ DELETE)
  * ``POST   /api/v1/accounts/{account_id}/oauth_apps/{app_id}/secret``
  * ``GET    /api/v1/accounts/{account_id}/oauth_authorizations`` — each user
  * ``DELETE /api/v1/accounts/{account_id}/oauth_authorizations/{app_id}``
  * ``GET    /api/v1/oauth/authorize`` (+ POST) — the consent page

Protocol (apps call these; no session):
  * ``POST /oauth/token`` — ``authorization_code`` and ``refresh_token``
  * ``POST /oauth/revoke``
  * ``GET  /.well-known/oauth-authorization-server`` (RFC 8414)
  * ``GET  /.well-known/oauth-protected-resource[/mcp]`` (RFC 9728)
"""

from __future__ import annotations

import base64
from typing import Annotated, Any
from urllib.parse import unquote_plus

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, Response
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.datastructures import FormData

from app.core.db import get_session
from app.core.deps import AccountContext, account_context, current_user, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.accounts.models import Account
from app.domains.oauth import service as svc
from app.domains.oauth.presenters import (
    present_app,
    present_app_with_secret,
    present_authorization,
    present_consent,
)
from app.domains.oauth.schemas import OAuthAppCreate, OAuthAppUpdate, OAuthConsentIn
from app.domains.users.models import User

apps_router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/oauth_apps",
    tags=["oauth"],
)
authorizations_router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/oauth_authorizations",
    tags=["oauth"],
)
consent_router = APIRouter(prefix="/api/v1/oauth", tags=["oauth"])
protocol_router = APIRouter(tags=["oauth"])

# RFC 6749 §5.1: token responses must not be cached.
_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


# ---------------------------------------------------------------------------
# Apps of the account (admins)
# ---------------------------------------------------------------------------
@apps_router.get("")
async def list_apps_endpoint(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    apps = await svc.list_apps(session, account_id=ctx.account.id)  # type: ignore[arg-type]
    counts = await svc.authorization_counts(session, [a.id for a in apps])  # type: ignore[misc]
    return {
        "apps": [present_app(a, authorizations_count=counts.get(a.id, 0)) for a in apps],  # type: ignore[arg-type]
        "endpoints": svc.endpoints(),
    }


@apps_router.post("", status_code=status.HTTP_200_OK)
async def create_app_endpoint(
    payload: OAuthAppCreate,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    app, secret = await svc.create_app(
        session,
        account_id=ctx.account.id,  # type: ignore[arg-type]
        created_by_id=ctx.user.id,
        name=payload.name,
        redirect_uris=payload.redirect_uris,
        confidential=payload.confidential,
    )
    return present_app_with_secret(app, secret, authorizations_count=0)


@apps_router.patch("/{app_id}")
async def update_app_endpoint(
    app_id: int,
    payload: OAuthAppUpdate,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    app = await svc.get_app(session, account_id=ctx.account.id, app_id=app_id)  # type: ignore[arg-type]
    app = await svc.update_app(
        session, app, name=payload.name, redirect_uris=payload.redirect_uris
    )
    counts = await svc.authorization_counts(session, [app_id])
    return present_app(app, authorizations_count=counts.get(app_id, 0))


@apps_router.post("/{app_id}/secret", status_code=status.HTTP_200_OK)
async def rotate_secret_endpoint(
    app_id: int,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    app = await svc.get_app(session, account_id=ctx.account.id, app_id=app_id)  # type: ignore[arg-type]
    secret = await svc.rotate_secret(session, app)
    counts = await svc.authorization_counts(session, [app_id])
    return present_app_with_secret(app, secret, authorizations_count=counts.get(app_id, 0))


@apps_router.delete("/{app_id}", status_code=status.HTTP_200_OK)
async def delete_app_endpoint(
    app_id: int,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    app = await svc.get_app(session, account_id=ctx.account.id, app_id=app_id)  # type: ignore[arg-type]
    await svc.delete_app(session, app)
    return {}


# ---------------------------------------------------------------------------
# Approved apps (each user, in this account)
# ---------------------------------------------------------------------------
@authorizations_router.get("")
async def list_authorizations_endpoint(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    grants = await svc.live_grants(
        session, account_id=ctx.account.id, user_id=ctx.user.id  # type: ignore[arg-type]
    )
    return {"authorizations": [present_authorization(app, tokens) for app, tokens in grants]}


@authorizations_router.delete("/{app_id}", status_code=status.HTTP_200_OK)
async def revoke_authorization_endpoint(
    app_id: int,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    revoked = await svc.revoke_grant(
        session,
        application_id=app_id,
        account_id=ctx.account.id,  # type: ignore[arg-type]
        user_id=ctx.user.id,  # type: ignore[arg-type]
    )
    if not revoked:
        raise ChatwootHTTPException(
            status_code=404, detail={"message": "No encontramos esa autorización."}
        )
    return {}


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------
@consent_router.get("/authorize")
async def consent_preview_endpoint(
    request: Request,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    try:
        auth = await svc.validate_authorize(session, dict(request.query_params))
    except svc.RedirectWithError as exc:
        return {"redirect_to": exc.redirect_to}
    owner = await session.get(Account, auth.app.account_id)
    return present_consent(
        auth,
        owner=owner,
        memberships=await svc.memberships(session, user_id=user.id),  # type: ignore[arg-type]
    )


@consent_router.post("/authorize", status_code=status.HTTP_200_OK)
async def consent_submit_endpoint(
    payload: OAuthConsentIn,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    try:
        auth = await svc.validate_authorize(session, payload.model_dump())
    except svc.RedirectWithError as exc:
        return {"redirect_to": exc.redirect_to}
    if not payload.approve:
        return {"redirect_to": svc.denied_redirect(auth)}
    return {
        "redirect_to": await svc.approve(session, user, auth, account_id=payload.account_id)
    }


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------
def _form_value(form: FormData, key: str) -> str | None:
    value = form.get(key)
    return value if isinstance(value, str) and value else None


def _client_credentials(request: Request, form: FormData) -> tuple[str | None, str | None]:
    """``client_secret_basic`` (RFC 6749 §2.3.1) or ``client_secret_post``;
    a public app sends only ``client_id``."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise svc.OAuthError(
                "invalid_client", "Credenciales Basic mal formadas.", status_code=401
            ) from exc
        client_id, _, client_secret = decoded.partition(":")
        return unquote_plus(client_id), unquote_plus(client_secret)
    return _form_value(form, "client_id"), _form_value(form, "client_secret")


def _oauth_error(exc: svc.OAuthError) -> JSONResponse:
    headers = dict(_NO_STORE)
    if exc.status_code == 401:
        headers["WWW-Authenticate"] = 'Basic realm="AloStudio"'
    return JSONResponse(
        {"error": exc.error, "error_description": exc.description},
        status_code=exc.status_code,
        headers=headers,
    )


@protocol_router.post("/oauth/token")
async def token_endpoint(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JSONResponse:
    form = await request.form()
    try:
        client_id, client_secret = _client_credentials(request, form)
        app = await svc.authenticate_client(
            session, client_id=client_id, client_secret=client_secret
        )
        grant_type = _form_value(form, "grant_type")
        if grant_type == "authorization_code":
            body = await svc.exchange_code(
                session,
                app,
                code=_form_value(form, "code"),
                redirect_uri=_form_value(form, "redirect_uri"),
                code_verifier=_form_value(form, "code_verifier"),
            )
        elif grant_type == "refresh_token":
            body = await svc.refresh(
                session,
                app,
                refresh_token=_form_value(form, "refresh_token"),
                scope=_form_value(form, "scope"),
            )
        else:
            raise svc.OAuthError(
                "unsupported_grant_type",
                "Los grant_type posibles son authorization_code y refresh_token.",
            )
    except svc.OAuthError as exc:
        # Returned, not raised: a revocation done while detecting a replay
        # has to be committed with the error.
        return _oauth_error(exc)
    return JSONResponse(body, headers=_NO_STORE)


@protocol_router.post("/oauth/revoke")
async def revoke_endpoint(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    form = await request.form()
    try:
        client_id, client_secret = _client_credentials(request, form)
        app = await svc.authenticate_client(
            session, client_id=client_id, client_secret=client_secret
        )
    except svc.OAuthError as exc:
        return _oauth_error(exc)
    await svc.revoke_token(session, app, token=_form_value(form, "token"))
    return Response(status_code=status.HTTP_200_OK)


@protocol_router.get("/.well-known/oauth-authorization-server")
async def authorization_server_metadata_endpoint() -> dict[str, Any]:
    return svc.authorization_server_metadata()


@protocol_router.get("/.well-known/oauth-protected-resource")
@protocol_router.get("/.well-known/oauth-protected-resource/mcp")
async def protected_resource_metadata_endpoint() -> dict[str, Any]:
    return svc.protected_resource_metadata()


__all__ = ["apps_router", "authorizations_router", "consent_router", "protocol_router"]
