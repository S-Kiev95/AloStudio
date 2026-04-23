"""HTTP-level tests for Phase 4a ``/api/v1/accounts/:id/conversations``.

Parity anchors:
  * ``Api::V1::Accounts::ConversationsController`` (the 4a subset listed in
    ``app/domains/conversations/router.py``).
  * ``_conversation.json.jbuilder`` / ``meta.json.jbuilder`` /
    ``toggle_status.json.jbuilder`` / ``index.json.jbuilder``.

Coverage:
  * Auth gates (401 unauthenticated, 404 non-member account).
  * ``POST   /conversations``                — with/without inline message.
  * ``GET    /conversations``                — filter by status/assignee_type.
  * ``GET    /conversations/meta``           — counts envelope.
  * ``GET    /conversations/:id``            — show wire shape.
  * ``PATCH  /conversations/:id``            — priority-only permitted_params.
  * ``POST   /conversations/:id/toggle_status``
  * ``POST   /conversations/:id/toggle_priority`` (head :ok).
  * ``POST   /conversations/:id/mute`` / ``/unmute`` (head :ok).
  * ``POST   /conversations/:id/custom_attributes``.
  * ``POST   /conversations/:id/update_last_seen``.
  * ``POST   /conversations/:id/unread``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    CONVERSATION_PRIORITY_HIGH,
    CONVERSATION_STATUS_OPEN,
    CONVERSATION_STATUS_RESOLVED,
    MESSAGE_TYPE_INCOMING,
    Conversation,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
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
    """Account + admin + agent + one API inbox + one contact + ContactInbox."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@conv.example.com",
            account_name="Conv Inc",
            user_full_name="Admin Owner",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    agent_side = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent@conv.example.com",
            account_name="Agent Side Account",
            user_full_name="Agent Beta",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner.account.id,
            user_id=agent_side.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    await db_session.flush()

    inbox_result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API Inbox",
            channel_type="api",
            channel_params={"webhook_url": "https://example.com/hook"},
        ),
    ).perform()

    contact = Contact(
        account_id=owner.account.id,
        email="c1@example.com",
        name="Seed Contact",
    )
    db_session.add(contact)
    await db_session.flush()

    contact_inbox = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox_result.inbox,
    ).perform()

    admin_h = await _mint_headers(db_session, owner.user)
    agent_h = await _mint_headers(db_session, agent_side.user)
    return owner, agent_side, inbox_result.inbox, contact, contact_inbox, admin_h, agent_h


async def _make_conversation(
    db_session, *, contact_inbox: ContactInbox, status: str | None = None
) -> Conversation:
    """Seed a conversation through the real builder so display_id + uuid
    + last_activity_at get their trigger-assigned / server-side defaults.
    """
    return await create_conversation(
        db_session,
        contact_inbox=contact_inbox,
        params=ConversationBuilderParams(status=status),
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
async def test_conversations_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/conversations")
    assert resp.status_code == 401


async def test_non_member_account_returns_404(client, seeded):
    _, _, _, _, _, admin_h, _ = seeded
    resp = await client.get("/api/v1/accounts/999999/conversations", headers=admin_h)
    assert resp.status_code == 404
    assert resp.json() == {"error": "Resource could not be found"}


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
async def test_create_conversation_minimal(client, seeded):
    owner, _, inbox, contact, _, admin_h, _ = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations",
        json={"inbox_id": inbox.id, "contact_id": contact.id},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # ``id`` is display_id (per-account sequence).
    assert body["id"] == 1
    assert body["account_id"] == owner.account.id
    assert body["inbox_id"] == inbox.id
    assert body["status"] == "open"
    # No inline message → messages array is empty.
    assert body["messages"] == []
    # meta nests sender + channel + hmac_verified.
    assert body["meta"]["channel"] == "Channel::Api"
    assert body["meta"]["sender"]["id"] == contact.id
    assert body["meta"]["hmac_verified"] is False
    # unread_count starts at 0 with no incoming messages.
    assert body["unread_count"] == 0


async def test_create_conversation_with_inline_message(client, seeded):
    owner, _, inbox, contact, _, admin_h, _ = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations",
        json={
            "inbox_id": inbox.id,
            "contact_id": contact.id,
            "message": {
                "content": "Hello world",
                "message_type": "outgoing",
            },
        },
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # With one message, the ``messages[]`` array emits the push-event shape
    # of the last message (single-element list).
    assert len(body["messages"]) == 1
    last_msg = body["messages"][0]
    assert last_msg["content"] == "Hello world"
    # Wire ``message_type`` is the INTEGER (outgoing == 1).
    assert last_msg["message_type"] == 1


async def test_create_conversation_rejects_missing_contact_inbox(client, seeded):
    owner, _, _, _, _, admin_h, _ = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations",
        json={},  # no inbox_id, no contact_id, no source_id
        headers=admin_h,
    )
    assert resp.status_code == 422
    assert resp.json() == {"message": "Contact inbox could not be resolved"}


async def test_create_conversation_rejects_bad_snoozed_until(client, seeded):
    owner, _, inbox, contact, _, admin_h, _ = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations",
        json={
            "inbox_id": inbox.id,
            "contact_id": contact.id,
            "snoozed_until": "not-a-datetime",
        },
        headers=admin_h,
    )
    assert resp.status_code == 422
    assert "snoozed_until" in resp.json()["message"]


# ---------------------------------------------------------------------------
# Index + meta
# ---------------------------------------------------------------------------
async def test_index_conversations_envelope(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h, _ = seeded
    await _make_conversation(db_session, contact_inbox=contact_inbox)
    await _make_conversation(db_session, contact_inbox=contact_inbox)

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations", headers=admin_h
    )
    assert resp.status_code == 200
    body = resp.json()
    # Rails wraps the index in ``{"data": {"meta": {...}, "payload": [...]}}``.
    assert set(body["data"]) == {"meta", "payload"}
    assert set(body["data"]["meta"]) == {
        "mine_count",
        "assigned_count",
        "unassigned_count",
        "all_count",
    }
    assert body["data"]["meta"]["all_count"] == 2
    assert body["data"]["meta"]["unassigned_count"] == 2
    assert body["data"]["meta"]["assigned_count"] == 0
    assert body["data"]["meta"]["mine_count"] == 0
    assert len(body["data"]["payload"]) == 2


async def test_index_filters_by_status(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h, _ = seeded
    # One open, one resolved.
    await _make_conversation(db_session, contact_inbox=contact_inbox)
    resolved = await _make_conversation(db_session, contact_inbox=contact_inbox)
    resolved.status = CONVERSATION_STATUS_RESOLVED
    db_session.add(resolved)
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations?status=resolved",
        headers=admin_h,
    )
    assert resp.status_code == 200
    payload = resp.json()["data"]["payload"]
    assert len(payload) == 1
    assert payload[0]["status"] == "resolved"


async def test_meta_counts_envelope(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h, _ = seeded
    await _make_conversation(db_session, contact_inbox=contact_inbox)

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/meta",
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "meta": {
            "mine_count": 0,
            "assigned_count": 0,
            "unassigned_count": 1,
            "all_count": 1,
        }
    }


# ---------------------------------------------------------------------------
# Show / update
# ---------------------------------------------------------------------------
async def test_show_conversation(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h, _ = seeded
    conv = await _make_conversation(db_session, contact_inbox=contact_inbox)

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}",
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == conv.display_id
    assert body["status"] == "open"


async def test_show_unknown_display_id_404(client, seeded):
    owner, _, _, _, _, admin_h, _ = seeded
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/9999",
        headers=admin_h,
    )
    assert resp.status_code == 404
    assert resp.json() == {"error": "Resource could not be found"}


async def test_update_priority_only(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h, _ = seeded
    conv = await _make_conversation(db_session, contact_inbox=contact_inbox)

    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}",
        json={"priority": "high", "status": "resolved"},  # status silently dropped
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["priority"] == "high"
    # ``status`` must be silently ignored (permit-drops-unknown semantics).
    assert body["status"] == "open"

    await db_session.refresh(conv)
    assert conv.priority == CONVERSATION_PRIORITY_HIGH
    assert conv.status == CONVERSATION_STATUS_OPEN


# ---------------------------------------------------------------------------
# Toggle status / priority
# ---------------------------------------------------------------------------
async def test_toggle_status_flip_open_to_resolved(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h, _ = seeded
    conv = await _make_conversation(db_session, contact_inbox=contact_inbox)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/toggle_status",
        json={},  # missing status → flip
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["payload"]["success"] is True
    assert body["payload"]["conversation_id"] == conv.display_id
    assert body["payload"]["current_status"] == "resolved"


async def test_toggle_status_explicit_snoozed(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h, _ = seeded
    conv = await _make_conversation(db_session, contact_inbox=contact_inbox)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/toggle_status",
        json={"status": "snoozed", "snoozed_until": "2099-01-01T00:00:00Z"},
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["payload"]["current_status"] == "snoozed"
    assert body["payload"]["snoozed_until"] is not None


async def test_toggle_priority_head_ok(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h, _ = seeded
    conv = await _make_conversation(db_session, contact_inbox=contact_inbox)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/toggle_priority",
        json={"priority": "urgent"},
        headers=admin_h,
    )
    # Rails ``head :ok`` → 200 with empty body.
    assert resp.status_code == 200
    assert resp.content == b""

    await db_session.refresh(conv)
    assert conv.priority is not None  # set to CONVERSATION_PRIORITY_URGENT internally.


async def test_toggle_priority_clear(client, seeded, db_session):
    """Rails ``.presence`` — empty/null clears the field."""
    owner, _, _, _, contact_inbox, admin_h, _ = seeded
    conv = await _make_conversation(db_session, contact_inbox=contact_inbox)
    conv.priority = CONVERSATION_PRIORITY_HIGH
    db_session.add(conv)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/toggle_priority",
        json={"priority": None},
        headers=admin_h,
    )
    assert resp.status_code == 200
    await db_session.refresh(conv)
    assert conv.priority is None


# ---------------------------------------------------------------------------
# Mute / unmute
# ---------------------------------------------------------------------------
async def test_mute_blocks_contact_and_resolves(client, seeded, db_session):
    owner, _, _, contact, contact_inbox, admin_h, _ = seeded
    conv = await _make_conversation(db_session, contact_inbox=contact_inbox)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/mute",
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.content == b""

    await db_session.refresh(conv)
    await db_session.refresh(contact)
    assert contact.blocked is True
    assert conv.status == CONVERSATION_STATUS_RESOLVED


async def test_unmute_unblocks_contact(client, seeded, db_session):
    owner, _, _, contact, contact_inbox, admin_h, _ = seeded
    conv = await _make_conversation(db_session, contact_inbox=contact_inbox)
    contact.blocked = True
    db_session.add(contact)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/unmute",
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.content == b""

    await db_session.refresh(contact)
    assert contact.blocked is False


# ---------------------------------------------------------------------------
# Custom attributes
# ---------------------------------------------------------------------------
async def test_set_custom_attributes(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h, _ = seeded
    conv = await _make_conversation(db_session, contact_inbox=contact_inbox)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/custom_attributes",
        json={"custom_attributes": {"plan": "gold", "region": "eu"}},
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["custom_attributes"] == {"plan": "gold", "region": "eu"}


async def test_set_custom_attributes_missing_key_coerces_to_empty(
    client, seeded, db_session
):
    owner, _, _, _, contact_inbox, admin_h, _ = seeded
    conv = await _make_conversation(db_session, contact_inbox=contact_inbox)
    conv.custom_attributes = {"pre": "existing"}
    db_session.add(conv)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/custom_attributes",
        json={},  # missing key → Rails coerces to {}
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["custom_attributes"] == {}


# ---------------------------------------------------------------------------
# update_last_seen
# ---------------------------------------------------------------------------
async def test_update_last_seen(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h, _ = seeded
    conv = await _make_conversation(db_session, contact_inbox=contact_inbox)
    assert conv.agent_last_seen_at is None

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/update_last_seen",
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.content == b""

    await db_session.refresh(conv)
    assert conv.agent_last_seen_at is not None


async def test_update_last_seen_also_bumps_assignee_when_assigned(
    client, seeded, db_session
):
    owner, _, _, _, contact_inbox, admin_h, _ = seeded
    conv = await _make_conversation(db_session, contact_inbox=contact_inbox)
    conv.assignee_id = owner.user.id
    db_session.add(conv)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/update_last_seen",
        headers=admin_h,
    )
    assert resp.status_code == 200
    await db_session.refresh(conv)
    assert conv.agent_last_seen_at is not None
    assert conv.assignee_last_seen_at is not None


# ---------------------------------------------------------------------------
# unread
# ---------------------------------------------------------------------------
async def test_unread_rewinds_agent_last_seen_at(client, seeded, db_session):
    from datetime import UTC, datetime, timedelta

    owner, _, inbox, _contact, contact_inbox, admin_h, _ = seeded
    conv = await _make_conversation(db_session, contact_inbox=contact_inbox)
    # Seed an incoming message + set agent_last_seen_at to "now".
    msg = Message(
        account_id=owner.account.id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_INCOMING,
        content="hi",
        sender_type="Contact",
        sender_id=_contact.id,
    )
    db_session.add(msg)
    conv.agent_last_seen_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.add(conv)
    await db_session.flush()
    await db_session.refresh(msg)  # pull server-side created_at

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/unread",
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.content == b""

    await db_session.refresh(conv)
    # Agent's last-seen was rewound to just before the incoming message.
    assert conv.agent_last_seen_at is not None
    assert conv.agent_last_seen_at < msg.created_at


async def test_unread_noop_when_no_incoming_messages(client, seeded, db_session):
    owner, _, _, _, contact_inbox, admin_h, _ = seeded
    conv = await _make_conversation(db_session, contact_inbox=contact_inbox)

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/unread",
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.content == b""
