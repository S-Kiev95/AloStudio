"""Integration tests for the V2 summary + conversations endpoints.

Anchors:
  reference/chatwoot/app/controllers/api/v2/accounts/reports_controller.rb
  reference/chatwoot/app/helpers/report_helper.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import Conversation
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
    toggle_status,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
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


async def _seed_admin(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@reps.example.com",
            account_name=f"Reps{suffix}",
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


async def _seed_conversation(db_session, owner) -> Conversation:
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
# Auth gates
# ---------------------------------------------------------------------------
async def test_summary_requires_auth(client):
    resp = await client.get("/api/v2/accounts/1/reports/summary")
    assert resp.status_code == 401


async def test_conversations_requires_auth(client):
    resp = await client.get(
        "/api/v2/accounts/1/reports/conversations?type=conversation"
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Summary — shape + previous block
# ---------------------------------------------------------------------------
async def test_summary_empty_account_returns_zeros(client, db_session):
    owner, headers = await _seed_admin(db_session, "-zr")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports/summary",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # All metric keys present, zero across the board.
    for key in (
        "conversations_count",
        "incoming_messages_count",
        "outgoing_messages_count",
        "resolutions_count",
    ):
        assert body[key] == 0
    for key in (
        "avg_first_response_time",
        "avg_resolution_time",
        "reply_time",
    ):
        assert body[key] == 0
    assert "previous" in body
    assert isinstance(body["previous"], dict)
    assert body["previous"]["conversations_count"] == 0


async def test_summary_counts_conversations_and_messages(client, db_session):
    owner, headers = await _seed_admin(db_session, "-cnt")
    conv = await _seed_conversation(db_session, owner)
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="hi", message_type="incoming"),
        user_id=None,
    )
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="hi back", message_type="outgoing"),
        user_id=owner.user.id,
    )
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports/summary",
        headers=headers,
    )
    body = resp.json()
    assert body["conversations_count"] == 1
    assert body["incoming_messages_count"] == 1
    assert body["outgoing_messages_count"] == 1


async def test_summary_includes_resolution_and_reply_metrics(client, db_session):
    """A resolved conversation contributes to resolutions_count + the
    avg_resolution_time / avg_first_response_time averages."""
    owner, headers = await _seed_admin(db_session, "-rt")
    conv = await _seed_conversation(db_session, owner)
    conv.created_at = datetime.now(UTC) - timedelta(seconds=60)
    conv.waiting_since = conv.created_at
    db_session.add(conv)
    await db_session.flush()
    # First agent reply emits first_response.
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content="hello", message_type="outgoing"),
        user_id=owner.user.id,
    )
    await toggle_status(db_session, conversation=conv, status="resolved")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports/summary",
        headers=headers,
    )
    body = resp.json()
    assert body["resolutions_count"] == 1
    assert body["avg_resolution_time"] >= 60.0
    assert body["avg_first_response_time"] >= 60.0


# ---------------------------------------------------------------------------
# Conversations metrics (current state)
# ---------------------------------------------------------------------------
async def test_conversations_endpoint_requires_type_param(client, db_session):
    """Rails returns 422 when ``params[:type]`` is missing."""
    owner, headers = await _seed_admin(db_session, "-noty")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports/conversations",
        headers=headers,
    )
    assert resp.status_code == 422


async def test_conversations_endpoint_returns_live_counters(client, db_session):
    owner, headers = await _seed_admin(db_session, "-live")
    # 2 open + 1 resolved.
    c1 = await _seed_conversation(db_session, owner)
    c2 = await _seed_conversation(db_session, owner)
    c3 = await _seed_conversation(db_session, owner)
    await toggle_status(db_session, conversation=c3, status="resolved")
    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports/conversations?type=conversation",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["open"] == 2
    # Neither conv has first_reply yet → both unattended.
    assert body["unattended"] == 2
    # Both unassigned (no assignee_id set).
    assert body["unassigned"] == 2
    assert "pending" in body


# ---------------------------------------------------------------------------
# Scope filter (inbox)
# ---------------------------------------------------------------------------
async def test_summary_scopes_to_inbox(client, db_session):
    """``type=inbox&id=<inbox_id>`` returns only metrics for that inbox."""
    owner, headers = await _seed_admin(db_session, "-sc")
    conv_a = await _seed_conversation(db_session, owner)
    conv_b = await _seed_conversation(db_session, owner)
    # conv_a + conv_b live in DIFFERENT inboxes because the seed
    # creates a new inbox per call. We re-fetch their inbox_ids.
    await create_message(
        db_session,
        conversation=conv_a,
        params=MessageBuilderParams(content="a", message_type="incoming"),
        user_id=None,
    )
    await create_message(
        db_session,
        conversation=conv_b,
        params=MessageBuilderParams(content="b", message_type="incoming"),
        user_id=None,
    )

    resp = await client.get(
        f"/api/v2/accounts/{owner.account.id}/reports/summary"
        f"?type=inbox&id={conv_a.inbox_id}",
        headers=headers,
    )
    body = resp.json()
    assert body["conversations_count"] == 1
    assert body["incoming_messages_count"] == 1


async def test_summary_per_account_isolated(client, db_session):
    """Conversations on another account are excluded from the totals."""
    owner_a, headers_a = await _seed_admin(db_session, "-ax")
    owner_b, _ = await _seed_admin(db_session, "-bx")
    await _seed_conversation(db_session, owner_a)
    await _seed_conversation(db_session, owner_b)
    await _seed_conversation(db_session, owner_b)
    resp = await client.get(
        f"/api/v2/accounts/{owner_a.account.id}/reports/summary",
        headers=headers_a,
    )
    body = resp.json()
    assert body["conversations_count"] == 1
