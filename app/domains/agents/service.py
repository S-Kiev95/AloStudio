"""Agent admin: invite, role change, remove + invitation mailer.

Anchors:
  reference/chatwoot/app/builders/agent_builder.rb
  reference/chatwoot/app/controllers/api/v1/accounts/agents_controller.rb

Chatwoot's flow: AgentBuilder finds-or-creates a User with a random
password, devise sends a confirmation email, the invitee confirms +
runs the password reset flow to set their password — four steps for
the invitee.

We collapse that to one step. On invite we:

  1. Find or create the User (random initial password — never sent).
  2. Mark ``confirmed_at`` automatically (admin vouched for them).
  3. Mint a ``reset_password_token`` (Devise-compatible — same digest
     algorithm we use in :mod:`app.domains.auth.password_reset`).
  4. Send a single "you've been invited" email that links the invitee
     to ``/reset-password?token=<raw>`` to set their password.
  5. Link the User to the Account via an ``AccountUser`` row.

Clicking the link drops the user into the existing reset-password
flow which sets the password and signs them in.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from email.message import EmailMessage

import aiosmtplib
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.domains.accounts.models import Account
from app.domains.auth.password_reset import (
    _digest_token,
    _new_raw_token,
)
from app.domains.users.models import (
    _ROLE_STR_TO_INT,
    AccountUser,
    User,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class AgentAlreadyInAccount(Exception):
    """Raised when the email already maps to an AccountUser on this account."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def invite_agent(
    session: AsyncSession,
    *,
    account: Account,
    inviter: User,
    email: str,
    name: str,
    role: str = "agent",
    availability: int | None = None,
    auto_offline: bool | None = None,
) -> tuple[User, AccountUser, str]:
    """Invite an agent to ``account``. Returns ``(user, account_user, raw_token)``.

    The ``raw_token`` is the once-only invitation token — returned so
    tests can exercise the link without scraping email. The router
    discards it; only the email recipient ever sees it.
    """
    normalized = email.strip().lower()
    role_int = _ROLE_STR_TO_INT.get(role, _ROLE_STR_TO_INT["agent"])

    assert account.id is not None

    # 1. Find or create the User.
    existing = (
        await session.exec(select(User).where(User.email == normalized))
    ).first()
    if existing is not None:
        user = existing
        # If they already belong to this account, the caller treats it
        # as a 422 / "already an agent".
        au = (
            await session.exec(
                select(AccountUser).where(
                    AccountUser.account_id == account.id,
                    AccountUser.user_id == user.id,
                )
            )
        ).first()
        if au is not None:
            raise AgentAlreadyInAccount()
    else:
        # New user — random initial password (overwritten via reset).
        random_password = f"1!aA{secrets.token_urlsafe(12)}"
        user = User(
            email=normalized,
            uid=normalized,
            name=name,
            display_name=name,
            encrypted_password=hash_password(random_password),
            confirmed_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(user)
        await session.flush()

    # 2. Mint a reset-password token (Devise-compatible digest).
    raw_token = _new_raw_token()
    user.reset_password_token = _digest_token(raw_token)
    user.reset_password_sent_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(user)

    # 3. Link to the account.
    au_kwargs: dict[str, object] = {
        "account_id": account.id,
        "user_id": user.id,
        "inviter_id": inviter.id,
        "role": role_int,
    }
    if availability is not None:
        au_kwargs["availability"] = availability
    if auto_offline is not None:
        au_kwargs["auto_offline"] = auto_offline
    account_user = AccountUser(**au_kwargs)  # type: ignore[arg-type]
    session.add(account_user)
    await session.flush()

    # 4. Fire-and-forget the email.
    await _send_invitation_email(
        invitee=user, inviter=inviter, account=account, raw_token=raw_token
    )

    return user, account_user, raw_token


async def update_account_user_role(
    session: AsyncSession,
    *,
    account_user: AccountUser,
    name: str | None,
    role: str | None,
    availability: int | None,
    auto_offline: bool | None,
    user: User,
) -> tuple[User, AccountUser]:
    """Patch the AccountUser + (optionally) the User.name. Returns both."""
    if role is not None:
        account_user.role = _ROLE_STR_TO_INT.get(role, account_user.role)
    if availability is not None:
        account_user.availability = availability
    if auto_offline is not None:
        account_user.auto_offline = auto_offline
    if name is not None:
        user.name = name
        session.add(user)
    session.add(account_user)
    await session.flush()
    return user, account_user


async def remove_account_user(
    session: AsyncSession, *, account_user: AccountUser
) -> None:
    """Drop the AccountUser link. The User row stays (they may belong
    to other accounts; the existing destroy_user task in Chatwoot's
    delayed-job runs only when there are zero remaining links — we
    leave that orphan-sweep to a follow-up worker)."""
    await session.delete(account_user)
    await session.flush()


# ---------------------------------------------------------------------------
# Mailer
# ---------------------------------------------------------------------------
def _build_invitation_email(
    *,
    invitee: User,
    inviter: User,
    account: Account,
    raw_token: str,
) -> EmailMessage:
    settings = get_settings()
    reset_url = (
        f"{settings.app_base_url.rstrip('/')}/reset-password?token={raw_token}"
    )
    msg = EmailMessage()
    msg["From"] = settings.mail_from
    msg["To"] = invitee.email or ""
    msg["Subject"] = f"Te invitaron a {account.name} en AloStudio"
    msg.set_content(
        f"""Hola {invitee.name or invitee.email},

{inviter.name} te invitó a unirte a la cuenta "{account.name}" en AloStudio.

Para terminar de configurar tu cuenta y elegir una contraseña, hacé clic acá:

    {reset_url}

Si no esperabas esta invitación podés ignorar este email.

— AloStudio
""",
    )
    return msg


async def _send_invitation_email(
    *,
    invitee: User,
    inviter: User,
    account: Account,
    raw_token: str,
) -> None:
    """Send the invitation email via SMTP. Failures are logged, never raised.

    The user is created and tokenised even if delivery fails — admin can
    resend or surface the link directly via the database in dev (we also
    return the ``raw_token`` from :func:`invite_agent` for tests).
    """
    settings = get_settings()
    if not invitee.email:
        return

    msg = _build_invitation_email(
        invitee=invitee, inviter=inviter, account=account, raw_token=raw_token
    )

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=settings.smtp_tls,
            start_tls=False,
            timeout=10.0,
        )
    except (aiosmtplib.SMTPException, OSError, TimeoutError) as exc:
        log.warning(
            "agents.invite.send_failed account_id=%s invitee=%s error=%s",
            account.id,
            invitee.email,
            exc,
        )


__all__ = [
    "AgentAlreadyInAccount",
    "invite_agent",
    "remove_account_user",
    "update_account_user_role",
]
