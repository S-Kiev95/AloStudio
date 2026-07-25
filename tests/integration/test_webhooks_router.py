"""Integration tests for Webhook CRUD + delivery listener.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/webhooks_controller.rb
  reference/chatwoot/app/listeners/webhook_listener.rb
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
    toggle_status,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.domains.webhooks.models import Webhook
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


async def _seed_admin(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@whk.example.com",
            account_name=f"WHK{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _seed_agent_member(db_session, owner_account, suffix: str):
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agent{suffix}@whk.example.com",
            account_name=f"Other{suffix}",
            user_full_name=f"Agent{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner_account.id,
            user_id=agent.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    await db_session.flush()
    headers, new_tokens = create_new_auth_token(
        user_tokens=agent.user.tokens, uid=agent.user.uid
    )
    agent.user.tokens = new_tokens
    db_session.add(agent.user)
    await db_session.flush()
    return agent, headers.as_response_headers()


async def _seed_conversation(db_session, owner):
    inbox = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API",
            channel_type="api",
            channel_params={"webhook_url": "https://x.example.com"},
        ),
    ).perform()
    contact = Contact(account_id=owner.account.id, name="X")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox.inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    return await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
async def test_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/webhooks")
    assert resp.status_code == 401


async def test_index_blocked_for_agent(client, db_session):
    owner, _ = await _seed_admin(db_session, "-ag")
    _agent, agent_headers = await _seed_agent_member(
        db_session, owner.account, "-ag"
    )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/webhooks",
        headers=agent_headers,
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
async def test_create_webhook_happy_path(client, db_session):
    owner, headers = await _seed_admin(db_session, "-cr")
    body = {
        "webhook": {
            "url": "https://hooks.example.com/in",
            "name": "Slack relay",
            "subscriptions": ["message_created", "conversation_created"],
        }
    }
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/webhooks",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()["payload"]["webhook"]
    assert payload["url"] == "https://hooks.example.com/in"
    assert set(payload["subscriptions"]) == {
        "message_created",
        "conversation_created",
    }
    assert isinstance(payload["secret"], str)
    assert len(payload["secret"]) == 24
    assert payload["account_id"] == owner.account.id


async def test_create_rejects_invalid_url(client, db_session):
    owner, headers = await _seed_admin(db_session, "-iu")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/webhooks",
        json={
            "webhook": {
                "url": "not-a-url",
                "subscriptions": ["message_created"],
            }
        },
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_rejects_invalid_subscription(client, db_session):
    owner, headers = await _seed_admin(db_session, "-is")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/webhooks",
        json={
            "webhook": {
                "url": "https://h.example.com",
                "subscriptions": ["frobnicate"],
            }
        },
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_rejects_empty_subscriptions(client, db_session):
    owner, headers = await _seed_admin(db_session, "-es")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/webhooks",
        json={
            "webhook": {
                "url": "https://h.example.com",
                "subscriptions": [],
            }
        },
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_rejects_duplicate_url(client, db_session):
    owner, headers = await _seed_admin(db_session, "-du")
    base = {
        "webhook": {
            "url": "https://dup.example.com",
            "subscriptions": ["message_created"],
        }
    }
    r1 = await client.post(
        f"/api/v1/accounts/{owner.account.id}/webhooks",
        json=base,
        headers=headers,
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"/api/v1/accounts/{owner.account.id}/webhooks",
        json=base,
        headers=headers,
    )
    assert r2.status_code == 422


async def test_update_changes_subscriptions(client, db_session):
    owner, headers = await _seed_admin(db_session, "-up")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/webhooks",
        json={
            "webhook": {
                "url": "https://up.example.com",
                "subscriptions": ["message_created"],
            }
        },
        headers=headers,
    )
    wid = create.json()["payload"]["webhook"]["id"]
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/webhooks/{wid}",
        json={
            "webhook": {
                "subscriptions": [
                    "conversation_created",
                    "conversation_updated",
                ]
            }
        },
        headers=headers,
    )
    assert resp.status_code == 200
    subs = resp.json()["payload"]["webhook"]["subscriptions"]
    assert set(subs) == {"conversation_created", "conversation_updated"}


async def test_destroy_returns_200(client, db_session):
    owner, headers = await _seed_admin(db_session, "-dl")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/webhooks",
        json={
            "webhook": {
                "url": "https://del.example.com",
                "subscriptions": ["message_created"],
            }
        },
        headers=headers,
    )
    wid = create.json()["payload"]["webhook"]["id"]
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/webhooks/{wid}",
        headers=headers,
    )
    assert resp.status_code == 200


async def test_index_returns_account_webhooks(client, db_session):
    owner, headers = await _seed_admin(db_session, "-ix")
    for url in ["https://a.example.com", "https://b.example.com"]:
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/webhooks",
            json={
                "webhook": {
                    "url": url,
                    "subscriptions": ["message_created"],
                }
            },
            headers=headers,
        )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/webhooks",
        headers=headers,
    )
    body = resp.json()["payload"]["webhooks"]
    urls = {row["url"] for row in body}
    assert urls == {"https://a.example.com", "https://b.example.com"}


# ---------------------------------------------------------------------------
# Delivery (listener)
# ---------------------------------------------------------------------------
@respx.mock
async def test_message_created_event_delivers_to_subscribed_webhook(
    db_session,
):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="del-admin@whk.example.com",
            account_name="WHK-del",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    conv = await _seed_conversation(db_session, owner)
    hook = Webhook(
        account_id=owner.account.id,
        url="https://hooks.example.com/m",
        subscriptions=["message_created"],
        webhook_type=0,
        secret="hooksecret",
    )
    db_session.add(hook)
    await db_session.flush()
    route = respx.post("https://hooks.example.com/m").mock(
        return_value=httpx.Response(200)
    )
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="hi", message_type="incoming"),
        user_id=None,
    )
    assert route.called
    req = route.calls.last.request
    body = json.loads(req.content)
    assert body["event"] == "message_created"
    assert body["content"] == "hi"
    # v2.7: event_id appears in body + mirrors the delivery header.
    assert len(body["event_id"]) == 36
    assert req.headers["X-Chatwoot-Delivery"] == body["event_id"]
    # v2.7: dual signature header. Legacy + GitHub-style ``sha256=<hex>``.
    import hashlib
    import hmac

    expected = hmac.new(
        b"hooksecret", req.content, hashlib.sha256
    ).hexdigest()
    assert req.headers["X-Chatwoot-Signature"] == expected
    assert req.headers["X-AloStudio-Signature"] == f"sha256={expected}"
    # v2.7: sender_type on message webhooks.
    assert "sender_type" in body


@respx.mock
async def test_webhook_skipped_for_unsubscribed_event(db_session):
    """A webhook only subscribed to ``conversation_created`` must not
    fire on ``message_created``."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="us-admin@whk.example.com",
            account_name="WHK-us",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    conv = await _seed_conversation(db_session, owner)
    hook = Webhook(
        account_id=owner.account.id,
        url="https://hooks.example.com/c",
        subscriptions=["conversation_created"],
        webhook_type=0,
        secret="x",
    )
    db_session.add(hook)
    await db_session.flush()
    route = respx.post("https://hooks.example.com/c").mock(
        return_value=httpx.Response(200)
    )
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="x", message_type="incoming"),
        user_id=None,
    )
    # Only conversation_created (fired by _seed_conversation) lands; the
    # message_created event must NOT trigger.
    sent_events = [
        json.loads(c.request.content)["event"] for c in route.calls
    ]
    assert "message_created" not in sent_events


@respx.mock
async def test_conversation_status_changed_event_delivers(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="sc-admin@whk.example.com",
            account_name="WHK-sc",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    conv = await _seed_conversation(db_session, owner)
    hook = Webhook(
        account_id=owner.account.id,
        url="https://hooks.example.com/sc",
        subscriptions=["conversation_status_changed"],
        webhook_type=0,
        secret="x",
    )
    db_session.add(hook)
    await db_session.flush()
    route = respx.post("https://hooks.example.com/sc").mock(
        return_value=httpx.Response(200)
    )
    await toggle_status(db_session, conversation=conv, status="resolved")
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body["event"] == "conversation_status_changed"
    assert body["status"] == "resolved"


@respx.mock
async def test_webhook_per_account_isolation(db_session):
    """A webhook on account A must NOT receive events from account B."""
    owner_a = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="a-admin@whk.example.com",
            account_name="WHK-A",
            user_full_name="A",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    owner_b = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="b-admin@whk.example.com",
            account_name="WHK-B",
            user_full_name="B",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    hook_a = Webhook(
        account_id=owner_a.account.id,
        url="https://hooks.example.com/a-only",
        subscriptions=["message_created"],
        webhook_type=0,
        secret="x",
    )
    db_session.add(hook_a)
    await db_session.flush()
    route_a = respx.post("https://hooks.example.com/a-only").mock(
        return_value=httpx.Response(200)
    )
    conv_b = await _seed_conversation(db_session, owner_b)
    await create_message(
        db_session,
        conversation=conv_b,
        params=MessageBuilderParams(content="iso", message_type="incoming"),
        user_id=None,
    )
    assert not route_a.called
