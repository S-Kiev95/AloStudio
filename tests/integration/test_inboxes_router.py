"""HTTP-level tests for ``/api/v1/accounts/:id/inboxes`` + nested
``inbox_members``.

Parity anchors:
  * ``Api::V1::Accounts::InboxesController`` + ``InboxPolicy``
  * ``Api::V1::Accounts::InboxMembersController``
  * ``_inbox.json.jbuilder`` + ``_agent.json.jbuilder`` partials

Coverage:
  * admin happy paths: create / show / index / update / destroy / reset_secret
  * agent read-only (show + index allowed only for assigned inboxes)
  * wire-shape parity on the Channel::Api subset (hmac_token/secret gated
    by admin, always-emitted union keys)
  * inbox_members list / add / replace (PATCH) / remove
  * reset_secret rotates the ``secret`` column in place
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
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
            email="admin@inboxes.example.com",
            account_name="Inboxes Inc",
            user_full_name="Admin Owner",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    side = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent@inboxes.example.com",
            account_name="Agent Side Account",
            user_full_name="Agent Beta",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner.account.id,
            user_id=side.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    await db_session.flush()
    admin_h = await _mint_headers(db_session, owner.user)
    agent_h = await _mint_headers(db_session, side.user)
    return owner, side, admin_h, agent_h


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------
async def test_inboxes_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/inboxes")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Create + wire shape
# ---------------------------------------------------------------------------
async def test_admin_creates_api_inbox(client, seeded):
    owner, _, admin_h, _ = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/inboxes",
        json={
            "name": "API Inbox",
            "channel": {"type": "api", "webhook_url": "https://example.com/hook"},
        },
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "API Inbox"
    assert body["channel_type"] == "Channel::Api"
    assert body["webhook_url"] == "https://example.com/hook"
    # Admin view carries hmac_token + secret.
    assert isinstance(body["hmac_token"], str) and len(body["hmac_token"]) > 0
    assert isinstance(body["secret"], str) and len(body["secret"]) > 0
    # Always-emitted union keys present with null for non-API channels.
    for k in (
        "tweets_enabled",
        "allowed_domains",
        "widget_color",
        "website_url",
        "welcome_title",
        "website_token",
    ):
        assert k in body


async def test_agent_cannot_create_inbox(client, seeded):
    owner, _, _, agent_h = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/inboxes",
        json={"name": "nope", "channel": {"type": "api"}},
        headers=agent_h,
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Index — admin sees all, agent sees assigned only
# ---------------------------------------------------------------------------
async def test_agent_sees_only_assigned_inboxes(client, seeded):
    owner, side, admin_h, agent_h = seeded

    # Two inboxes; only one has the agent as a member.
    ix_open = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/inboxes",
            json={"name": "Open Shop", "channel": {"type": "api"}},
            headers=admin_h,
        )
    ).json()
    _ix_closed = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/inboxes",
            json={"name": "Closed Shop", "channel": {"type": "api"}},
            headers=admin_h,
        )
    ).json()

    # Admin wires the agent into Open Shop only.
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/inbox_members",
        json={"inbox_id": ix_open["id"], "user_ids": [side.user.id]},
        headers=admin_h,
    )

    # Admin: both inboxes.
    admin_list = await client.get(
        f"/api/v1/accounts/{owner.account.id}/inboxes", headers=admin_h
    )
    assert {ix["name"] for ix in admin_list.json()["payload"]} == {
        "Open Shop",
        "Closed Shop",
    }

    # Agent: only Open Shop, and without hmac_token/secret.
    agent_list = await client.get(
        f"/api/v1/accounts/{owner.account.id}/inboxes", headers=agent_h
    )
    agent_rows = agent_list.json()["payload"]
    assert [ix["name"] for ix in agent_rows] == ["Open Shop"]
    assert "hmac_token" not in agent_rows[0]
    assert "secret" not in agent_rows[0]


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
async def test_admin_patches_inbox_and_channel(client, seeded):
    owner, _, admin_h, _ = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/inboxes",
            json={"name": "Before", "channel": {"type": "api"}},
            headers=admin_h,
        )
    ).json()

    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/inboxes/{created['id']}",
        json={
            "name": "After",
            "greeting_enabled": True,
            "greeting_message": "Hello!",
            "channel": {"webhook_url": "https://new.example.com/hook"},
        },
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "After"
    assert body["greeting_enabled"] is True
    assert body["greeting_message"] == "Hello!"
    assert body["webhook_url"] == "https://new.example.com/hook"


# ---------------------------------------------------------------------------
# Destroy
# ---------------------------------------------------------------------------
async def test_admin_destroys_inbox(client, seeded):
    owner, _, admin_h, _ = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/inboxes",
            json={"name": "Ephemeral", "channel": {"type": "api"}},
            headers=admin_h,
        )
    ).json()
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/inboxes/{created['id']}",
        headers=admin_h,
    )
    assert resp.status_code == 200
    # Chatwoot's async-delete message carries through.
    assert resp.json() == {"message": "The inbox is scheduled for deletion"}


# ---------------------------------------------------------------------------
# reset_secret
# ---------------------------------------------------------------------------
async def test_reset_secret_rotates_value(client, seeded):
    owner, _, admin_h, _ = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/inboxes",
            json={"name": "Secrets", "channel": {"type": "api"}},
            headers=admin_h,
        )
    ).json()
    original_secret = created["secret"]
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/inboxes/{created['id']}/reset_secret",
        headers=admin_h,
    )
    assert resp.status_code == 200
    new_secret = resp.json()["secret"]
    assert isinstance(new_secret, str) and new_secret
    assert new_secret != original_secret


# ---------------------------------------------------------------------------
# inbox_members
# ---------------------------------------------------------------------------
async def test_inbox_members_add_and_list(client, seeded):
    owner, side, admin_h, _ = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/inboxes",
            json={"name": "Shared Inbox", "channel": {"type": "api"}},
            headers=admin_h,
        )
    ).json()
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/inbox_members",
        json={"inbox_id": created["id"], "user_ids": [owner.user.id, side.user.id]},
        headers=admin_h,
    )
    assert resp.status_code == 200
    payload = resp.json()["payload"]
    assert {a["id"] for a in payload} == {owner.user.id, side.user.id}

    listing = await client.get(
        f"/api/v1/accounts/{owner.account.id}/inbox_members/{created['id']}",
        headers=admin_h,
    )
    assert {a["id"] for a in listing.json()["payload"]} == {
        owner.user.id,
        side.user.id,
    }


async def test_inbox_members_patch_replaces_set(client, seeded):
    owner, side, admin_h, _ = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/inboxes",
            json={"name": "Rotating", "channel": {"type": "api"}},
            headers=admin_h,
        )
    ).json()
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/inbox_members",
        json={"inbox_id": created["id"], "user_ids": [owner.user.id]},
        headers=admin_h,
    )
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/inbox_members",
        json={"inbox_id": created["id"], "user_ids": [side.user.id]},
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert [a["id"] for a in resp.json()["payload"]] == [side.user.id]
