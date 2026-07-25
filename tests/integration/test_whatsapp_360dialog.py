"""Integration tests for the 360dialog WhatsApp provider.

The inbound parser is shared with Cloud — 360dialog ships the
``value`` object at the top level instead of wrapping it under
``entry[0].changes[0].value``. We verify a couple of representative
payloads round-trip through ``process_360dialog_webhook`` correctly.

Outbound goes through ``send_text_message_360dialog`` which posts
to the per-channel ``provider_config['url']`` with a
``D360-API-KEY`` header (no Bearer prefix). We assert the URL,
headers and body shape via respx.

Anchors:
  reference/chatwoot/app/services/whatsapp/incoming_message_service.rb
  reference/chatwoot/app/services/whatsapp/providers/whatsapp_360_dialog_service.rb
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    MESSAGE_TYPE_INCOMING,
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
    WHATSAPP_PROVIDER_360DIALOG,
    Inbox,
    WhatsappChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import User
from app.domains.whatsapp.cloud_provider import (
    _PHONE_ID_API_VERSION,  # noqa: F401  -- pin the import path
)
from app.domains.whatsapp.dialog360_provider import send_text_message_360dialog
from app.domains.whatsapp.incoming_cloud import process_360dialog_webhook

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------
async def _seed(
    db_session,
    *,
    suffix: str,
    contact_phone: str = "+5551234567",
    api_key: str = "360d-secret",
    base_url: str = "https://waba-sandbox.360dialog.io/v1",
) -> tuple[WhatsappChannel, Inbox, Conversation, User]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@d360.example.com",
            account_name=f"D360{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WA via 360dialog",
            channel_type="whatsapp",
            channel_params={
                "phone_number": f"+1555{suffix.lstrip('-').rjust(7, '0')[:7]}",
                "provider": WHATSAPP_PROVIDER_360DIALOG,
                "provider_config": {
                    "api_key": api_key,
                    "url": base_url,
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


def _d360_text_payload(
    *, from_phone: str, mid: str, body: str, profile_name: str | None = None
) -> dict[str, Any]:
    """360dialog ships the value object at the top level — not wrapped
    under ``entry[0].changes[0].value`` like Meta Cloud does.
    """
    contacts: list[dict[str, Any]] = []
    if profile_name:
        contacts.append({"profile": {"name": profile_name}, "wa_id": from_phone})
    return {
        "messages": [
            {
                "from": from_phone,
                "id": mid,
                "type": "text",
                "text": {"body": body},
                "timestamp": "1700000000",
            }
        ],
        "contacts": contacts,
    }


# ---------------------------------------------------------------------------
# Inbound — process_360dialog_webhook
# ---------------------------------------------------------------------------
async def test_360dialog_text_inbound_creates_message(db_session):
    channel, inbox, _conv, _user = await _seed(db_session, suffix="-in")
    payload = _d360_text_payload(
        from_phone="5551234567",
        mid="gB-360-1",
        body="hi from 360",
        profile_name="Diana",
    )
    out = await process_360dialog_webhook(
        db_session, channel=channel, inbox=inbox, payload=payload
    )
    assert len(out) == 1
    msg = out[0]
    assert msg.message_type == MESSAGE_TYPE_INCOMING
    assert msg.content == "hi from 360"
    assert msg.source_id == "gB-360-1"


async def test_360dialog_handles_top_level_statuses(db_session):
    channel, inbox, _conv, _user = await _seed(db_session, suffix="-stat")
    # First seed an outbound-with-known-id by sending one inbound (the
    # 5c.3 status processor only updates messages it can find).
    await process_360dialog_webhook(
        db_session,
        channel=channel,
        inbox=inbox,
        payload=_d360_text_payload(
            from_phone="5552223344",
            mid="gB-out-stat",
            body="hi",
        ),
    )
    out = await process_360dialog_webhook(
        db_session,
        channel=channel,
        inbox=inbox,
        payload={
            "statuses": [
                {
                    "id": "gB-out-stat",
                    "status": "delivered",
                    "timestamp": "1700000001",
                    "recipient_id": "5552223344",
                }
            ]
        },
    )
    assert len(out) == 1


async def test_360dialog_empty_payload_is_noop(db_session):
    channel, inbox, _conv, _user = await _seed(db_session, suffix="-empty")
    assert await process_360dialog_webhook(
        db_session, channel=channel, inbox=inbox, payload={}
    ) == []


# ---------------------------------------------------------------------------
# Outbound — send_text_message_360dialog
# ---------------------------------------------------------------------------
@respx.mock
async def test_360dialog_send_uses_d360_api_key_header(db_session):
    channel, inbox, conv, user = await _seed(db_session, suffix="-hdr")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="hello via 360",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(
        "https://waba-sandbox.360dialog.io/v1/messages"
    ).mock(
        return_value=httpx.Response(
            200, json={"messages": [{"id": "gB-out-1"}]}
        )
    )
    ok = await send_text_message_360dialog(
        db_session, channel=channel, message=msg, to_phone="5551234567"
    )
    assert ok is True
    request = route.calls.last.request
    # 360dialog uses D360-API-KEY (NOT Bearer + key like Meta Cloud).
    assert request.headers.get("d360-api-key") == "360d-secret"
    assert "authorization" not in request.headers
    body = json.loads(request.content)
    # No messaging_product field — that's Meta Cloud-only.
    assert "messaging_product" not in body
    assert body == {
        "to": "5551234567",
        "type": "text",
        "text": {"body": "hello via 360"},
    }
    await db_session.refresh(msg)
    assert msg.source_id == "gB-out-1"


@respx.mock
async def test_360dialog_send_includes_reply_context(db_session):
    channel, inbox, conv, user = await _seed(db_session, suffix="-ctx")
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="Replying",
        content_attributes={"in_reply_to_external_id": "gB-original"},
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(
        "https://waba-sandbox.360dialog.io/v1/messages"
    ).mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "gB-r"}]})
    )
    ok = await send_text_message_360dialog(
        db_session, channel=channel, message=msg, to_phone="5551234567"
    )
    assert ok is True
    body = json.loads(route.calls.last.request.content)
    assert body["context"] == {"message_id": "gB-original"}


@respx.mock
async def test_360dialog_send_4xx_returns_false(db_session):
    channel, inbox, conv, user = await _seed(db_session, suffix="-4xx")
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

    respx.post(
        "https://waba-sandbox.360dialog.io/v1/messages"
    ).mock(
        return_value=httpx.Response(
            403,
            json={"meta": {"developer_message": "invalid api key"}},
        )
    )
    ok = await send_text_message_360dialog(
        db_session, channel=channel, message=msg, to_phone="5551234567"
    )
    assert ok is False
    await db_session.refresh(msg)
    assert msg.source_id == pre


# ---------------------------------------------------------------------------
# Full create_message cascade — 360dialog inbox routing
# ---------------------------------------------------------------------------
@respx.mock
async def test_outgoing_message_routes_to_360dialog_when_provider_default(
    db_session,
):
    """Creating an outgoing Message on a Channel::Whatsapp inbox with
    provider=default routes to 360dialog (not the Meta Cloud branch)."""
    _channel, _inbox, conv, user = await _seed(db_session, suffix="-cascade")

    route = respx.post(
        "https://waba-sandbox.360dialog.io/v1/messages"
    ).mock(
        return_value=httpx.Response(
            200, json={"messages": [{"id": "gB-cascade"}]}
        )
    )
    msg = await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="from cascade", message_type="outgoing"
        ),
        user_id=user.id,
    )
    assert msg is not None
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body["text"]["body"] == "from cascade"
    assert body["to"] == "5551234567"
    await db_session.refresh(msg)
    assert msg.source_id == "gB-cascade"
