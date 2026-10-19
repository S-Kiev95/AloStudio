"""Who may change installation-wide settings.

Not account-scoped: these settings belong to the deployment, so the gate
hangs off the authenticated user rather than off an account in the path.

A fresh deployment has **no** super admin — nothing in the signup path
creates one — so gating purely on the role would make the settings
screen unreachable on exactly the install that needs it most: the one
deployed with no credentials yet.

So the gate has a bootstrap arm. While the installation has no super
admin at all, an administrator of the *first* account is treated as the
operator, because on a single-tenant deployment that is who they are.
The moment a real super admin exists the bootstrap stops applying and
the role is the only way in.

Postiz super admins get in through the ``super_admin`` claim of the SSO
token (:mod:`app.domains.auth.sso`). The claim marks the *session* that
exchange mints, not the user: SSO links to whichever user already has
that email, and a session that user opened with a password must never
inherit Postiz's say-so. Those sessions don't close the bootstrap.

An account Postiz created over SSO never counts as the first account: it
belongs to a Postiz organization, not to whoever deployed the sidecar, so
its admins get in only through that claim.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request, status
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth.devise_token_auth import HEADER_CLIENT
from app.core.db import get_session
from app.core.deps import current_user
from app.core.errors import ChatwootHTTPException
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_ADMINISTRATOR,
    AccountUser,
    User,
)

SUPER_ADMIN_TYPE = "SuperAdmin"

# Set on a ``users.tokens`` entry when Postiz's SSO token said super_admin.
SSO_SUPER_ADMIN_TOKEN_KEY = "sso_super_admin"


async def has_any_super_admin(session: AsyncSession) -> bool:
    count = (
        await session.exec(
            select(func.count(User.id)).where(User.type == SUPER_ADMIN_TYPE)
        )
    ).one()
    return bool(count)


async def _administers_first_account(session: AsyncSession, user: User) -> bool:
    from app.domains.accounts.models import Account

    first_account = (
        await session.exec(
            select(Account).order_by(Account.id).limit(1)  # type: ignore[arg-type]
        )
    ).first()
    if first_account is None or (first_account.settings or {}).get("postiz_org_id"):
        return False
    row = (
        await session.exec(
            select(AccountUser).where(
                AccountUser.user_id == user.id,
                AccountUser.account_id == first_account.id,
                AccountUser.role == ACCOUNT_USER_ROLE_ADMINISTRATOR,
            )
        )
    ).first()
    return row is not None


def _is_sso_super_admin_session(request: Request, user: User) -> bool:
    # current_user already verified this client's token.
    entry = (user.tokens or {}).get(request.headers.get(HEADER_CLIENT) or "") or {}
    return entry.get(SSO_SUPER_ADMIN_TOKEN_KEY) is True


async def require_operator(
    request: Request,
    user: Annotated[User, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Super admin, a Postiz super admin's SSO session, or the bootstrap
    operator described above."""
    if user.type == SUPER_ADMIN_TYPE or _is_sso_super_admin_session(request, user):
        return user

    if not await has_any_super_admin(
        session
    ) and await _administers_first_account(session, user):
        return user

    raise ChatwootHTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": "You are not authorized to do this action",
            # Same reason as require_admin: a browser must not read this
            # as an expired session and sign the user out.
            "code": "not_authorized",
        },
    )


__all__ = [
    "SSO_SUPER_ADMIN_TOKEN_KEY",
    "SUPER_ADMIN_TYPE",
    "has_any_super_admin",
    "require_operator",
]
