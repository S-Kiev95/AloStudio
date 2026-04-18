"""Password reset service — Devise ``reset_password_token`` parity.

Ports the Ruby helpers behind
``DeviseOverrides::PasswordsController#create`` +
``#update`` (``reference/chatwoot/app/controllers/devise_overrides/passwords_controller.rb``):

  * ``User#send_reset_password_instructions`` (from Devise Recoverable):
    1. Generate a raw token ``raw = SecureRandom.urlsafe_base64(20)``.
    2. Compute the per-column key
       ``key = HMAC_SHA256(secret_key_base, "reset_password_token")``.
    3. Store ``enc = HMAC_SHA256(key, raw)`` in ``users.reset_password_token``.
    4. Stamp ``reset_password_sent_at = Time.now``.
    5. Send the raw token to the user by email (out of scope for Phase 1;
       logged instead — see ``_dispatch_reset_email``).

  * ``PasswordsController#update`` (consume):
    1. Take the raw token from the request, re-hash it with the same HMAC.
    2. Find the user by the *digest* column.
    3. Verify the ``reset_password_sent_at`` is within the expiry window.
       Devise default is 6 hours (``config.reset_password_within = 6.hours``
       in ``config/initializers/devise.rb``).
    4. Confirm the user if not already confirmed (Devise Recoverable special
       case — see the Ruby controller comment "confirm if user resets
       password without confirming anytime before").
    5. Bcrypt-hash the new password, clear the reset + confirmation tokens,
       invalidate every existing devise-token-auth session, save.

The token hashing uses HMAC-SHA256 keyed by the app secret — matches
Devise's scheme byte-for-byte so a Chatwoot DB dump could *in theory*
hand us a valid raw token whose digest we'd recognise (assuming the
``SECRET_KEY`` values are aligned, which is only true for same-host
deployments — out of scope). The key point is we don't ever store the
raw token and we use a constant-time compare on lookup.

Email delivery is deferred — :func:`_dispatch_reset_email` just logs the
raw token today. When the ARQ mailer lands (post-Phase-1), swap the body
of that function for an enqueue call; no callers change.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.domains.users.models import User

# Devise ``config.reset_password_within = 6.hours``.
RESET_PASSWORD_WITHIN = timedelta(hours=6)

# Column name threaded into the HMAC key — matches
# ``Devise.token_generator.key_for(:reset_password_token)`` so the digest
# in the DB is computed the same way.
_RESET_COLUMN = "reset_password_token"


@dataclass(slots=True)
class ResetTokenIssued:
    """Tuple returned by :func:`request_password_reset` — used by callers
    that want to drive the mailer (tests, future ARQ handler). The raw
    token is *never* written to the DB; only the digest is stored.
    """

    user: User
    raw_token: str


def _secret_key() -> bytes:
    """App secret reused as the HMAC seed — matches Devise's use of
    ``Rails.application.secret_key_base``.
    """
    return get_settings().secret_key.encode("utf-8")


def _column_key(column: str) -> bytes:
    """``OpenSSL::HMAC.hexdigest(SHA256, secret, column)`` as raw bytes."""
    return hmac.new(_secret_key(), column.encode("utf-8"), hashlib.sha256).digest()


def _digest_token(raw: str) -> str:
    """Hash an incoming raw token the way Devise would.

    Equivalent to ``Devise.token_generator.digest(klass, :reset_password_token, raw)``
    which returns hex, not bytes.
    """
    key = _column_key(_RESET_COLUMN)
    return hmac.new(key, raw.encode("utf-8"), hashlib.sha256).hexdigest()


def _new_raw_token() -> str:
    """Devise's ``friendly_token`` — URL-safe base64(20 bytes). Stripping
    padding matches the Ruby default.
    """
    return secrets.token_urlsafe(20)


async def _dispatch_reset_email(user: User, raw_token: str) -> None:
    """Stub for the Devise mailer.

    Phase 1 logs the raw token so the MailHog inspector or test harness
    can pick it up. When the ARQ mailer ships, replace the body with an
    enqueue and keep the signature.
    """
    get_logger("auth.password_reset").info(
        "password_reset_token_issued",
        user_id=user.id,
        email=user.email,
        # Explicitly tagged so grepping production logs doesn't surface
        # the raw token by accident — log destinations should scrub this.
        raw_token_preview=f"{raw_token[:4]}…{raw_token[-4:]}",
    )


async def request_password_reset(
    session: AsyncSession, email: str
) -> ResetTokenIssued | None:
    """``User.from_email(email)&.send_reset_password_instructions``.

    Returns ``None`` silently when the email doesn't resolve to a user —
    the caller must *not* branch on this, because Chatwoot always returns
    200 to prevent email enumeration. The ``None`` return exists only so
    tests can assert the no-op path.
    """
    normalized = (email or "").strip().lower()
    if not normalized:
        return None

    user = (await session.exec(select(User).where(User.email == normalized))).first()
    if user is None:
        return None

    raw = _new_raw_token()
    user.reset_password_token = _digest_token(raw)
    user.reset_password_sent_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(user)
    await session.flush()

    await _dispatch_reset_email(user, raw)
    return ResetTokenIssued(user=user, raw_token=raw)


async def consume_password_reset(
    session: AsyncSession,
    raw_token: str,
    password: str,
    password_confirmation: str | None = None,
) -> User | None:
    """Apply a password reset. Returns the user on success, ``None`` on
    any validation failure (unknown/expired token, confirmation mismatch).

    Mirrors the Ruby ``reset_password_and_confirmation`` helper lines
    28-35, folding the ``@recoverable`` lookup + ``reset_password!`` +
    post-hooks into one transactional unit.
    """
    if not raw_token or not password:
        return None

    if password_confirmation is not None and password != password_confirmation:
        return None

    digest = _digest_token(raw_token)
    user = (
        await session.exec(
            select(User).where(User.reset_password_token == digest)
        )
    ).first()
    if user is None:
        return None

    # Expiry window
    if user.reset_password_sent_at is None:
        return None
    if (
        datetime.now(UTC).replace(tzinfo=None) - user.reset_password_sent_at
    ) > RESET_PASSWORD_WITHIN:
        return None

    # Devise Recoverable quirk: a successful password reset also confirms
    # the user if they never did. See comment line 29 of the Ruby file.
    if user.confirmed_at is None:
        user.confirmed_at = datetime.now(UTC).replace(tzinfo=None)

    user.encrypted_password = hash_password(password)
    user.reset_password_token = None
    user.reset_password_sent_at = None
    user.confirmation_token = None
    # ``remove_tokens_after_password_reset = true`` — blow away every
    # devise-token-auth session (forces sign-in on every device).
    user.tokens = {}

    session.add(user)
    await session.flush()
    return user
