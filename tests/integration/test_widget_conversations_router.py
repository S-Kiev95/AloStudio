"""Integration tests for the widget conversation + message endpoints
(``/api/v1/widget/conversations*`` + ``/api/v1/widget/messages*``).

Anchors:
  reference/chatwoot/app/controllers/api/v1/widget/conversations_controller.rb
  reference/chatwoot/app/controllers/api/v1/widget/messages_controller.rb
  reference/chatwoot/app/controllers/api/v1/widget/base_controller.rb

Coverage:
  * GET /widget/conversations: null when none, last conversation when present.
  * POST /widget/messages auto-creates the conversation, sends incoming,
    returns the message push-event shape with sender=contact.
  * GET /widget/messages: empty when no conversation, paginated otherwise.
  * update_last_seen, toggle_typing, toggle_status (with end_conversation
    flag gate).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.conversations.models import (
    CONVERSATION_STATUS_RESOLVED,
    MESSAGE_TYPE_INCOMING,
    Conversation,
    Message,
)
from app.domains.inboxes.models import WebWidget
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
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


async def _seed_widget(db_session, *, end_conversation: bool = True):
    """Create a fresh account + WebWidget inbox.

    The widget defaults to feature_flags=7 which enables
    end_conversation. To exercise the gate we toggle the bit off.
    """
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@conv-w.example.com",
            account_name="ConvW",
            user_full_name="ConvW Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Widget",
            channel_type="web_widget",
            channel_params={"website_url": "https://example.com"},
        ),
    ).perform()
    web_widget = result.channel
    assert isinstance(web_widget, WebWidget)
    if not end_conversation:
        # Drop bit 3 (end_conversation).
        web_widget.feature_flags &= ~(1 << 2)
        db_session.add(web_widget)
        await db_session.flush()
        await db_session.refresh(web_widget)
    return owner, result.inbox, web_widget


async def _bootstrap_widget(client, ww: WebWidget) -> str:
    """Hit /widget/config to mint a contact + token. Returns the JWT."""
    resp = await client.post(
        f"/api/v1/widget/config?website_token={ww.website_token}"
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["auth_token"]


# ---------------------------------------------------------------------------
# /widget/conversations  (index)
# ---------------------------------------------------------------------------
async def test_conversations_index_null_when_visitor_has_none(
    client, db_session
):
    _, _, ww = await _seed_widget(db_session)
    token = await _bootstrap_widget(client, ww)
    resp = await client.get(
        f"/api/v1/widget/conversations?website_token={ww.website_token}",
        headers={"X-Auth-Token": token},
    )
    assert resp.status_code == 200
    assert resp.json() is None


async def test_conversations_index_returns_last_conversation(
    client, db_session
):
    """After a /widget/messages POST creates a conversation, the index
    returns that conversation's push-event shape."""
    _, _, ww = await _seed_widget(db_session)
    token = await _bootstrap_widget(client, ww)
    create = await client.post(
        f"/api/v1/widget/messages?website_token={ww.website_token}",
        json={"message": {"content": "Hello"}},
        headers={"X-Auth-Token": token},
    )
    assert create.status_code == 200, create.text

    resp = await client.get(
        f"/api/v1/widget/conversations?website_token={ww.website_token}",
        headers={"X-Auth-Token": token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body is not None
    assert body["status"] == "open"


# ---------------------------------------------------------------------------
# /widget/messages
# ---------------------------------------------------------------------------
async def test_messages_create_auto_creates_conversation(
    client, db_session
):
    """First /widget/messages POST mints a conversation + sends an
    incoming message whose sender is the contact."""
    _, inbox, ww = await _seed_widget(db_session)
    token = await _bootstrap_widget(client, ww)

    resp = await client.post(
        f"/api/v1/widget/messages?website_token={ww.website_token}",
        json={
            "message": {
                "content": "Need help with billing",
                "echo_id": "client-xyz",
                "referer_url": "https://example.com/pricing",
                "reply_to": 99,
            }
        },
        headers={"X-Auth-Token": token},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["content"] == "Need help with billing"
    assert body["echo_id"] == "client-xyz"
    # Wire ``message_type`` is the integer (incoming = 0).
    assert body["message_type"] == MESSAGE_TYPE_INCOMING
    # ``content_attributes.in_reply_to`` carries through.
    assert body["content_attributes"]["in_reply_to"] == 99

    # DB state: one conversation, one message, sender_type=Contact.
    conv = (
        await db_session.exec(
            select(Conversation).where(
                Conversation.contact_inbox_id == None  # noqa: E711
            )
        )
    ).first()
    # The contact_inbox_id IS set; the above is a defensive shape check
    # — find by inbox id instead.
    conv = (
        await db_session.exec(
            select(Conversation).where(Conversation.inbox_id == inbox.id)
        )
    ).first()
    assert conv is not None
    msgs = list(
        (
            await db_session.exec(
                select(Message).where(Message.conversation_id == conv.id)
            )
        ).all()
    )
    assert len(msgs) == 1
    assert msgs[0].sender_type == "Contact"
    # Conversation carries the referer in additional_attributes.
    assert (conv.additional_attributes or {}).get("referer") == "https://example.com/pricing"


async def test_messages_create_appends_to_existing_conversation(
    client, db_session
):
    _, _, ww = await _seed_widget(db_session)
    token = await _bootstrap_widget(client, ww)

    await client.post(
        f"/api/v1/widget/messages?website_token={ww.website_token}",
        json={"message": {"content": "First"}},
        headers={"X-Auth-Token": token},
    )
    await client.post(
        f"/api/v1/widget/messages?website_token={ww.website_token}",
        json={"message": {"content": "Second"}},
        headers={"X-Auth-Token": token},
    )

    convs = list(
        (
            await db_session.exec(select(Conversation))
        ).all()
    )
    assert len(convs) == 1
    msgs = list(
        (
            await db_session.exec(
                select(Message).where(Message.conversation_id == convs[0].id)
            )
        ).all()
    )
    contents = sorted(m.content for m in msgs)
    assert contents == ["First", "Second"]


async def test_messages_index_empty_when_no_conversation(client, db_session):
    _, _, ww = await _seed_widget(db_session)
    token = await _bootstrap_widget(client, ww)
    resp = await client.get(
        f"/api/v1/widget/messages?website_token={ww.website_token}",
        headers={"X-Auth-Token": token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"meta": {}, "payload": []}


async def test_messages_index_returns_messages_oldest_first(
    client, db_session
):
    _, _, ww = await _seed_widget(db_session)
    token = await _bootstrap_widget(client, ww)
    for n in range(3):
        await client.post(
            f"/api/v1/widget/messages?website_token={ww.website_token}",
            json={"message": {"content": f"msg-{n}"}},
            headers={"X-Auth-Token": token},
        )
    resp = await client.get(
        f"/api/v1/widget/messages?website_token={ww.website_token}",
        headers={"X-Auth-Token": token},
    )
    assert resp.status_code == 200
    payload = resp.json()["payload"]
    contents = [m["content"] for m in payload]
    assert contents == ["msg-0", "msg-1", "msg-2"]


# ---------------------------------------------------------------------------
# update_last_seen / toggle_typing / toggle_status
# ---------------------------------------------------------------------------
async def test_update_last_seen_stamps_contact_last_seen_at(
    client, db_session
):
    _, _, ww = await _seed_widget(db_session)
    token = await _bootstrap_widget(client, ww)
    await client.post(
        f"/api/v1/widget/messages?website_token={ww.website_token}",
        json={"message": {"content": "hello"}},
        headers={"X-Auth-Token": token},
    )

    resp = await client.post(
        f"/api/v1/widget/conversations/update_last_seen?website_token={ww.website_token}",
        headers={"X-Auth-Token": token},
    )
    assert resp.status_code == 200
    conv = (await db_session.exec(select(Conversation))).first()
    assert conv is not None
    assert conv.contact_last_seen_at is not None


async def test_toggle_typing_returns_ok(client, db_session):
    """The dispatcher fan-out side-effects are covered by 4b's listener
    tests; here we just assert the endpoint accepts the call."""
    _, _, ww = await _seed_widget(db_session)
    token = await _bootstrap_widget(client, ww)
    await client.post(
        f"/api/v1/widget/messages?website_token={ww.website_token}",
        json={"message": {"content": "hi"}},
        headers={"X-Auth-Token": token},
    )
    resp = await client.post(
        f"/api/v1/widget/conversations/toggle_typing?website_token={ww.website_token}",
        json={"typing_status": "on"},
        headers={"X-Auth-Token": token},
    )
    assert resp.status_code == 200


async def test_toggle_status_resolves_when_flag_enabled(
    client, db_session
):
    _, _, ww = await _seed_widget(db_session, end_conversation=True)
    token = await _bootstrap_widget(client, ww)
    await client.post(
        f"/api/v1/widget/messages?website_token={ww.website_token}",
        json={"message": {"content": "hi"}},
        headers={"X-Auth-Token": token},
    )
    resp = await client.post(
        f"/api/v1/widget/conversations/toggle_status?website_token={ww.website_token}",
        headers={"X-Auth-Token": token},
    )
    assert resp.status_code == 200
    conv = (await db_session.exec(select(Conversation))).first()
    assert conv is not None
    assert conv.status == CONVERSATION_STATUS_RESOLVED


async def test_toggle_status_403_when_flag_disabled(client, db_session):
    """Mirror Rails ``return head :forbidden unless @web_widget.end_conversation?``."""
    _, _, ww = await _seed_widget(db_session, end_conversation=False)
    token = await _bootstrap_widget(client, ww)
    await client.post(
        f"/api/v1/widget/messages?website_token={ww.website_token}",
        json={"message": {"content": "hi"}},
        headers={"X-Auth-Token": token},
    )
    resp = await client.post(
        f"/api/v1/widget/conversations/toggle_status?website_token={ww.website_token}",
        headers={"X-Auth-Token": token},
    )
    assert resp.status_code == 403
