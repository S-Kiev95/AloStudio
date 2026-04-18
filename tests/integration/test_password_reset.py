"""HTTP + service tests for the password reset flow.

Parity anchors:
  * ``POST /auth/password`` → always 200, generic body — no email
    enumeration (Chatwoot's ``DeviseOverrides::PasswordsController#create``).
  * ``PUT /auth/password`` → on success emits ``_user.json.jbuilder`` body
    + devise-token-auth headers; on bad token 422 with
    ``{"message": "Invalid token", "redirect_url": "/"}``.
  * Password reset invalidates every existing devise-token-auth session
    (``remove_tokens_after_password_reset = true``).
  * Expired tokens (> 6h) are rejected.
  * An unconfirmed user becomes confirmed as a side effect of a
    successful reset (Devise Recoverable quirk).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.core.security import verify_password
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.auth.password_reset import (
    _digest_token,
    consume_password_reset,
    request_password_reset,
)
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
async def seeded_user(db_session):
    result = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="forgetful@rocket.example.com",
            account_name="Forgetful Labs",
            user_full_name="Forgetful",
            user_password="OriginalPass1!",
            confirmed=True,
        ),
    ).perform()
    return result.user


async def test_request_reset_stores_digest_never_raw(db_session, seeded_user):
    issued = await request_password_reset(db_session, "forgetful@rocket.example.com")
    assert issued is not None
    # The raw is returned to the caller (simulates the mailer pickup) but
    # the DB stores only the HMAC digest.
    await db_session.refresh(seeded_user)
    assert seeded_user.reset_password_token is not None
    assert seeded_user.reset_password_token != issued.raw_token
    assert seeded_user.reset_password_token == _digest_token(issued.raw_token)
    assert seeded_user.reset_password_sent_at is not None


async def test_request_reset_endpoint_always_returns_200(client, db_session, seeded_user):
    resp = await client.post(
        "/auth/password", json={"email": "forgetful@rocket.example.com"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "instructions" in body["message"].lower()


async def test_request_reset_for_unknown_email_does_not_leak(client):
    """No enumeration: same 200 + same body for an email we've never seen."""
    resp = await client.post(
        "/auth/password", json={"email": "never-seen@rocket.example.com"}
    )
    assert resp.status_code == 200
    assert "instructions" in resp.json()["message"].lower()


async def test_apply_reset_happy_path(client, db_session, seeded_user):
    issued = await request_password_reset(db_session, "forgetful@rocket.example.com")
    assert issued is not None

    resp = await client.put(
        "/auth/password",
        json={
            "reset_password_token": issued.raw_token,
            "password": "BrandNewPass2@",
            "password_confirmation": "BrandNewPass2@",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"]["email"] == "forgetful@rocket.example.com"

    # Response headers carry a freshly-minted devise-token-auth session.
    assert resp.headers.get("access-token")
    assert resp.headers.get("client")
    assert resp.headers.get("uid") == "forgetful@rocket.example.com"

    # New password works, old one doesn't, reset columns cleared.
    await db_session.refresh(seeded_user)
    assert verify_password("BrandNewPass2@", seeded_user.encrypted_password)
    assert not verify_password("OriginalPass1!", seeded_user.encrypted_password)
    assert seeded_user.reset_password_token is None
    assert seeded_user.reset_password_sent_at is None


async def test_apply_reset_rejects_bad_token(client, seeded_user):
    resp = await client.put(
        "/auth/password",
        json={
            "reset_password_token": "totally-made-up-token",
            "password": "BrandNewPass2@",
            "password_confirmation": "BrandNewPass2@",
        },
    )
    assert resp.status_code == 422
    # Body matches Ruby ``render json: {message: ..., redirect_url: ...}``
    # exactly — no FastAPI ``detail`` wrapper.
    assert resp.json() == {"message": "Invalid token", "redirect_url": "/"}


async def test_apply_reset_rejects_confirmation_mismatch(client, db_session, seeded_user):
    issued = await request_password_reset(db_session, "forgetful@rocket.example.com")
    assert issued is not None
    resp = await client.put(
        "/auth/password",
        json={
            "reset_password_token": issued.raw_token,
            "password": "BrandNewPass2@",
            "password_confirmation": "DifferentPass3#",
        },
    )
    assert resp.status_code == 422


async def test_apply_reset_invalidates_existing_sessions(client, db_session, seeded_user):
    """``remove_tokens_after_password_reset = true`` — existing devices log out."""
    # Mint a device session up front.
    old_headers, new_tokens = create_new_auth_token(
        user_tokens=seeded_user.tokens, uid=seeded_user.uid
    )
    seeded_user.tokens = new_tokens
    db_session.add(seeded_user)
    await db_session.flush()

    # Confirm the old session works against a protected endpoint.
    ok = await client.get(
        "/api/v1/profile", headers=old_headers.as_response_headers()
    )
    assert ok.status_code == 200

    issued = await request_password_reset(db_session, "forgetful@rocket.example.com")
    assert issued is not None

    resp = await client.put(
        "/auth/password",
        json={
            "reset_password_token": issued.raw_token,
            "password": "BrandNewPass2@",
        },
    )
    assert resp.status_code == 200

    # Old device's headers are now rejected.
    gone = await client.get(
        "/api/v1/profile", headers=old_headers.as_response_headers()
    )
    assert gone.status_code == 401


async def test_apply_reset_rejects_expired_token(client, db_session, seeded_user):
    """reset_password_sent_at older than 6h -> 422 even with a known token."""
    issued = await request_password_reset(db_session, "forgetful@rocket.example.com")
    assert issued is not None
    # Back-date the timestamp just past the window (Devise default 6h).
    seeded_user.reset_password_sent_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=6, minutes=1)
    db_session.add(seeded_user)
    await db_session.flush()

    resp = await client.put(
        "/auth/password",
        json={
            "reset_password_token": issued.raw_token,
            "password": "BrandNewPass2@",
        },
    )
    assert resp.status_code == 422


async def test_apply_reset_confirms_unconfirmed_user(client, db_session):
    """Recoverable side effect: resetting an unconfirmed user's password
    also stamps ``confirmed_at``."""
    # Build an unconfirmed user directly (AccountBuilder supports this).
    built = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="pending@rocket.example.com",
            account_name="Pending Inc",
            user_full_name="Pending",
            user_password="OriginalPass1!",
            confirmed=False,
        ),
    ).perform()
    assert built.user.confirmed_at is None

    issued = await request_password_reset(db_session, "pending@rocket.example.com")
    assert issued is not None

    resp = await client.put(
        "/auth/password",
        json={
            "reset_password_token": issued.raw_token,
            "password": "BrandNewPass2@",
        },
    )
    assert resp.status_code == 200
    await db_session.refresh(built.user)
    assert built.user.confirmed_at is not None


async def test_service_returns_none_for_unknown_email(db_session):
    """Service-level path: unknown email -> None (no leak from the router)."""
    got = await request_password_reset(db_session, "nobody@rocket.example.com")
    assert got is None


async def test_service_consume_returns_none_for_bad_token(db_session, seeded_user):
    got = await consume_password_reset(
        db_session, raw_token="wrong", password="anything"
    )
    assert got is None
