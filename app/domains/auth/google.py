"""Sign in with Google — for users an administrator already invited.

Written from Google's OpenID Connect documentation (web server flow):

  * ``GET /auth/google`` tells the login page whether the button shows
    (``GOOGLE_CLIENT_ID`` and ``GOOGLE_CLIENT_SECRET`` set in Ajustes →
    Instalación).
  * ``GET /auth/google/authorize_url?nonce=…`` builds Google's consent URL
    (``openid email profile``). The frontend draws ``nonce`` at random,
    keeps it in an httpOnly cookie and passes it here; it travels in the
    signed ``state``, so a callback is only accepted from the browser that
    started it (no logging someone into another person's account).
  * Google sends the browser back to the frontend's
    ``/auth/google/callback``, which posts ``code`` + ``state`` (and the
    cookie's nonce) to ``POST /auth/google``. The code is exchanged at
    Google's token endpoint; the ID token it returns comes straight from
    Google over TLS, so its claims are read without checking the signature
    again (OpenID Connect Core 3.1.3.7), but ``iss``, ``aud`` and ``exp``
    are checked.

Only an existing user signs in: Google proves the address, the invitation
gives the access. The address must be verified by Google and, when
``GOOGLE_ALLOWED_DOMAIN`` is set (a Google Workspace domain), belong to it.
Signing in confirms a still-unconfirmed invitee, as Google already proved
the address is theirs.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.core.oauth_state import sign_oauth_state, verify_oauth_state
from app.domains.auth.sso import issue_session
from app.domains.users.models import AccountUser, User

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")
CALLBACK_PATH = "/auth/google/callback"
_FLOW = "google_login"


class GoogleSignInRequest(BaseModel):
    code: str
    state: str
    nonce: str


def _enabled() -> bool:
    settings = get_settings()
    return bool(settings.google_client_id and settings.google_client_secret)


def _redirect_uri() -> str:
    return get_settings().app_base_url.rstrip("/") + CALLBACK_PATH


def _refused(message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail={"errors": [message]}
    )


def _id_token_claims(id_token: str) -> dict[str, Any]:
    """The claims of an ID token received straight from Google's token
    endpoint (see module docstring), after checking who it is for."""
    try:
        payload = id_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError):
        raise _refused("Google devolvió una identidad inválida.") from None
    if (
        claims.get("iss") not in ISSUERS
        or claims.get("aud") != get_settings().google_client_id
        or int(claims.get("exp") or 0) < time.time()
    ):
        raise _refused("Google devolvió una identidad inválida.")
    return claims


@router.get("/google")
async def google_sign_in_status() -> dict[str, Any]:
    """Whether the login page offers "Entrar con Google"."""
    return {"enabled": _enabled()}


@router.get("/google/authorize_url")
async def google_authorize_url(
    nonce: str = Query(min_length=16, max_length=128),
) -> dict[str, str]:
    if not _enabled():
        raise ChatwootHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errors": ["El ingreso con Google no está activado."]},
        )
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": sign_oauth_state(0, flow=f"{_FLOW}:{nonce}"),
        "prompt": "select_account",
    }
    if settings.google_allowed_domain:
        # Google's hint to show only accounts of that Workspace domain;
        # the domain is checked again on the way back.
        params["hd"] = settings.google_allowed_domain
    return {"url": f"{AUTHORIZE_URL}?{urlencode(params)}"}


@router.post("/google", status_code=status.HTTP_200_OK)
async def google_sign_in(
    payload: GoogleSignInRequest,
    response: Response,
    session: AsyncSession = Depends(get_session, scope="function"),
) -> dict:
    """Exchange Google's code for an AloStudio session of an invited user.
    Answers like ``POST /auth/sign_in``."""
    if not _enabled():
        raise ChatwootHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errors": ["El ingreso con Google no está activado."]},
        )
    state = verify_oauth_state(payload.state)
    if state.get("flow") != f"{_FLOW}:{payload.nonce}":
        raise _refused("El ingreso con Google venció o no empezó en este navegador. Probá de nuevo.")

    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "code": payload.code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": _redirect_uri(),
                    "grant_type": "authorization_code",
                },
            )
    except httpx.HTTPError as exc:
        log.warning("auth.google.transport err=%s", type(exc).__name__)
        raise ChatwootHTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"errors": ["No se pudo contactar a Google. Probá de nuevo."]},
        ) from exc
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    id_token = body.get("id_token") if isinstance(body, dict) else None
    if resp.status_code >= 400 or not isinstance(id_token, str):
        log.info("auth.google.token_refused status=%s error=%s", resp.status_code, body.get("error"))
        raise _refused("Google no confirmó el ingreso. Probá de nuevo.")

    claims = _id_token_claims(id_token)
    email = str(claims.get("email") or "").strip().lower()
    if not email or claims.get("email_verified") is not True:
        raise _refused("Tu cuenta de Google no tiene un correo verificado.")
    domain = settings.google_allowed_domain.strip().lower()
    if domain and (claims.get("hd") or "").lower() != domain:
        raise _refused(f"Entrá con tu cuenta de Google de {domain}.")

    user = (await session.exec(select(User).where(User.email == email))).first()
    membership = (
        (
            await session.exec(
                select(AccountUser)
                .where(AccountUser.user_id == user.id)
                .order_by(AccountUser.id)  # type: ignore[arg-type]
            )
        ).first()
        if user is not None
        else None
    )
    if user is None or membership is None:
        raise ChatwootHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "errors": [
                    f"{email} no tiene acceso a AloStudio. Pedile a un administrador "
                    "que te invite."
                ]
            },
        )
    if user.confirmed_at is None:
        user.confirmed_at = datetime.now(UTC).replace(tzinfo=None)
    return await issue_session(
        session, response, user=user, active_account_id=membership.account_id
    )


__all__ = ["router"]
