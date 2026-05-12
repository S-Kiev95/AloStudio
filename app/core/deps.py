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
     expired entry) devise's ``authenticate_user!`` short-circuits with
     401 + ``{"errors": ["You need to sign in or sign up before continuing."]}``.
     The "Invalid login credentials" message Chatwoot uses comes from
     the ``Auth::SessionsController#create`` path (bad-creds on sign_in)
     — distinct surface, distinct body.

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

from dataclasses import dataclass

from fastapi import Depends, Path, Request, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth.devise_token_auth import (
    HEADER_ACCESS_TOKEN,
    HEADER_CLIENT,
    HEADER_UID,
    verify_auth_token,
)
from app.core.current import current_user_ctx
from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.domains.accounts.models import Account
from app.domains.users.models import ACCOUNT_USER_ROLE_ADMINISTRATOR, AccountUser, User

# Mirrors devise's ``authenticate_user!`` 401 envelope. The distinct
# "Invalid login credentials" body fires only on the ``/auth/sign_in``
# bad-creds path — :mod:`app.domains.auth.router` owns that.
_UNAUTHENTICATED = {
    "errors": ["You need to sign in or sign up before continuing."]
}


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
    """Require a valid devise-token-auth session. Raises 401 otherwise.

    The 401 body uses :class:`ChatwootHTTPException` (unwrapped) so the
    envelope matches devise's ``authenticate_user!`` byte-for-byte —
    ``{"errors": ["You need to sign in or sign up before continuing."]}``
    rather than FastAPI's default ``{"detail": ...}`` wrap.
    """
    headers = _read_auth_headers(request)
    if headers is None:
        raise ChatwootHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_UNAUTHENTICATED
        )
    access_token, client, uid = headers

    user = await _load_user(session, uid)
    if user is None:
        raise ChatwootHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_UNAUTHENTICATED
        )

    if not verify_auth_token(
        user.tokens, client=client, access_token=access_token
    ):
        raise ChatwootHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_UNAUTHENTICATED
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


# ============================================================================
# Account-scoped authorization — the Rails ``Current.account`` + Pundit stack
# ============================================================================
@dataclass(slots=True)
class AccountContext:
    """The tuple Rails mints for every request under ``Api::V1::Accounts::``.

    Chatwoot's ``Api::V1::Accounts::BaseController`` runs two before_actions:

      * ``ensure_current_account`` — sets ``Current.account`` from
        ``params[:account_id]`` after asserting the current user is a
        member.
      * ``ensure_current_account_user`` — sets ``Current.account_user``,
        the :class:`AccountUser` row for ``(current_user, account)``.

    We carry the same three pieces through a single dependency so policies
    can read ``ctx.account_user.role`` without a second DB hit.
    """

    user: User
    account: Account
    account_user: AccountUser

    @property
    def is_administrator(self) -> bool:
        return self.account_user.role == ACCOUNT_USER_ROLE_ADMINISTRATOR


async def account_context(
    account_id: int = Path(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> AccountContext:
    """Populate :class:`AccountContext` or 404.

    The 404-not-401 choice matches Rails exactly: a non-member hitting a
    scoped endpoint gets a 404 because ``current_user.accounts.find(id)``
    raises ``ActiveRecord::RecordNotFound``. We deliberately don't leak
    membership information.
    """
    stmt = (
        select(AccountUser, Account)
        .join(Account, Account.id == AccountUser.account_id)  # type: ignore[arg-type]
        .where(Account.id == account_id, AccountUser.user_id == user.id)
    )
    row = (await session.exec(stmt)).first()
    if row is None:
        # Rails' RequestExceptionHandler renders ``{"error": "Resource
        # could not be found"}`` for every ``ActiveRecord::RecordNotFound``
        # under Api::V1::Accounts::. Wire parity — *not* ``{"message": ...}``.
        raise ChatwootHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Resource could not be found"},
        )
    au, account = row
    # Mirrors Rails' ``Current.user = current_user`` at the top of the
    # ``Api::V1::Accounts::BaseController`` request cycle. Read by the
    # ActionCableListener to stamp the ``performer`` field on broadcasts.
    current_user_ctx.set(user)
    return AccountContext(user=user, account=account, account_user=au)


def require_admin(ctx: AccountContext = Depends(account_context)) -> AccountContext:
    """Mirror of Pundit's ``@account_user.administrator?`` gate.

    Chatwoot's ``check_authorization`` before_action invokes the action's
    policy method (e.g. ``InboxPolicy#create?``) which returns
    ``@account_user.administrator?``. A denial raises
    ``Pundit::NotAuthorizedError`` → a 401 via
    ``RequestExceptionHandler#render_unauthorized`` with the unwrapped
    body ``{"error": "You are not authorized to do this action"}``. We
    replicate the exact shape.
    """
    if not ctx.is_administrator:
        raise ChatwootHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "You are not authorized to do this action"},
        )
    return ctx
