"""Integration tests for the WhatsApp Cloud outbound path.

Uses ``respx`` to intercept httpx calls to Meta's Graph API. The
real Graph endpoint is never hit; tests assert on the URL path,
headers and body shape we POST plus the WAMID round-trip stamping
on ``messages.source_id``.

Anchors:
  reference/chatwoot/app/services/whatsapp/providers/whatsapp_cloud_service.rb
  reference/chatwoot/spec/services/whatsapp/providers/whatsapp_cloud_service_spec.rb
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

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
from app.domains.inboxes.models import (
    WHATSAPP_PROVIDER_CLOUD,
    Inbox,
    WhatsappChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams

# Resolve mappers (Conversation.team forward-ref).
from app.domains.teams import models as _teams  # noqa: F401
from app.domains.users.models import User
from app.domains.whatsapp.cloud_provider import (
    _PHONE_ID_API_VERSION,
    send_text_message_cloud,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------
async def _seed(
    db_session,
    *,
    suffix: str,
    contact_phone: str = "+5551234567",
) -> tuple[WhatsappChannel, Inbox, Conversation, User]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@waout.example.com",
            account_name=f"WAOut{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WA Inbox",
            channel_type="whatsapp",
            channel_params={
                "phone_number": f"+1555000{suffix.lstrip('-')[:4] or '0001'}",
                "provider": WHATSAPP_PROVIDER_CLOUD,
                "provider_config": {
                    "api_key": "EAAxxxx-secret",
                    "phone_number_id": "12345",
                    "business_account_id": "67890",
                },
            },
        ),
    ).perform()
    assert isinstance(result.channel, WhatsappChannel)
    contact = Contact(
        account_id=owner.account.id,
        phone_number=contact_phone,
        name="Diana",
    )
    db_session.add(contact)
    await db_session.flush()
    contact_inbox = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=result.inbox,
        source_id=contact_phone,
    ).perform()
    conversation = await create_conversation(
        db_session,
        contact_inbox=contact_inbox,
        params=ConversationBuilderParams(),
    )
    return result.channel, result.inbox, conversation, owner.user


def _graph_url(channel: WhatsappChannel) -> str:
    pid = channel.provider_config["phone_number_id"]
    return f"https://graph.facebook.com/{_PHONE_ID_API_VERSION}/{pid}/messages"


# ---------------------------------------------------------------------------
# send_text_message_cloud — direct
# ---------------------------------------------------------------------------
@respx.mock
async def test_send_text_posts_to_graph_with_correct_shape(db_session):
    channel, _inbox, _conv, _user = await _seed(db_session, suffix="-shape")

    # Insert an outbound message manually; we don't want the post-create
    # cascade firing here — we test send_text_message_cloud in isolation.
    msg = Message(
        account_id=channel.account_id,
        inbox_id=_inbox.id,
        conversation_id=_conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="Hello from the agent",
        sender_type="User",
        sender_id=_user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(_graph_url(channel)).mock(
        return_value=httpx.Response(
            200,
            json={
                "messaging_product": "whatsapp",
                "contacts": [{"input": "5551234567", "wa_id": "5551234567"}],
                "messages": [{"id": "wamid.HBgB-graph-id-123"}],
            },
        )
    )

    ok = await send_text_message_cloud(
        db_session, channel=channel, message=msg, to_phone="5551234567"
    )
    assert ok is True
    assert route.called
    request = route.calls.last.request
    assert request.headers.get("authorization") == "Bearer EAAxxxx-secret"
    assert request.headers.get("content-type") == "application/json"
    body = json.loads(request.content)
    assert body == {
        "messaging_product": "whatsapp",
        "to": "5551234567",
        "type": "text",
        "text": {"body": "Hello from the agent"},
    }
    # Stamped WAMID on source_id.
    await db_session.refresh(msg)
    assert msg.source_id == "wamid.HBgB-graph-id-123"


@respx.mock
async def test_send_text_includes_reply_context_when_set(db_session):
    """``content_attributes.in_reply_to_external_id`` -> Meta
    ``context.message_id``. Used for "quoted reply" UX."""
    channel, _inbox, _conv, _user = await _seed(db_session, suffix="-reply")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=_inbox.id,
        conversation_id=_conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="Replying to your earlier note",
        content_attributes={"in_reply_to_external_id": "wamid.original-1"},
        sender_type="User",
        sender_id=_user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(_graph_url(channel)).mock(
        return_value=httpx.Response(
            200,
            json={"messages": [{"id": "wamid.reply-out"}]},
        )
    )
    ok = await send_text_message_cloud(
        db_session, channel=channel, message=msg, to_phone="5551234567"
    )
    assert ok is True
    body = json.loads(route.calls.last.request.content)
    assert body["context"] == {"message_id": "wamid.original-1"}


@respx.mock
async def test_send_text_4xx_returns_false_and_doesnt_stamp(db_session):
    channel, _inbox, _conv, _user = await _seed(db_session, suffix="-fail")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=_inbox.id,
        conversation_id=_conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="this will fail",
        sender_type="User",
        sender_id=_user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()
    pre_source_id = msg.source_id

    respx.post(_graph_url(channel)).mock(
        return_value=httpx.Response(
            400,
            json={
                "error": {
                    "message": "(#100) Invalid parameter",
                    "type": "OAuthException",
                    "code": 100,
                }
            },
        )
    )
    ok = await send_text_message_cloud(
        db_session, channel=channel, message=msg, to_phone="5551234567"
    )
    assert ok is False
    await db_session.refresh(msg)
    assert msg.source_id == pre_source_id  # unchanged


@respx.mock
async def test_send_text_transport_error_returns_false(db_session):
    """ConnectError raised by httpx is swallowed + returns False —
    must never propagate to the caller (a Graph outage shouldn't
    break the create-message flow)."""
    channel, _inbox, _conv, _user = await _seed(db_session, suffix="-net")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=_inbox.id,
        conversation_id=_conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="net dies mid-flight",
        sender_type="User",
        sender_id=_user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    respx.post(_graph_url(channel)).mock(
        side_effect=httpx.ConnectError("dns fail")
    )
    ok = await send_text_message_cloud(
        db_session, channel=channel, message=msg, to_phone="5551234567"
    )
    assert ok is False


@respx.mock
async def test_send_text_skips_when_provider_config_incomplete(db_session):
    """Channel with empty provider_config should short-circuit before
    any HTTP call. Graph remains untouched."""
    channel, _inbox, _conv, _user = await _seed(db_session, suffix="-bad")
    # Mutate to a degenerate provider_config (kept in DB so attr access
    # works, but missing the required keys).
    channel.provider_config = {}
    db_session.add(channel)
    await db_session.flush()
    await db_session.refresh(channel)

    msg = Message(
        account_id=channel.account_id,
        inbox_id=_inbox.id,
        conversation_id=_conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="x",
        sender_type="User",
        sender_id=_user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    # Channel has no provider_config — send_text_message_cloud must
    # short-circuit BEFORE any HTTP call. We register a catch-all
    # respx route so that any actual call would surface as a 500
    # (and the test would notice).
    route = respx.post(
        "https://graph.facebook.com/"
    ).mock(return_value=httpx.Response(500))
    ok = await send_text_message_cloud(
        db_session, channel=channel, message=msg, to_phone="5551234567"
    )
    assert ok is False
    assert not route.called


# ---------------------------------------------------------------------------
# Full create_message cascade — outbound message on a WhatsApp inbox
# ---------------------------------------------------------------------------
@respx.mock
async def test_outgoing_message_via_create_message_hits_graph(db_session):
    """Creating an outgoing Message on a Channel::Whatsapp inbox via
    the canonical ``create_message`` path triggers Graph send through
    the post-create cascade."""
    channel, _inbox, conv, user = await _seed(db_session, suffix="-cascade")

    route = respx.post(_graph_url(channel)).mock(
        return_value=httpx.Response(
            200, json={"messages": [{"id": "wamid.cascade"}]}
        )
    )

    msg = await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="from the cascade",
            message_type="outgoing",
        ),
        user_id=user.id,
    )
    assert msg is not None
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body["text"]["body"] == "from the cascade"
    # Phone-number stripped to bare wa_id (no leading ``+``).
    assert body["to"] == "5551234567"

    await db_session.refresh(msg)
    assert msg.source_id == "wamid.cascade"
