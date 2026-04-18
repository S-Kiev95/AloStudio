"""HTTP-level tests for ``POST /api/v1/accounts``.

Asserts the request -> response shape + devise-token-auth headers end to
end through the FastAPI app, using the per-test ``db_session`` fixture
mounted as the ``get_session`` dependency so rows roll back at teardown.

Parity checks against ``accounts_controller#create`` +
``accounts/create.json.jbuilder``:

  * Body envelope: ``{"data": {...}}`` with id, account_id, role=admin,
    access_token, accounts=[{id,name,active_at,role,locale}], etc.
  * Response headers carry ``access-token``, ``client``, ``uid``,
    ``expiry``, ``token-type: Bearer``.
  * Missing account_name AND user_full_name -> 422.
  * Duplicate email -> 422 with Chatwoot's error envelope.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import get_session
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    """httpx client with ``get_session`` overridden to the test session.

    We yield the same ``db_session`` from the override so the router writes
    into the rolled-back transaction. ``commit()`` on the test session is a
    no-op inside a SAVEPOINT; the outer rollback cleans up either way.
    """

    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


async def test_signup_returns_user_payload_with_auth_headers(client):
    resp = await client.post(
        "/api/v1/accounts",
        json={
            "account_name": "Rocket Labs",
            "email": "founder@rocket.example.com",
            "password": "Password123!",
            "locale": "en",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "data" in body
    data = body["data"]

    # Shape parity with accounts/create.json.jbuilder
    assert data["email"] == "founder@rocket.example.com"
    assert data["provider"] == "email"
    assert data["uid"] == "founder@rocket.example.com"
    assert data["account_id"] == data["accounts"][0]["id"]
    assert data["role"] == 1  # administrator
    assert data["confirmed"] is True
    assert isinstance(data["access_token"], str) and len(data["access_token"]) == 24
    assert len(data["accounts"]) == 1
    nested = data["accounts"][0]
    assert nested["name"] == "Rocket Labs"
    assert nested["role"] == 1
    assert nested["locale"] == 0

    # devise-token-auth response headers
    assert resp.headers.get("access-token")
    assert resp.headers.get("client")
    assert resp.headers.get("uid") == "founder@rocket.example.com"
    assert resp.headers.get("token-type") == "Bearer"
    assert int(resp.headers["expiry"]) > 0


async def test_signup_accepts_user_full_name_when_account_name_missing(client):
    resp = await client.post(
        "/api/v1/accounts",
        json={
            "user_full_name": "Solo Founder",
            "email": "solo@rocket.example.com",
            "password": "Password123!",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["name"] == "Solo Founder"


async def test_signup_rejects_missing_names(client):
    resp = await client.post(
        "/api/v1/accounts",
        json={"email": "nameless@rocket.example.com", "password": "Password123!"},
    )
    assert resp.status_code == 422
    # Chatwoot-shape: {"message": "...", ...payload}.
    assert resp.json()["detail"]["message"] == "Invalid params"


async def test_signup_rejects_duplicate_email(client):
    await client.post(
        "/api/v1/accounts",
        json={
            "account_name": "Dupe A",
            "email": "dupe@rocket.example.com",
            "password": "Password123!",
        },
    )
    resp = await client.post(
        "/api/v1/accounts",
        json={
            "account_name": "Dupe B",
            "email": "dupe@rocket.example.com",
            "password": "Password123!",
        },
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "already exists" in detail["message"].lower()
    assert detail["email"] == "dupe@rocket.example.com"


async def test_signup_rejects_disposable_email(client):
    resp = await client.post(
        "/api/v1/accounts",
        json={
            "account_name": "Throwaway Corp",
            "email": "burner@mailinator.com",
            "password": "Password123!",
        },
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail == {"message": "Email is invalid", "valid": True, "disposable": True}
