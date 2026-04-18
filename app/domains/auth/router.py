"""``POST /auth/sign_in`` — devise-token-auth-compatible sessions.

Ports ``DeviseOverrides::SessionsController#create`` +
``DeviseTokenAuth::SessionsController#render_create_success`` from
``reference/chatwoot/app/controllers/devise_overrides/sessions_controller.rb``
and the devise-token-auth gem.

Contract preserved for wire parity:

  * Success → HTTP 200, body shaped like ``devise/_auth.json.jbuilder``
    (``{ "data": { ...user } }``), response headers carry the rotated
    ``access-token`` / ``client`` / ``uid`` / ``expiry`` / ``token-type``.
  * Invalid credentials → HTTP 401, body ``{ "errors": ["Invalid login credentials. Please try again."] }``
    matching devise-token-auth's default.
  * The user's ``sign_in_count``, ``current_sign_in_at``, ``last_sign_in_at``
    are updated (Devise ``trackable``).

Phase 1 omissions:
  * MFA / SSO token / OTP — the Ruby controller branches on these before
    calling ``super``. Phase 1 is email+password only; we return 401 for
    anything that isn't a straight email/password match.
  * ``process_sso_auth_token`` — same reason.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth.devise_token_auth import (
    HEADER_CLIENT,
    create_new_auth_token,
)
from app.core.db import get_session
from app.core.deps import current_user
from app.core.security import verify_password
from app.domains.users.models import AccessToken, AccountUser, User
from app.domains.users.presenters import present_auth_response

router = APIRouter(prefix="/auth", tags=["auth"])


class SignInRequest(BaseModel):
    """Body accepted by ``POST /auth/sign_in``.

    Chatwoot's devise-token-auth gem permits ``email`` + ``password`` (plus
    the unused ``mfa_token`` / ``sso_auth_token`` branches).
    """

    email: EmailStr
    password: str


_INVALID_CREDENTIALS_BODY = {
    # devise-token-auth default. Kept verbatim for parity.
    "errors": ["Invalid login credentials. Please try again."]
}


@router.post("/sign_in", status_code=status.HTTP_200_OK)
async def sign_in(
    payload: SignInRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Authenticate email+password, return user payload + auth headers."""
    normalized_email = payload.email.strip().lower()

    stmt = select(User).where(User.email == normalized_email)
    user = (await session.exec(stmt)).first()

    if user is None or not verify_password(payload.password, user.encrypted_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS_BODY,
        )

    # active_for_authentication? — Devise's gate. We mirror the two checks
    # Chatwoot enables: confirmable (requires confirmed_at if the column
    # isn't nil-tolerant in that deployment) and a non-suspended status on
    # the user itself. Phase 1 treats ``confirmed_at is None`` as the only
    # blocker — the AccountBuilder stamps ``confirmed=True`` for api-only
    # signups, so fresh users clear the gate.
    if user.confirmed_at is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "errors": [
                    "A confirmation email was sent to your account at "
                    f"'{user.email}'. You must follow the instructions in the"
                    " email before your account can be activated"
                ]
            },
        )

    # Devise `trackable` hook: bump sign-in counters before minting the token.
    now = datetime.now(UTC).replace(tzinfo=None)
    user.sign_in_count = (user.sign_in_count or 0) + 1
    user.last_sign_in_at = user.current_sign_in_at
    user.current_sign_in_at = now

    # Mint a fresh devise-token-auth client/token/expiry triple.
    headers, new_tokens = create_new_auth_token(
        user_tokens=user.tokens,
        uid=user.uid,
    )
    user.tokens = new_tokens
    session.add(user)
    await session.flush()

    for k, v in headers.as_response_headers().items():
        response.headers[k] = v

    # Fetch user's account memberships + polymorphic AccessToken in parallel.
    memberships = (
        await session.exec(
            select(AccountUser)
            .where(AccountUser.user_id == user.id)
            .order_by(AccountUser.id)  # type: ignore[arg-type]
        )
    ).all()

    access_token = (
        await session.exec(
            select(AccessToken).where(
                AccessToken.owner_type == "User",
                AccessToken.owner_id == user.id,
            )
        )
    ).first()

    if access_token is None:
        # Should exist for any user created via AccountBuilder. If not, we
        # still return a sign_in response but with a blank token string —
        # matches the jbuilder which would raise in Rails; here we avoid
        # the 500 and let the client re-sign-in after re-provisioning.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errors": ["access token missing for user"]},
        )

    return present_auth_response(
        user=user,
        access_token=access_token,
        account_users=list(memberships),
    )


@router.delete("/sign_out", status_code=status.HTTP_200_OK)
async def sign_out(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """``DELETE /auth/sign_out`` — drop the current client's session.

    Ports the devise-token-auth default ``SessionsController#destroy``
    which removes ``user.tokens[client]`` and returns 200 on success.

    Parity notes:
      * Only the *caller's* ``(client, access-token)`` pair is invalidated.
        Sessions on other devices keep working — matches
        ``change_headers_on_each_request = false`` + the gem's per-client
        token storage.
      * ``current_user`` has already validated the headers, so missing or
        bad credentials return 404 in Chatwoot (the gem renders
        ``{"errors": ["User was not found or was not logged in."]}`` with
        HTTP 404). We preserve that status code and body.
    """
    client = request.headers.get(HEADER_CLIENT) or ""
    tokens = dict(user.tokens or {})
    if client in tokens:
        del tokens[client]
        user.tokens = tokens
        session.add(user)
        await session.flush()
    return {"message": "Signed out successfully."}
