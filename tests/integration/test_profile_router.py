"""HTTP-level tests for ``GET /api/v1/profile`` + ``PUT /api/v1/profile``.

Parity anchors:
  * ``profiles_controller.rb#show`` → ``show.json.jbuilder`` → ``_user.json.jbuilder``.
  * ``profiles_controller.rb#update`` — wraps body in ``profile:``, branches
    on password presence requiring ``current_password`` match.
  * Missing / bad devise-token-auth headers → 401 with devise-token-auth
    envelope.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.core.security import verify_password
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
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
async def authed(db_session):
    """Seed a user + mint a devise-token-auth session; return (user, headers).

    Mirrors what ``/auth/sign_in`` does in production: AccountBuilder makes
    the row, then ``create_new_auth_token`` stamps ``user.tokens`` with the
    bcrypt-hashed token. We return the raw header triple to attach to the
    outbound request.
    """
    result = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="me@rocket.example.com",
            account_name="My Workspace",
            user_full_name="Me Myself",
            user_password="Password123!",
            confirmed=True,
            locale="en",
        ),
    ).perform()

    headers, new_tokens = create_new_auth_token(
        user_tokens=result.user.tokens, uid=result.user.uid
    )
    result.user.tokens = new_tokens
    db_session.add(result.user)
    await db_session.flush()

    return result.user, headers.as_response_headers()


async def test_show_profile_requires_auth(client):
    resp = await client.get("/api/v1/profile")
    assert resp.status_code == 401
    # Mirrors devise's ``authenticate_user!`` envelope — unwrapped
    # ``{"errors": [...]}`` (NOT the bad-creds string, which is
    # reserved for the ``/auth/sign_in`` failure path).
    assert resp.json() == {
        "errors": ["You need to sign in or sign up before continuing."]
    }


async def test_show_profile_returns_current_user(client, authed):
    user, headers = authed
    resp = await client.get("/api/v1/profile", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["email"] == "me@rocket.example.com"
    assert data["id"] == user.id
    assert data["role"] == 1  # administrator
    assert len(data["accounts"]) == 1


async def test_show_profile_rejects_bad_token(client, authed):
    _, headers = authed
    bad = dict(headers)
    bad["access-token"] = "definitely-not-the-right-one"
    resp = await client.get("/api/v1/profile", headers=bad)
    assert resp.status_code == 401


async def test_show_profile_rejects_wrong_client(client, authed):
    _, headers = authed
    bad = dict(headers)
    bad["client"] = "unknown-client-id"
    resp = await client.get("/api/v1/profile", headers=bad)
    assert resp.status_code == 401


async def test_update_profile_fields(client, authed, db_session):
    user, headers = authed
    resp = await client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "profile": {
                "name": "Renamed Person",
                "display_name": "RP",
                "message_signature": "Cheers, RP",
                "ui_settings": {"theme": "dark"},
            }
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["name"] == "Renamed Person"
    assert data["display_name"] == "RP"
    assert data["available_name"] == "RP"  # display_name wins
    assert data["message_signature"] == "Cheers, RP"
    assert data["ui_settings"] == {"theme": "dark"}

    await db_session.refresh(user)
    assert user.name == "Renamed Person"
    assert user.ui_settings == {"theme": "dark"}


async def test_update_profile_password_requires_current_password(client, authed):
    _, headers = authed
    resp = await client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "profile": {
                "password": "NewPassword456!",
                "current_password": "wrong-old-password",
            }
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["message"] == "Invalid current password"


async def test_update_profile_rotates_password(client, authed, db_session):
    user, headers = authed
    resp = await client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "profile": {
                "password": "NewPassword456!",
                "password_confirmation": "NewPassword456!",
                "current_password": "Password123!",
            }
        },
    )
    assert resp.status_code == 200, resp.text

    await db_session.refresh(user)
    assert verify_password("NewPassword456!", user.encrypted_password)
    assert not verify_password("Password123!", user.encrypted_password)


async def test_update_profile_merges_custom_attributes(client, authed, db_session):
    user, headers = authed
    # Seed an unrelated custom attribute so we can prove merge (not replace).
    user.custom_attributes = {"industry": "saas"}
    db_session.add(user)
    await db_session.flush()

    resp = await client.put(
        "/api/v1/profile",
        headers=headers,
        json={"profile": {"phone_number": "+1-555-0100"}},
    )
    assert resp.status_code == 200

    fresh = (
        await db_session.exec(select(User).where(User.id == user.id))
    ).one()
    assert fresh.custom_attributes == {"industry": "saas", "phone_number": "+1-555-0100"}
