"""HTTP-level tests for ``POST /auth/sign_in``.

Parity with ``DeviseOverrides::SessionsController#create`` +
``devise/_auth.json.jbuilder``:

  * 200 with ``{"data": {...user}}`` body on good credentials.
  * Response headers carry ``access-token``/``client``/``uid``/``expiry``/
    ``token-type`` (rotated on every sign_in).
  * 401 with ``{"errors": ["Invalid login credentials. Please try again."]}``
    for unknown email or bad password.
  * ``sign_in_count`` + ``current_sign_in_at`` are updated (Devise trackable).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.db import get_session
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
async def seeded_user(db_session):
    """Pre-create a confirmed user with a known password via AccountBuilder."""
    result = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent@rocket.example.com",
            account_name="Rocket Labs",
            user_full_name="A. Gent",
            user_password="Password123!",
            confirmed=True,
            locale="en",
        ),
    ).perform()
    return result


async def test_sign_in_success_returns_user_and_rotates_token(client, seeded_user):
    resp = await client.post(
        "/auth/sign_in",
        json={"email": "agent@rocket.example.com", "password": "Password123!"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "data" in body
    data = body["data"]

    # _user.json.jbuilder shape
    assert data["email"] == "agent@rocket.example.com"
    assert data["available_name"] == "A. Gent"
    assert data["account_id"] == seeded_user.account.id
    assert data["role"] == 1
    assert data["confirmed"] is True
    assert data["access_token"] == seeded_user.access_token.token
    assert len(data["accounts"]) == 1
    acct = data["accounts"][0]
    assert acct["name"] == "Rocket Labs"
    assert acct["status"] == 0  # active
    assert acct["permissions"] == ["administrator"]
    assert acct["availability_status"] == "online"

    # devise-token-auth headers
    assert resp.headers.get("access-token")
    assert resp.headers.get("client")
    assert resp.headers.get("uid") == "agent@rocket.example.com"
    assert resp.headers.get("token-type") == "Bearer"


async def test_sign_in_case_insensitive_email(client, seeded_user):
    resp = await client.post(
        "/auth/sign_in",
        json={"email": "AGENT@ROCKET.EXAMPLE.COM", "password": "Password123!"},
    )
    assert resp.status_code == 200


async def test_sign_in_rejects_bad_password(client, seeded_user):
    resp = await client.post(
        "/auth/sign_in",
        json={"email": "agent@rocket.example.com", "password": "wrong-guess"},
    )
    assert resp.status_code == 401
    # Body is devise-token-auth's default failure envelope — ``success:
    # false`` + ``errors`` array. No FastAPI ``detail`` wrapper (see
    # ChatwootHTTPException).
    assert resp.json() == {
        "success": False,
        "errors": ["Invalid login credentials. Please try again."],
    }


async def test_sign_in_rejects_unknown_email(client):
    resp = await client.post(
        "/auth/sign_in",
        json={"email": "ghost@rocket.example.com", "password": "Password123!"},
    )
    assert resp.status_code == 401


async def test_sign_in_updates_trackable_counters(client, seeded_user, db_session):
    before = (
        await db_session.exec(select(User).where(User.email == "agent@rocket.example.com"))
    ).one()
    initial_count = before.sign_in_count

    resp = await client.post(
        "/auth/sign_in",
        json={"email": "agent@rocket.example.com", "password": "Password123!"},
    )
    assert resp.status_code == 200

    await db_session.refresh(before)
    assert before.sign_in_count == initial_count + 1
    assert before.current_sign_in_at is not None


async def test_sign_out_invalidates_current_client_only(client, seeded_user, db_session):
    """DELETE /auth/sign_out drops the caller's client entry; other devices survive."""
    # Mint two client sessions on the same user (two devices).
    from app.core.auth.devise_token_auth import create_new_auth_token

    first_headers, tokens = create_new_auth_token(
        user_tokens=seeded_user.user.tokens, uid=seeded_user.user.uid
    )
    seeded_user.user.tokens = tokens
    db_session.add(seeded_user.user)
    await db_session.flush()

    second_headers, tokens = create_new_auth_token(
        user_tokens=seeded_user.user.tokens, uid=seeded_user.user.uid
    )
    seeded_user.user.tokens = tokens
    db_session.add(seeded_user.user)
    await db_session.flush()

    assert len(seeded_user.user.tokens) == 2

    # Sign out with the first device's headers.
    resp = await client.delete(
        "/auth/sign_out", headers=first_headers.as_response_headers()
    )
    assert resp.status_code == 200
    assert resp.json() == {"message": "Signed out successfully."}

    await db_session.refresh(seeded_user.user)
    assert first_headers.client not in seeded_user.user.tokens
    assert second_headers.client in seeded_user.user.tokens

    # The second device's headers still authenticate successfully.
    resp2 = await client.get(
        "/api/v1/profile", headers=second_headers.as_response_headers()
    )
    assert resp2.status_code == 200


async def test_sign_out_requires_auth(client):
    """No auth headers -> 401 (same envelope as every other protected call)."""
    resp = await client.delete("/auth/sign_out")
    assert resp.status_code == 401


async def test_sign_in_rejects_unconfirmed_user(client, db_session):
    """confirmed_at IS NULL should short-circuit to 401 (Devise Confirmable)."""
    await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="pending@rocket.example.com",
            account_name="Pending Inc",
            user_full_name="Pending",
            user_password="Password123!",
            confirmed=False,  # <-- key difference
        ),
    ).perform()

    resp = await client.post(
        "/auth/sign_in",
        json={"email": "pending@rocket.example.com", "password": "Password123!"},
    )
    assert resp.status_code == 401
    msg = resp.json()["errors"][0]
    assert "confirmation email" in msg.lower()
