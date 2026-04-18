"""HTTP-level tests for ``GET /api/v1/accounts/:id`` + ``PATCH`` same.

Parity anchors:
  * ``accounts_controller.rb#show`` → ``accounts/show.json.jbuilder`` →
    ``_account.json.jbuilder`` (whitelisted custom_attributes keys).
  * ``accounts_controller.rb#update`` — merge semantics for
    ``custom_attributes`` and ``settings``; assign for scalars; auto-advance
    onboarding_step from 'account_update' → 'invite_team'.
  * ``fetch_account`` scopes the lookup via ``current_user.accounts`` so
    non-members get 404 (not 403).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
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
    result = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="owner@rocket.example.com",
            account_name="Rocket Labs",
            user_full_name="Owner",
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
    return result, headers.as_response_headers()


async def test_show_account_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1")
    assert resp.status_code == 401


async def test_show_account_returns_scoped_payload(client, authed):
    built, headers = authed
    resp = await client.get(f"/api/v1/accounts/{built.account.id}", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == built.account.id
    assert body["name"] == "Rocket Labs"
    assert body["locale"] == 0
    assert body["status"] == 0  # active
    # Phase 1 stubs — present but empty.
    assert body["features"] == {}
    assert body["cache_keys"] == {}
    # No custom_attributes key when the column is empty (jbuilder `if present?`).
    assert "custom_attributes" not in body


async def test_show_account_404_for_non_member(client, authed, db_session):
    _, headers = authed
    # A second, unrelated account the authed user does NOT belong to.
    other = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="stranger@rocket.example.com",
            account_name="Other Corp",
            user_full_name="Stranger",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()

    resp = await client.get(f"/api/v1/accounts/{other.account.id}", headers=headers)
    assert resp.status_code == 404


async def test_update_account_assigns_scalars(client, authed, db_session):
    built, headers = authed
    resp = await client.patch(
        f"/api/v1/accounts/{built.account.id}",
        headers=headers,
        json={
            "name": "Rocket Labs 2.0",
            "domain": "rocket.example",
            "support_email": "help@rocket.example.com",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Rocket Labs 2.0"
    assert body["domain"] == "rocket.example"
    assert body["support_email"] == "help@rocket.example.com"

    await db_session.refresh(built.account)
    assert built.account.name == "Rocket Labs 2.0"


async def test_update_account_merges_custom_attributes(client, authed, db_session):
    built, headers = authed
    # Seed an unrelated key that must survive.
    built.account.custom_attributes = {"plan_name": "pro"}
    db_session.add(built.account)
    await db_session.flush()

    resp = await client.patch(
        f"/api/v1/accounts/{built.account.id}",
        headers=headers,
        json={"industry": "saas", "company_size": "11-50"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ca = body["custom_attributes"]
    assert ca["plan_name"] == "pro"
    assert ca["industry"] == "saas"
    assert ca["company_size"] == "11-50"


async def test_update_account_advances_onboarding_step(client, authed, db_session):
    built, headers = authed
    built.account.custom_attributes = {"onboarding_step": "account_update"}
    db_session.add(built.account)
    await db_session.flush()

    # Any update (even an empty merge) should trip the onboarding_step rule.
    resp = await client.patch(
        f"/api/v1/accounts/{built.account.id}",
        headers=headers,
        json={"name": "Rocket Labs v2"},
    )
    assert resp.status_code == 200
    await db_session.refresh(built.account)
    assert built.account.custom_attributes["onboarding_step"] == "invite_team"


async def test_update_account_merges_settings(client, authed, db_session):
    built, headers = authed
    built.account.settings = {"audio_transcriptions": False}
    db_session.add(built.account)
    await db_session.flush()

    resp = await client.patch(
        f"/api/v1/accounts/{built.account.id}",
        headers=headers,
        json={"auto_resolve_after": 720, "auto_resolve_message": "Auto-closed"},
    )
    assert resp.status_code == 200
    await db_session.refresh(built.account)
    assert built.account.settings == {
        "audio_transcriptions": False,
        "auto_resolve_after": 720,
        "auto_resolve_message": "Auto-closed",
    }
