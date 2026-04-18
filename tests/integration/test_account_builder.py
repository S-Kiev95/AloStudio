"""Integration tests for AccountBuilder.

Runs against alostudio_test (see tests/conftest.py env defaults). The nested
transaction in ``db_session`` rolls back at teardown — tests are order-
independent and leave no residue.

Parity with Chatwoot:
  * `AccountBuilder.new(...).perform` returns `[user, account]` — our
    result object exposes both plus the freshly-created AccessToken and
    AccountUser so callers don't have to re-query.
  * User.email is downcased, uid mirrors email, pubsub_token is set.
  * AccessToken is created with owner_type=User, owner_id=user.id and a
    24-char Base58 token.
  * The creator is linked as administrator role.
"""

from __future__ import annotations

import pytest
from sqlmodel import select

from app.domains.accounts.exceptions import InvalidEmail, UserExists
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_ADMINISTRATOR,
    AccessToken,
    AccountUser,
    User,
)

pytestmark = pytest.mark.integration


async def test_builder_creates_account_user_membership_and_token(db_session):
    result = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="Alice@Example.com",
            account_name="Alice Corp",
            user_full_name="Alice Example",
            user_password="Password123!",
            confirmed=True,
            locale="en",
        ),
    ).perform()

    assert result.account.id is not None
    assert result.account.name == "Alice Corp"
    assert result.account.locale == 0  # "en"

    assert result.user.id is not None
    assert result.user.email == "alice@example.com"  # downcased
    assert result.user.uid == "alice@example.com"
    assert result.user.provider == "email"
    assert result.user.name == "Alice Example"
    assert result.user.pubsub_token and len(result.user.pubsub_token) == 24
    assert result.user.encrypted_password.startswith("$2b$")  # bcrypt
    assert result.user.confirmed_at is not None

    assert result.account_user.role == ACCOUNT_USER_ROLE_ADMINISTRATOR
    assert result.account_user.account_id == result.account.id
    assert result.account_user.user_id == result.user.id

    assert result.access_token.owner_type == "User"
    assert result.access_token.owner_id == result.user.id
    assert result.access_token.token and len(result.access_token.token) == 24


async def test_builder_rejects_duplicate_email(db_session):
    params = AccountBuilderParams(
        email="dup@example.com",
        account_name="First",
        user_full_name="First Owner",
        user_password="Password123!",
        confirmed=True,
    )
    await AccountBuilder(db_session, params).perform()

    with pytest.raises(UserExists) as exc:
        await AccountBuilder(
            db_session,
            AccountBuilderParams(
                email="DUP@example.com",  # case-insensitive match
                account_name="Second",
                user_full_name="Second Owner",
                user_password="Password123!",
            ),
        ).perform()
    assert exc.value.payload == {"email": "DUP@example.com"}


async def test_builder_rejects_invalid_email_shape(db_session):
    with pytest.raises(InvalidEmail) as exc:
        await AccountBuilder(
            db_session,
            AccountBuilderParams(
                email="not-an-email",
                account_name="Broken",
                user_full_name="B Owner",
                user_password="Password123!",
            ),
        ).perform()
    # Matches the Chatwoot error payload shape.
    assert exc.value.payload == {"valid": False, "disposable": None}


async def test_builder_flags_disposable_email(db_session):
    with pytest.raises(InvalidEmail) as exc:
        await AccountBuilder(
            db_session,
            AccountBuilderParams(
                email="throwaway@mailinator.com",
                account_name="Disposable",
                user_full_name="D Owner",
                user_password="Password123!",
            ),
        ).perform()
    assert exc.value.payload == {"valid": True, "disposable": True}


async def test_builder_links_existing_user_without_recreating(db_session):
    # First, a regular signup creates user + account A.
    first = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="multi@example.com",
            account_name="Workspace A",
            user_full_name="Multi Tenant",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()

    # Now pretend that same user (already authenticated in the dashboard)
    # creates a second account — the builder should link without creating
    # a new User row.
    second = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=first.user.email or "",
            account_name="Workspace B",
            existing_user=first.user,
        ),
    ).perform()

    assert second.user.id == first.user.id
    assert second.account.id != first.account.id
    # AccessToken is the SAME one (we don't mint a second token per account).
    assert second.access_token.id == first.access_token.id

    # And there must be exactly two AccountUser rows for this user.
    memberships = (
        await db_session.exec(select(AccountUser).where(AccountUser.user_id == first.user.id))
    ).all()
    assert {m.account_id for m in memberships} == {first.account.id, second.account.id}
    assert all(m.role == ACCOUNT_USER_ROLE_ADMINISTRATOR for m in memberships)


async def test_builder_persists_in_db(db_session):
    """End-to-end: commit-visible rows match what the builder returned."""
    result = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="persist@example.com",
            account_name="Persist Inc",
            user_full_name="P Owner",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()

    user_row = (
        await db_session.exec(select(User).where(User.email == "persist@example.com"))
    ).one()
    assert user_row.id == result.user.id

    token_row = (
        await db_session.exec(
            select(AccessToken).where(AccessToken.owner_id == result.user.id)
        )
    ).one()
    assert token_row.token == result.access_token.token
