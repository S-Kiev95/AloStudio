"""FastAPI auth dependencies.

Ports the Rails ``authenticate_user!`` + ``current_user`` filters that
``Api::BaseController`` runs on every protected request.

Chatwoot's auth chain on an authenticated API hit:

  1. ``DeviseTokenAuth::Concerns::SetUserByToken#set_user_by_token`` reads
     ``access-token`` / ``client`` / ``uid`` headers, finds the User by
     ``uid + provider`` and verifies the stored bcrypt hash in
     ``user.tokens[client]`` against the incoming ``access-token``.
  2. If valid, ``current_user`` is populated and the request continues; the
     rotated headers are sent back in the response via an after_action.
  3. If anything fails (missing headers, unknown uid, bad bcrypt compare,
     expired entry) Rails renders 401 with the devise-token-auth envelope
     ``{"errors": ["Invalid login credentials. Please try again."]}``.

Our ``current_user`` dependency does the same three things and yields a
:class:`~app.domains.users.models.User`. A thinner ``optional_current_user``
variant returns ``None`` instead of raising — used by endpoints that should
behave differently for anonymous visitors (e.g. widget + some signup flows).

We deliberately **don't** rotate tokens here — ``change_headers_on_each_request``
is false (see :mod:`app.core.auth.devise_token_auth`), so the client keeps
the same ``(client, access-token)`` pair across requests. Rotation only
happens on sign_in and password reset.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth.devise_token_auth import (
    HEADER_ACCESS_TOKEN,
    HEADER_CLIENT,
    HEADER_UID,
    verify_auth_token,
)
from app.core.db import get_session
from app.domains.users.models import User

_INVALID_CREDS = {"errors": ["Invalid login credentials. Please try again."]}


def _read_auth_headers(request: Request) -> tuple[str, str, str] | None:
    """Return ``(access_token, client, uid)`` or ``None`` if any are missing.

    Header names are case-insensitive (Starlette normalises on read), so
    this accepts both wire-case and title-case. Empty strings count as
    missing — matches devise-token-auth which treats blank headers as
    unauthenticated.
    """
    access_token = request.headers.get(HEADER_ACCESS_TOKEN) or ""
    client = request.headers.get(HEADER_CLIENT) or ""
    uid = request.headers.get(HEADER_UID) or ""
    if not (access_token and client and uid):
        return None
    return access_token, client, uid


async def _load_user(session: AsyncSession, uid: str) -> User | None:
    """Find User by ``uid`` — matches Devise's ``User.from_email`` helper.

    Chatwoot's uid is the downcased email for provider=email users; we
    keep that equivalence in :meth:`AccountBuilder._create_user`. For
    omniauth users Chatwoot uses the provider's user id — not in scope
    for Phase 1 but the shape here will continue to work because we filter
    by ``uid`` alone.
    """
    stmt = select(User).where(User.uid == uid.lower())
    return (await session.exec(stmt)).first()


async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Require a valid devise-token-auth session. Raises 401 otherwise."""
    headers = _read_auth_headers(request)
    if headers is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDS
        )
    access_token, client, uid = headers

    user = await _load_user(session, uid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDS
        )

    if not verify_auth_token(
        user.tokens, client=client, access_token=access_token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDS
        )

    return user


async def optional_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Return the current user or ``None`` — never raises.

    Useful for endpoints like ``POST /api/v1/accounts`` where an existing
    user's session (dashboard "add account" flow) changes the response
    shape but anonymous callers are still allowed.
    """
    headers = _read_auth_headers(request)
    if headers is None:
        return None
    access_token, client, uid = headers
    user = await _load_user(session, uid)
    if user is None:
        return None
    if not verify_auth_token(
        user.tokens, client=client, access_token=access_token
    ):
        return None
    return user
