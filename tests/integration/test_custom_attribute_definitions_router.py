"""HTTP-level tests for Phase 3
``/api/v1/accounts/:id/custom_attribute_definitions``.

Parity anchors:
  * ``Api::V1::Accounts::CustomAttributeDefinitionsController``
  * ``_custom_attribute_definition.json.jbuilder``

Coverage:
  * Auth gate (401 unauthenticated)
  * Create + wire shape (ISO-8601 timestamps — not unix, unlike Contact)
  * Create validates key regex + STANDARD_ATTRIBUTE_KEYS conflict
  * Index filters by ``attribute_model`` when supplied
  * Show + update + destroy (204 on destroy, matching ``head :no_content``)
  * ``attribute_key`` is intentionally not updatable post-create
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.custom_attributes.models import CustomAttributeDefinition
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


async def _mint_headers(db_session, user) -> dict[str, str]:
    headers, new_tokens = create_new_auth_token(
        user_tokens=user.tokens, uid=user.uid
    )
    user.tokens = new_tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


@pytest.fixture
async def seeded(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@cad.example.com",
            account_name="CAD Inc",
            user_full_name="Admin Owner",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    admin_h = await _mint_headers(db_session, owner.user)
    return owner, admin_h


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------
async def test_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/custom_attribute_definitions")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
async def test_create_conversation_attribute(client, seeded):
    owner, admin_h = seeded
    # ``priority`` is a STANDARD_ATTRIBUTE for conversations — pick a
    # non-shadowing key like ``severity``.
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/custom_attribute_definitions",
        json={
            "custom_attribute_definition": {
                "attribute_display_name": "Severity",
                "attribute_display_type": "list",
                "attribute_key": "severity",
                "attribute_model": "conversation_attribute",
                "attribute_values": ["low", "medium", "high"],
            }
        },
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["attribute_display_name"] == "Severity"
    # Enum fields serialized as their string form.
    assert body["attribute_display_type"] == "list"
    assert body["attribute_model"] == "conversation_attribute"
    assert body["attribute_key"] == "severity"
    assert body["attribute_values"] == ["low", "medium", "high"]
    # Timestamps are ISO-8601 (not unix-int like Contact).
    assert "T" in body["created_at"]
    assert "T" in body["updated_at"]


async def test_create_rejects_reserved_contact_key(client, seeded):
    owner, admin_h = seeded
    # ``name`` shadows Contact#name → STANDARD_ATTRIBUTE_KEYS guard fires.
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/custom_attribute_definitions",
        json={
            "custom_attribute_definition": {
                "attribute_display_name": "Name",
                "attribute_display_type": "text",
                "attribute_key": "name",
                "attribute_model": "contact_attribute",
            }
        },
        headers=admin_h,
    )
    assert resp.status_code == 422
    assert "reserved" in resp.json()["message"].lower()


async def test_create_rejects_bad_key_format(client, seeded):
    owner, admin_h = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/custom_attribute_definitions",
        json={
            "custom_attribute_definition": {
                "attribute_display_name": "Bad",
                "attribute_display_type": "text",
                "attribute_key": "has spaces",
                "attribute_model": "contact_attribute",
            }
        },
        headers=admin_h,
    )
    assert resp.status_code == 422
    assert "alphanumeric" in resp.json()["message"].lower()


async def test_create_rejects_duplicate_key_per_model(client, seeded, db_session):
    owner, admin_h = seeded
    db_session.add(
        CustomAttributeDefinition(
            account_id=owner.account.id,
            attribute_display_name="Existing",
            attribute_key="plan",
            attribute_display_type=0,
            attribute_model=1,  # contact_attribute
        )
    )
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/custom_attribute_definitions",
        json={
            "custom_attribute_definition": {
                "attribute_display_name": "Duplicate",
                "attribute_display_type": "text",
                "attribute_key": "plan",
                "attribute_model": "contact_attribute",
            }
        },
        headers=admin_h,
    )
    assert resp.status_code == 422
    assert "already been taken" in resp.json()["message"].lower()


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------
async def test_index_filters_by_attribute_model(client, seeded, db_session):
    owner, admin_h = seeded
    db_session.add(
        CustomAttributeDefinition(
            account_id=owner.account.id,
            attribute_display_name="Plan",
            attribute_key="plan",
            attribute_display_type=0,
            attribute_model=1,  # contact
        )
    )
    db_session.add(
        CustomAttributeDefinition(
            account_id=owner.account.id,
            attribute_display_name="Priority",
            attribute_key="priority",
            attribute_display_type=6,
            attribute_model=0,  # conversation
        )
    )
    await db_session.flush()

    # No filter → both
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/custom_attribute_definitions",
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # Filter → one
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/custom_attribute_definitions"
        "?attribute_model=contact_attribute",
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["attribute_key"] == "plan"


# ---------------------------------------------------------------------------
# Show / update / destroy
# ---------------------------------------------------------------------------
async def test_show_update_destroy(client, seeded, db_session):
    owner, admin_h = seeded
    row = CustomAttributeDefinition(
        account_id=owner.account.id,
        attribute_display_name="Original",
        attribute_key="original_key",
        attribute_display_type=0,
        attribute_model=1,
    )
    db_session.add(row)
    await db_session.flush()

    # Show
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/custom_attribute_definitions/{row.id}",
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.json()["attribute_display_name"] == "Original"

    # Update: display name changes; attribute_key is ignored (not editable).
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/custom_attribute_definitions/{row.id}",
        json={
            "custom_attribute_definition": {
                "attribute_display_name": "Renamed",
                "attribute_key": "ignored_rename",
            }
        },
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["attribute_display_name"] == "Renamed"
    # attribute_key unchanged — the service intentionally skips the update.
    assert body["attribute_key"] == "original_key"

    # Destroy → 204 empty body
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/custom_attribute_definitions/{row.id}",
        headers=admin_h,
    )
    assert resp.status_code == 204
    assert resp.content == b""


async def test_show_not_found(client, seeded):
    owner, admin_h = seeded
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/custom_attribute_definitions/999999",
        headers=admin_h,
    )
    assert resp.status_code == 404
    assert resp.json() == {"error": "Resource could not be found"}
