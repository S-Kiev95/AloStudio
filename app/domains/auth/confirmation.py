"""Email confirmation service — Devise ``Confirmable`` parity.

Ports the logic behind ``DeviseOverrides::ConfirmationsController#create``
and ``Auth::ResendConfirmationsController#create`` from
``reference/chatwoot/app/controllers/devise_overrides/confirmations_controller.rb``
and ``.../auth/resend_confirmations_controller.rb``.

Devise stores ``confirmation_token`` *as plaintext* in the DB (unlike
reset_password_token which is HMAC-hashed) — the reasoning is that
confirmation tokens are single-use and low-value pre-click. We preserve
that shape; anyone who's looked at a Chatwoot DB will recognise the
column contents immediately.

Three controller cases we reproduce verbatim on the failure paths:

  * token missing / unknown user     → 422 ``{"message":"Invalid token", ...}``
  * user already confirmed           → 422 ``{"message":"Already confirmed", ...}``
  * unknown late-stage failure       → 422 ``{"message":"Failure", ...}``

The resend endpoint (``POST /resend_confirmation``) always returns 204 —
no enumeration, matching ``head :ok`` in the Ruby controller.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.domains.users.models import User


class ConfirmationError(StrEnum):
    """Categorises why a confirmation attempt failed — maps 1:1 to the
    three branches in ``ConfirmationsController#render_confirmation_error``.

    ``StrEnum`` (Python 3.11+) is the canonical replacement for the
    ``class X(str, Enum)`` idiom — identical string-equality semantics
    at the call site, plus the members ``.value`` round-trips through
    JSON serialisers the same way Devise's string-backed enums do.
    """

    INVALID_TOKEN = "invalid_token"
    ALREADY_CONFIRMED = "already_confirmed"


@dataclass(slots=True)
class ConfirmationIssued:
    user: User
    raw_token: str


def _new_confirmation_token() -> str:
    """Devise's ``generate_confirmation_token!`` produces a URL-safe token
    via ``Devise.friendly_token`` (20 random bytes, base64url, unpadded).
    Same as the reset token generator.
    """
    return secrets.token_urlsafe(20)


async def _dispatch_confirmation_email(user: User, raw_token: str) -> None:
    """Stub for the Devise ``Devise::Mailer#confirmation_instructions``.

    Same policy as the password reset mailer: log a preview today, swap
    for an ARQ enqueue once the mail worker ships.
    """
    get_logger("auth.confirmation").info(
        "confirmation_token_issued",
        user_id=user.id,
        email=user.email,
        raw_token_preview=f"{raw_token[:4]}…{raw_token[-4:]}",
    )


async def issue_confirmation_token(
    session: AsyncSession, user: User
) -> ConfirmationIssued:
    """Stamp a fresh ``confirmation_token`` + ``confirmation_sent_at`` and
    return the raw token for the mailer.

    No-ops on an already-confirmed user only at the caller's discretion —
    Devise itself allows re-issuing tokens (e.g. email-change flow), so
    we don't gate here.
    """
    raw = _new_confirmation_token()
    user.confirmation_token = raw
    user.confirmation_sent_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(user)
    await session.flush()
    await _dispatch_confirmation_email(user, raw)
    return ConfirmationIssued(user=user, raw_token=raw)


async def consume_confirmation_token(
    session: AsyncSession, raw_token: str
) -> User | ConfirmationError:
    """Confirm the user bound to ``raw_token``.

    Returns the confirmed :class:`User` on success, or a
    :class:`ConfirmationError` variant the router maps to Chatwoot's
    exact error body.
    """
    if not raw_token:
        return ConfirmationError.INVALID_TOKEN

    user = (
        await session.exec(
            select(User).where(User.confirmation_token == raw_token)
        )
    ).first()
    if user is None:
        return ConfirmationError.INVALID_TOKEN

    if user.confirmed_at is not None:
        return ConfirmationError.ALREADY_CONFIRMED

    user.confirmed_at = datetime.now(UTC).replace(tzinfo=None)
    # Devise leaves the confirmation_token column populated post-confirm
    # (no explicit clear in Confirmable#confirm!). We mirror that so a
    # DB dump side-by-side comparison matches.
    session.add(user)
    await session.flush()
    return user


async def request_confirmation_resend(session: AsyncSession, email: str) -> None:
    """Resend the confirmation email to an unconfirmed user.

    Ports ``Auth::ResendConfirmationsController#create``. Returns
    silently in every branch (unknown email, already-confirmed user,
    empty input) — the router always emits 204 so no enumeration leaks.
    """
    normalized = (email or "").strip().lower()
    if not normalized:
        return

    user = (
        await session.exec(select(User).where(User.email == normalized))
    ).first()
    if user is None or user.confirmed_at is not None:
        return

    await issue_confirmation_token(session, user)
