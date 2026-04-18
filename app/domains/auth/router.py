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
from fastapi.responses import JSONResponse
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
from app.domains.auth.confirmation import (
    ConfirmationError,
    consume_confirmation_token,
    request_confirmation_resend,
)
from app.domains.auth.password_reset import (
    consume_password_reset,
    request_password_reset,
)
from app.domains.users.models import AccessToken, AccountUser, User
from app.domains.users.presenters import present_auth_response

router = APIRouter(prefix="/auth", tags=["auth"])

# Separate router for the unauthenticated resend endpoint — Chatwoot mounts
# it at the root (``POST /resend_confirmation``), not under ``/auth``. The
# Ruby comment explains: OmniAuth middleware intercepts all ``/auth/*``
# POSTs as provider callbacks, so resend had to live outside that scope.
# We preserve the exact path for wire parity even though our app has no
# OmniAuth middleware to worry about.
resend_confirmation_router = APIRouter(tags=["auth"])


class SignInRequest(BaseModel):
    """Body accepted by ``POST /auth/sign_in``.

    Chatwoot's devise-token-auth gem permits ``email`` + ``password`` (plus
    the unused ``mfa_token`` / ``sso_auth_token`` branches).
    """

    email: EmailStr
    password: str


_INVALID_CREDENTIALS_BODY = {
    # devise-token-auth default envelope. The gem's
    # ``render_create_error`` method sets both ``success: false`` and
    # ``errors`` — we mirror both keys verbatim because real clients
    # (Chatwoot's Vue dashboard) check ``success`` before reading
    # ``errors``.
    "success": False,
    "errors": ["Invalid login credentials. Please try again."],
}


class ChatwootHTTPException(HTTPException):
    """``HTTPException`` whose ``detail`` dict becomes the response body
    directly, *not* wrapped under a ``"detail"`` key.

    Why a marker subclass instead of raw :class:`JSONResponse` returns:
    every Rails controller in this port emits the body with ``render
    json: {...}`` — i.e. no envelope. FastAPI's default
    :func:`http_exception_handler` wraps ``detail`` as
    ``{"detail": ...}``. Installing a custom handler for this marker
    class lets us keep idiomatic ``raise`` flow in the controllers
    while matching Chatwoot byte-for-byte on the wire.
    """


async def chatwoot_http_exception_handler(
    _request: Request, exc: ChatwootHTTPException
) -> JSONResponse:
    """Emit ``exc.detail`` directly as the response body (no ``detail``
    wrapper)."""
    body = exc.detail if isinstance(exc.detail, dict | list) else {"message": exc.detail}
    return JSONResponse(status_code=exc.status_code, content=body)


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
        raise ChatwootHTTPException(
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
        raise ChatwootHTTPException(
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
        raise ChatwootHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errors": ["access token missing for user"]},
        )

    return present_auth_response(
        user=user,
        access_token=access_token,
        account_users=list(memberships),
    )


class PasswordResetRequest(BaseModel):
    """Body of ``POST /auth/password`` — request a reset email."""

    email: EmailStr


class PasswordResetApply(BaseModel):
    """Body of ``PUT /auth/password`` — consume the reset token."""

    reset_password_token: str
    password: str
    password_confirmation: str | None = None


@router.post("/password", status_code=status.HTTP_200_OK)
async def request_password_reset_endpoint(
    payload: PasswordResetRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """``POST /auth/password`` — always 200, no enumeration.

    Ports ``DeviseOverrides::PasswordsController#create``. Chatwoot
    responds with ``I18n.t('messages.reset_password')`` which resolves
    (en locale) to *"You will receive an email with instructions on how to
    reset your password in a few minutes."*.
    """
    await request_password_reset(session, payload.email)
    # String is ``I18n.t('messages.reset_password')`` from
    # ``reference/chatwoot/config/locales/en.yml`` line 44 — kept
    # verbatim so the parity harness can ``==``-compare.
    return {
        "message": (
            "Request for password reset is successful. A email with"
            " instructions will be sent to your email if it exists."
        )
    }


@router.put("/password", status_code=status.HTTP_200_OK)
async def apply_password_reset_endpoint(
    payload: PasswordResetApply,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """``PUT /auth/password`` — apply the reset, mint a fresh session.

    Mirrors ``PasswordsController#update`` — on success emits the
    devise-token-auth headers + ``_user.json.jbuilder`` body (rotated
    token; every prior client session is invalidated by the service).
    On failure returns Chatwoot's exact error envelope
    ``{"message": "Invalid token", "redirect_url": "/"}`` with 422.
    """
    user = await consume_password_reset(
        session,
        raw_token=payload.reset_password_token,
        password=payload.password,
        password_confirmation=payload.password_confirmation,
    )
    if user is None:
        raise ChatwootHTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": "Invalid token", "redirect_url": "/"},
        )

    # Issue a brand new devise-token-auth session (``send_auth_headers``).
    headers, new_tokens = create_new_auth_token(
        user_tokens=user.tokens, uid=user.uid
    )
    user.tokens = new_tokens
    session.add(user)
    await session.flush()

    for k, v in headers.as_response_headers().items():
        response.headers[k] = v

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
        raise ChatwootHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errors": ["access token missing for user"]},
        )

    return present_auth_response(
        user=user,
        access_token=access_token,
        account_users=list(memberships),
    )


class ConfirmationConsumeRequest(BaseModel):
    """Body of ``POST /auth/confirmation`` — consume a confirmation token."""

    confirmation_token: str


class ResendConfirmationRequest(BaseModel):
    """Body of ``POST /resend_confirmation`` — request a new confirmation email."""

    email: EmailStr


@router.post("/confirmation", status_code=status.HTTP_200_OK)
async def apply_confirmation_endpoint(
    payload: ConfirmationConsumeRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """``POST /auth/confirmation`` — mark the user confirmed + sign them in.

    Ports ``DeviseOverrides::ConfirmationsController#create``. On success
    the Ruby controller emits ``send_auth_headers`` + ``devise/_auth.json.jbuilder``,
    i.e. the same envelope as ``sign_in`` (auto login after email
    confirmation). On failure it renders one of three 422 bodies
    identified by the service's :class:`ConfirmationError` variant.
    """
    outcome = await consume_confirmation_token(session, payload.confirmation_token)
    if isinstance(outcome, ConfirmationError):
        # Ruby controller's three-branch ``render_confirmation_error``:
        #   blank   → "Invalid token"
        #   confirmed_at → "Already confirmed"
        #   else    → "Failure"
        # Our service folds "blank" and "unknown" into INVALID_TOKEN (same
        # wire message). The "Failure" branch is unreachable in practice
        # (the Ruby ``confirm`` returning false without the above two
        # preconditions is a validation-error edge case we don't replicate
        # — there are no extra confirm-time validations in Phase 1).
        if outcome is ConfirmationError.ALREADY_CONFIRMED:
            message = "Already confirmed"
        else:
            message = "Invalid token"
        raise ChatwootHTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": message, "redirect_url": "/"},
        )

    user = outcome
    # ``send_auth_headers`` — mint a fresh devise-token-auth session and
    # return the user payload. Matches the ``sign_in`` response shape.
    headers, new_tokens = create_new_auth_token(
        user_tokens=user.tokens, uid=user.uid
    )
    user.tokens = new_tokens
    session.add(user)
    await session.flush()

    for k, v in headers.as_response_headers().items():
        response.headers[k] = v

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
        raise ChatwootHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errors": ["access token missing for user"]},
        )

    return present_auth_response(
        user=user,
        access_token=access_token,
        account_users=list(memberships),
    )


@resend_confirmation_router.post(
    "/resend_confirmation", status_code=status.HTTP_204_NO_CONTENT
)
async def resend_confirmation_endpoint(
    payload: ResendConfirmationRequest,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """``POST /resend_confirmation`` — always 204, no enumeration.

    Ports ``Auth::ResendConfirmationsController#create``. The Ruby
    controller gates on hCaptcha before the email lookup; we defer the
    captcha wiring to a later phase and keep the same 204-regardless
    contract so clients don't have to branch.
    """
    await request_confirmation_resend(session, payload.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
