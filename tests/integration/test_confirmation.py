"""HTTP + service tests for the email-confirmation flow.

Parity anchors (``DeviseOverrides::ConfirmationsController`` +
``Auth::ResendConfirmationsController``):

  * ``POST /auth/confirmation`` with a valid token → 200 with
    ``_auth.json.jbuilder`` body + rotated devise-token-auth headers,
    user's ``confirmed_at`` stamped.
  * Unknown token → 422 ``{"message": "Invalid token", "redirect_url": "/"}``.
  * Already-confirmed user → 422 ``{"message": "Already confirmed", ...}``.
  * ``POST /resend_confirmation`` → always 204 (no enumeration):
        - unknown email: 204, no side effects
        - confirmed email: 204, no new token issued
        - unconfirmed email: 204, fresh token stamped
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.auth.confirmation import (
    ConfirmationError,
    consume_confirmation_token,
    issue_confirmation_token,
)
from app.domains.users.models import User
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
async def unconfirmed_user(db_session):
    """A fresh user whose ``confirmed_at`` is NULL — simulates a signup
    path that required confirmation instead of the api-only auto-confirm.
    """
    result = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="rookie@rocket.example.com",
            account_name="Rookie Labs",
            user_full_name="Rookie",
            user_password="OriginalPass1!",
            confirmed=False,
        ),
    ).perform()
    return result


@pytest.fixture
async def confirmed_user(db_session):
    result = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="veteran@rocket.example.com",
            account_name="Veteran Labs",
            user_full_name="Vet Eran",
            user_password="OriginalPass1!",
            confirmed=True,
        ),
    ).perform()
    return result


# --------------------------------------------------------------- service layer


async def test_issue_stamps_plaintext_token_and_sent_at(db_session, unconfirmed_user):
    """Devise ``Confirmable`` stores the raw token in the DB (unlike
    reset tokens which are HMAC-hashed) — verify we mirror that."""
    issued = await issue_confirmation_token(db_session, unconfirmed_user.user)
    await db_session.refresh(unconfirmed_user.user)

    assert unconfirmed_user.user.confirmation_token == issued.raw_token
    assert unconfirmed_user.user.confirmation_sent_at is not None


async def test_consume_rejects_empty_token(db_session):
    got = await consume_confirmation_token(db_session, raw_token="")
    assert got is ConfirmationError.INVALID_TOKEN


async def test_consume_rejects_unknown_token(db_session, unconfirmed_user):
    got = await consume_confirmation_token(db_session, raw_token="totally-unknown")
    assert got is ConfirmationError.INVALID_TOKEN


async def test_consume_rejects_already_confirmed(db_session, confirmed_user):
    """A user whose ``confirmed_at`` is stamped should short-circuit to
    ``ALREADY_CONFIRMED`` — matches Ruby's second branch in
    ``render_confirmation_error``."""
    # Artificially stamp a confirmation_token to isolate the confirmed_at check.
    issued = await issue_confirmation_token(db_session, confirmed_user.user)
    got = await consume_confirmation_token(db_session, raw_token=issued.raw_token)
    assert got is ConfirmationError.ALREADY_CONFIRMED


# --------------------------------------------------------------- POST /auth/confirmation


async def test_confirmation_happy_path(client, db_session, unconfirmed_user):
    issued = await issue_confirmation_token(db_session, unconfirmed_user.user)

    resp = await client.post(
        "/auth/confirmation",
        json={"confirmation_token": issued.raw_token},
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    # _auth.json.jbuilder shape — same body as sign_in.
    assert body["data"]["email"] == "rookie@rocket.example.com"
    assert body["data"]["confirmed"] is True

    # Auto-login: response carries a fresh devise-token-auth session.
    assert resp.headers.get("access-token")
    assert resp.headers.get("client")
    assert resp.headers.get("uid") == "rookie@rocket.example.com"
    assert resp.headers.get("token-type") == "Bearer"

    await db_session.refresh(unconfirmed_user.user)
    assert unconfirmed_user.user.confirmed_at is not None


async def test_confirmation_rejects_unknown_token(client, unconfirmed_user):
    resp = await client.post(
        "/auth/confirmation",
        json={"confirmation_token": "never-issued"},
    )
    assert resp.status_code == 422
    # Body matches the Ruby ``render json: {message: ..., redirect_url: ...}``
    # envelope exactly — no FastAPI ``detail`` wrapping.
    assert resp.json() == {
        "message": "Invalid token",
        "redirect_url": "/",
    }


async def test_confirmation_rejects_already_confirmed(
    client, db_session, confirmed_user
):
    issued = await issue_confirmation_token(db_session, confirmed_user.user)
    resp = await client.post(
        "/auth/confirmation",
        json={"confirmation_token": issued.raw_token},
    )
    assert resp.status_code == 422
    assert resp.json() == {
        "message": "Already confirmed",
        "redirect_url": "/",
    }


# --------------------------------------------------------------- POST /resend_confirmation


async def test_resend_returns_204_for_unknown_email(client, db_session):
    """No enumeration: same 204 for an email we've never seen."""
    resp = await client.post(
        "/resend_confirmation",
        json={"email": "ghost@rocket.example.com"},
    )
    assert resp.status_code == 204
    # 204 bodies are empty per HTTP spec — httpx surfaces this as empty.
    assert resp.content == b""


async def test_resend_returns_204_for_confirmed_email(client, db_session, confirmed_user):
    """Already-confirmed users don't get a new token but we still 204."""
    # Ensure no token exists before.
    await db_session.refresh(confirmed_user.user)
    before_token = confirmed_user.user.confirmation_token
    before_sent = confirmed_user.user.confirmation_sent_at

    resp = await client.post(
        "/resend_confirmation",
        json={"email": "veteran@rocket.example.com"},
    )
    assert resp.status_code == 204

    await db_session.refresh(confirmed_user.user)
    # Untouched — the resend service short-circuits on confirmed users.
    assert confirmed_user.user.confirmation_token == before_token
    assert confirmed_user.user.confirmation_sent_at == before_sent


async def test_resend_issues_fresh_token_for_unconfirmed(
    client, db_session, unconfirmed_user
):
    await db_session.refresh(unconfirmed_user.user)
    assert unconfirmed_user.user.confirmation_token is None

    resp = await client.post(
        "/resend_confirmation",
        json={"email": "rookie@rocket.example.com"},
    )
    assert resp.status_code == 204

    # The Session the service wrote to is the same one bound to the test
    # fixture (via the get_session override), so we can see the change
    # directly on the user row.
    refreshed = (
        await db_session.exec(
            select(User).where(User.email == "rookie@rocket.example.com")
        )
    ).one()
    assert refreshed.confirmation_token is not None
    assert refreshed.confirmation_sent_at is not None


async def test_resend_is_case_insensitive(client, db_session, unconfirmed_user):
    resp = await client.post(
        "/resend_confirmation",
        json={"email": "ROOKIE@ROCKET.EXAMPLE.COM"},
    )
    assert resp.status_code == 204

    refreshed = (
        await db_session.exec(
            select(User).where(User.email == "rookie@rocket.example.com")
        )
    ).one()
    assert refreshed.confirmation_token is not None
