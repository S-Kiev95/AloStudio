"""Integration tests for the Instagram outbound path.

Uses respx to intercept httpx calls to Meta's Graph API. Tests
assert the URL, query string, body shape, and the message_id
round-trip stamping on ``messages.source_id``.

Anchors:
  reference/chatwoot/app/services/instagram/messenger/send_on_instagram_service.rb
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
)
from app.domains.inboxes.models import Inbox, InstagramChannel
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram.sender import send_text_message_instagram
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import User

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------
async def _seed(
    db_session,
    *,
    suffix: str,
    igsid: str = "IGSID-OUT-42",
    instagram_id: str = "IG-ACCT",
    access_token: str = "EAAxxxx-ig",
) -> tuple[InstagramChannel, Inbox, Conversation, User]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@igout.example.com",
            account_name=f"IGOut{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="IG Inbox",
            channel_type="instagram",
            channel_params={
                "instagram_id": instagram_id,
                "access_token": access_token,
                "expires_at": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
            },
        ),
    ).perform()
    assert isinstance(result.channel, InstagramChannel)

    contact = Contact(account_id=owner.account.id, name="Diana")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=result.inbox,
        source_id=igsid,
    ).perform()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    return result.channel, result.inbox, conv, owner.user


def _expected_url(channel: InstagramChannel) -> str:
    settings = get_settings()
    return (
        f"https://graph.facebook.com/{settings.facebook_api_version}"
        f"/me/messages?access_token={channel.access_token}"
    )


# ---------------------------------------------------------------------------
# send_text_message_instagram — direct
# ---------------------------------------------------------------------------
@respx.mock
async def test_send_text_posts_canonical_body(db_session):
    channel, inbox, conv, user = await _seed(db_session, suffix="-shape")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="hi from Chatwoot via IG",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(
            200,
            json={"recipient_id": "IGSID-OUT-42", "message_id": "ig.mid.out"},
        )
    )
    ok = await send_text_message_instagram(
        db_session, channel=channel, message=msg, to_igsid="IGSID-OUT-42"
    )
    assert ok is True
    body = json.loads(route.calls.last.request.content)
    # IG body has NO ``messaging_type``/``tag`` fields (Messenger-only).
    assert body == {
        "recipient": {"id": "IGSID-OUT-42"},
        "message": {"text": "hi from Chatwoot via IG"},
    }
    await db_session.refresh(msg)
    assert msg.source_id == "ig.mid.out"


@respx.mock
async def test_send_text_4xx_returns_false_no_stamp(db_session):
    channel, inbox, conv, user = await _seed(db_session, suffix="-fail")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="will fail",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()
    pre = msg.source_id

    respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(
            403,
            json={
                "error": {
                    "message": "User cannot be messaged",
                    "code": 100,
                }
            },
        )
    )
    ok = await send_text_message_instagram(
        db_session, channel=channel, message=msg, to_igsid="IGSID-OUT-42"
    )
    assert ok is False
    await db_session.refresh(msg)
    assert msg.source_id == pre


@respx.mock
async def test_send_text_skips_when_no_igsid(db_session):
    channel, inbox, conv, user = await _seed(db_session, suffix="-noid")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="x",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post("https://graph.facebook.com/").mock(
        return_value=httpx.Response(500)
    )
    ok = await send_text_message_instagram(
        db_session, channel=channel, message=msg, to_igsid=""
    )
    assert ok is False
    assert not route.called


# ---------------------------------------------------------------------------
# Full create_message cascade
# ---------------------------------------------------------------------------
@respx.mock
async def test_outgoing_message_via_create_message_hits_graph(db_session):
    """Creating an outgoing Message on a Channel::Instagram inbox via
    create_message triggers the Graph send through the post-create
    cascade. The IGSID resolves from ContactInbox.source_id."""
    channel, inbox, conv, user = await _seed(
        db_session, suffix="-cascade", igsid="IGSID-CASCADE"
    )
    route = respx.post(_expected_url(channel)).mock(
        return_value=httpx.Response(
            200,
            json={
                "recipient_id": "IGSID-CASCADE",
                "message_id": "ig.cascade",
            },
        )
    )
    msg = await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="from cascade",
            message_type="outgoing",
        ),
        user_id=user.id,
    )
    assert msg is not None
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body["recipient"] == {"id": "IGSID-CASCADE"}
    assert body["message"]["text"] == "from cascade"
    await db_session.refresh(msg)
    assert msg.source_id == "ig.cascade"
