"""Account + user signup builder.

Ports `reference/chatwoot/app/builders/account_builder.rb` 1:1 (except where
Rails-specific concerns translate differently):

  Ruby                                       Python equivalent
  -----------------------------------------  --------------------------------
  AccountBuilder.perform                     AccountBuilder.perform (async)
  Account::SignUpEmailValidationService      email_validator.validate_signup_email
  AccessTokenable `after_create` callback    _create_access_token() in txn
  Pubsubable `has_secure_token :pubsub_token`  base58_token() on User init
  Devise `before_validation :set_password_and_uid` on :create
                                              _set_uid_and_password() pre-insert
  `User#confirm` (from Devise Confirmable)   _confirm() — sets confirmed_at
  link_user_to_account                       _link_user_to_account (role=admin)

Rails-side callbacks that we intentionally skip (none are observable on the
Phase 1 endpoints):

  * Avatarable `after_save :avatar_url_callback` — handled lazily when we
    read `avatar_url` from the user (returns empty-string default).
  * Pubsubable `before_save :rotate_pubsub_token` — password rotation
    semantics; first-time signup is identical because we generate a token
    on create.
  * `after_destroy_async :remove_macros` — destroy-time only.

All DB work runs inside a single SQLAlchemy transaction, matching
``ActiveRecord::Base.transaction`` in Ruby.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import hash_password
from app.core.tokens import base58_token
from app.domains.accounts.email_validator import validate_signup_email
from app.domains.accounts.exceptions import UserErrors, UserExists
from app.domains.accounts.models import (
    ACCOUNT_LOCALE_CODE_TO_INT,
    Account,
)
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_ADMINISTRATOR,
    AccessToken,
    AccountUser,
    User,
)


@dataclass(slots=True)
class AccountBuilderParams:
    """Input bag mirroring the keyword args of ``AccountBuilder.new``."""

    email: str
    account_name: str | None = None
    user_full_name: str | None = None
    user_password: str | None = None
    confirmed: bool = False
    locale: str | None = None  # ISO code; maps to int via ACCOUNT_LOCALE_CODE_TO_INT
    super_admin: bool = False
    # If the caller is already authenticated (dashboard "add account" flow),
    # the existing user is passed in and re-linked to the new account instead
    # of being re-created. `None` means unauthenticated signup.
    existing_user: User | None = None


@dataclass(slots=True)
class AccountBuilderResult:
    """Mirrors `[user, account]` tuple returned by the Ruby builder."""

    user: User
    account: Account
    access_token: AccessToken  # eagerly created — matches AccessTokenable after_create
    account_user: AccountUser  # the freshly linked (or re-linked) membership


class AccountBuilder:
    """Atomically create Account + User + AccountUser + AccessToken."""

    def __init__(self, session: AsyncSession, params: AccountBuilderParams) -> None:
        self.session = session
        self.params = params

    async def perform(self) -> AccountBuilderResult:
        """Run the full signup transaction.

        Mirrors ``def perform`` in AccountBuilder.rb — validations only run
        when we're creating a brand-new user (Rails branches on ``@user.nil?``).
        Exceptions propagate to the caller; no rescue-and-reraise needed as
        FastAPI exception handlers already log.
        """
        p = self.params

        if p.existing_user is None:
            validate_signup_email(p.email)
            await self._ensure_email_unused()

        # Single SQLAlchemy transaction (nested in caller's session).
        # We use a SAVEPOINT so the builder can be called inside an
        # outer request-scoped transaction without accidentally committing.
        async with self.session.begin_nested():
            account = await self._create_account()

            if p.existing_user is not None:
                user = p.existing_user
            else:
                user = await self._create_user()

            account_user = await self._link_user_to_account(user, account)

            # AccessTokenable `after_create` — only for brand-new users.
            if p.existing_user is None:
                access_token = await self._create_access_token(user)
            else:
                access_token = await self._get_access_token(user)

        return AccountBuilderResult(
            user=user,
            account=account,
            access_token=access_token,
            account_user=account_user,
        )

    # --------------------------------------------------------------- helpers

    async def _ensure_email_unused(self) -> None:
        """`User.exists?(email: @email)` → raise UserExists."""
        email = (self.params.email or "").lower()
        result = await self.session.exec(select(User.id).where(User.email == email))
        if result.first() is not None:
            raise UserExists(payload={"email": self.params.email})

    async def _create_account(self) -> Account:
        """`Account.create!(name:, locale:)` in Ruby."""
        locale_int = ACCOUNT_LOCALE_CODE_TO_INT.get(self.params.locale or "en", 0)
        account = Account(
            name=self.params.account_name or "",
            locale=locale_int,
        )
        self.session.add(account)
        await self.session.flush()  # populate account.id for subsequent inserts
        return account

    async def _create_user(self) -> User:
        """`User.create!` with Devise hooks inlined.

        Equivalent to ``def create_user`` in account_builder.rb plus the
        Devise ``before_validation :set_password_and_uid`` callback which
        copies email → uid on create, and ``User#confirm`` which stamps
        ``confirmed_at``.
        """
        p = self.params
        if not p.user_password:
            raise UserErrors(payload={"password": ["can't be blank"]})

        email = (p.email or "").lower()
        user = User(
            provider="email",
            uid=email,  # matches `set_password_and_uid` callback
            email=email,
            encrypted_password=hash_password(p.user_password),
            name=p.user_full_name or "",
            pubsub_token=base58_token(24),  # Pubsubable `has_secure_token :pubsub_token`
            type="SuperAdmin" if p.super_admin else None,
            confirmed_at=datetime.now(UTC).replace(tzinfo=None) if p.confirmed else None,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def _link_user_to_account(self, user: User, account: Account) -> AccountUser:
        """`AccountUser.create!(..., role: administrator)`.

        The builder always creates the linking user as administrator — this
        is the "owner" of the new account. In Rails it's the raw integer enum
        value ``AccountUser.roles['administrator']``; we use the Python
        constant for the same value.
        """
        account_user = AccountUser(
            account_id=account.id,
            user_id=user.id,
            role=ACCOUNT_USER_ROLE_ADMINISTRATOR,
        )
        self.session.add(account_user)
        await self.session.flush()
        return account_user

    async def _create_access_token(self, user: User) -> AccessToken:
        """AccessTokenable: ``after_create :create_access_token``.

        Chatwoot generates the token via ``has_secure_token`` → Rails'
        ``SecureRandom.base58(24)``. We use the same alphabet/length via
        :func:`app.core.tokens.base58_token`.
        """
        token = AccessToken(
            owner_type="User",
            owner_id=user.id,
            token=base58_token(24),
        )
        self.session.add(token)
        await self.session.flush()
        return token

    async def _get_access_token(self, user: User) -> AccessToken:
        """Fetch the existing polymorphic token when we re-link an existing user."""
        stmt = select(AccessToken).where(
            AccessToken.owner_type == "User",
            AccessToken.owner_id == user.id,
        )
        result = await self.session.exec(stmt)
        token = result.first()
        if token is None:
            # Should not happen for a persisted user, but the AccessTokenable
            # concern backfills on read in Rails — mirror that behaviour.
            return await self._create_access_token(user)
        return token
