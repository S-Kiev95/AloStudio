"""Integration tests for the Label CRUD surface.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/labels_controller.rb
  reference/chatwoot/app/policies/label_policy.rb
  reference/chatwoot/app/services/labels/update_service.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import Conversation
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
    update_labels,
)
from app.domains.inboxes.models import Inbox
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.labels.models import Label
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_AGENT,
    AccountUser,
)
from app.main import app

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
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


async def _seed_admin(db_session, suffix: str = ""):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@labels.example.com",
            account_name=f"Labels{suffix}",
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


async def _seed_agent(db_session, suffix: str = ""):
    """Account with a non-admin agent member — for index-vs-write
    auth tests."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"owner{suffix}@labels.example.com",
            account_name=f"Labels{suffix}",
            user_full_name=f"Owner{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agent{suffix}@labels.example.com",
            account_name=f"Other{suffix}",
            user_full_name=f"Agent{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner.account.id,
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
    return owner, agent, headers.as_response_headers()


# ---------------------------------------------------------------------------
# Auth + permissions
# ---------------------------------------------------------------------------
async def test_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/labels")
    assert resp.status_code == 401


async def test_index_works_for_agent(client, db_session):
    owner, agent, headers = await _seed_agent(db_session, suffix="-agix")
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/labels", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json() == {"payload": []}


async def test_create_blocked_for_agent(client, db_session):
    owner, agent, headers = await _seed_agent(db_session, suffix="-agcr")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/labels",
        json={"label": {"title": "blocked"}},
        headers=headers,
    )
    assert resp.status_code == 401
    assert resp.json() == {
        "error": "You are not authorized to do this action"
    }


# ---------------------------------------------------------------------------
# CRUD happy paths
# ---------------------------------------------------------------------------
async def test_create_returns_canonical_shape(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-cr")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/labels",
        json={"label": {"title": "Urgent", "description": "VIP"}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "urgent"  # downcased
    assert body["description"] == "VIP"
    assert body["color"] == "#1f93ff"  # default
    assert body["show_on_sidebar"] is None
    assert isinstance(body["id"], int)


async def test_create_rejects_duplicate_title(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-dup")
    base = {"label": {"title": "support"}}
    r1 = await client.post(
        f"/api/v1/accounts/{owner.account.id}/labels",
        json=base,
        headers=headers,
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"/api/v1/accounts/{owner.account.id}/labels",
        json=base,
        headers=headers,
    )
    assert r2.status_code == 422
    assert "taken" in r2.json()["message"].lower()


async def test_create_rejects_invalid_chars(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-inv")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/labels",
        json={"label": {"title": "has spaces!"}},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "invalid" in resp.json()["message"].lower()


async def test_create_rejects_blank_title(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-bl")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/labels",
        json={"label": {"title": "   "}},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "blank" in resp.json()["message"].lower()


async def test_index_orders_by_title(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-ord")
    for t in ["zeta", "alpha", "mike"]:
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/labels",
            json={"label": {"title": t}},
            headers=headers,
        )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/labels", headers=headers
    )
    titles = [row["title"] for row in resp.json()["payload"]]
    assert titles == ["alpha", "mike", "zeta"]


async def test_show_404_for_unknown_id(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-404")
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/labels/9999", headers=headers
    )
    assert resp.status_code == 404


async def test_update_changes_fields(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-up")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/labels",
        json={"label": {"title": "billing"}},
        headers=headers,
    )
    lid = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/labels/{lid}",
        json={"label": {"description": "money stuff", "color": "#ff00ff"}},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] == "money stuff"
    assert body["color"] == "#ff00ff"
    assert body["title"] == "billing"  # unchanged


async def test_destroy_returns_200_empty_body(client, db_session):
    """Rails: ``head :ok`` — HTTP 200 with empty body, NOT 204."""
    owner, headers = await _seed_admin(db_session, suffix="-del")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/labels",
        json={"label": {"title": "trash"}},
        headers=headers,
    )
    lid = create.json()["id"]
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/labels/{lid}", headers=headers
    )
    assert resp.status_code == 200
    # Idempotent re-delete is 404 (gone).
    again = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/labels/{lid}", headers=headers
    )
    assert again.status_code == 404


# ---------------------------------------------------------------------------
# Rename cascade — the headline 6.1 feature
# ---------------------------------------------------------------------------
async def _seed_conversation_with_label(
    db_session, owner, label_title: str
) -> Conversation:
    """Helper: create an inbox + conversation + tag with one label."""
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API",
            channel_type="api",
            channel_params={"webhook_url": "https://x.example.com"},
        ),
    ).perform()
    assert isinstance(result.inbox, Inbox)
    contact = Contact(account_id=owner.account.id, name="X")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=result.inbox,
        source_id="lab-cascade",
    ).perform()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    await update_labels(
        db_session, conversation=conv, titles=[label_title]
    )
    return conv


async def test_rename_walks_cached_label_list(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-rn")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/labels",
        json={"label": {"title": "vip"}},
        headers=headers,
    )
    lid = create.json()["id"]
    conv = await _seed_conversation_with_label(db_session, owner, "vip")
    assert conv.cached_label_list == "vip"

    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/labels/{lid}",
        json={"label": {"title": "premium"}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "premium"

    # The conversation's denormalised CSV picks up the new title even
    # though ConversationLabel is keyed on label_id.
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    assert fresh.cached_label_list == "premium"


async def test_destroy_strips_label_from_cached_list(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-rds")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/labels",
        json={"label": {"title": "discard"}},
        headers=headers,
    )
    lid = create.json()["id"]
    conv = await _seed_conversation_with_label(db_session, owner, "discard")

    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/labels/{lid}", headers=headers
    )
    assert resp.status_code == 200

    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    assert fresh.cached_label_list is None
    # The Label row itself is gone too (CASCADE drops the join row).
    remaining = list(
        (
            await db_session.exec(
                select(Label).where(Label.account_id == owner.account.id)
            )
        ).all()
    )
    assert remaining == []


async def test_rename_idempotent_when_title_unchanged(client, db_session):
    """Patching with the same title shouldn't trigger the cascade or
    raise the unique-index 422."""
    owner, headers = await _seed_admin(db_session, suffix="-noop")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/labels",
        json={"label": {"title": "stable"}},
        headers=headers,
    )
    lid = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/labels/{lid}",
        json={"label": {"title": "stable", "color": "#abcdef"}},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "stable"
    assert resp.json()["color"] == "#abcdef"
