"""Integration tests for the Bandwidth SMS surface.

Single test module covers the webhook receiver + inbound processor
+ outbound sender + post-create cascade because the Bandwidth
surface is small enough to ship as one milestone (5f.4).

Anchors:
  reference/chatwoot/app/services/sms/incoming_message_service.rb
  reference/chatwoot/app/models/channel/sms.rb
  reference/chatwoot/app/controllers/webhooks/sms_controller.rb
"""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.db import get_session
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
    Inbox,
    SmsChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.sms_bandwidth.incoming import process_bandwidth_webhook
from app.domains.sms_bandwidth.sender import send_sms_bandwidth
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import User
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


def _bw_config() -> dict[str, str]:
    return {
        "account_id": "bw-acct-1",
        "api_token": "bw-token",
        "api_secret": "bw-secret",
        "application_id": "bw-app-1",
    }


async def _seed(
    db_session,
    *,
    suffix: str,
    phone_number: str = "+15551234567",
) -> tuple[SmsChannel, Inbox, Conversation, User]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@bw.example.com",
            account_name=f"BW{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Bandwidth SMS",
            channel_type="sms",
            channel_params={
                "phone_number": phone_number,
                "provider_config": _bw_config(),
            },
        ),
    ).perform()
    assert isinstance(result.channel, SmsChannel)

    contact = Contact(
        account_id=owner.account.id,
        phone_number="+15559998888",
        name="Diana",
    )
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=result.inbox,
        source_id="+15559998888",
    ).perform()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    return result.channel, result.inbox, conv, owner.user


def _bw_url(account_id: str = "bw-acct-1") -> str:
    return f"https://messaging.bandwidth.com/api/v2/users/{account_id}/messages"


def _bw_inbound(
    *, bw_id: str, from_phone: str, to_phone: str, text: str
) -> list[dict[str, Any]]:
    """Bandwidth wraps each event in an array; one element per inbound."""
    return [
        {
            "type": "message-received",
            "message": {
                "id": bw_id,
                "from": from_phone,
                "to": [to_phone],
                "text": text,
                "applicationId": "bw-app-1",
                "time": "2026-05-06T12:34:56Z",
            },
        }
    ]


# ===========================================================================
# Inbound — process_bandwidth_webhook
# ===========================================================================
async def test_inbound_creates_contact_and_message(db_session):
    _channel, _inbox, _conv, _user = await _seed(
        db_session, suffix="-in", phone_number="+15551234567"
    )
    out = await process_bandwidth_webhook(
        db_session,
        payload=_bw_inbound(
            bw_id="bw-id-1",
            from_phone="+15558887777",
            to_phone="+15551234567",
            text="hi from bw",
        ),
        phone_number="+15551234567",
    )
    assert len(out) == 1
    msg = out[0]
    assert msg.message_type == MESSAGE_TYPE_INCOMING
    assert msg.content == "hi from bw"
    assert msg.source_id == "bw-id-1"

    contact = (
        await db_session.exec(
            select(Contact).where(Contact.phone_number == "+15558887777")
        )
    ).first()
    assert contact is not None


async def test_inbound_unknown_phone_drops_silently(db_session):
    await _seed(db_session, suffix="-unknown", phone_number="+15551111111")
    out = await process_bandwidth_webhook(
        db_session,
        payload=_bw_inbound(
            bw_id="x",
            from_phone="+15558887777",
            to_phone="+19999999999",
            text="hi",
        ),
        phone_number="+19999999999",  # no matching channel
    )
    assert out == []


async def test_inbound_skips_non_message_received_events(db_session):
    """Bandwidth delivers delivery / failure callbacks alongside
    message-received. 5f.4 only handles message-received; other types
    drop silently."""
    await _seed(db_session, suffix="-delivery", phone_number="+15553334444")
    payload = [
        {
            "type": "message-delivered",
            "message": {"id": "bw-x", "from": "+1", "to": ["+15553334444"]},
        }
    ]
    out = await process_bandwidth_webhook(
        db_session, payload=payload, phone_number="+15553334444"
    )
    assert out == []


async def test_inbound_idempotent_on_bandwidth_id(db_session):
    await _seed(db_session, suffix="-dup", phone_number="+15554445555")
    payload = _bw_inbound(
        bw_id="bw-dup",
        from_phone="+15558887777",
        to_phone="+15554445555",
        text="once",
    )
    first = await process_bandwidth_webhook(
        db_session, payload=payload, phone_number="+15554445555"
    )
    second = await process_bandwidth_webhook(
        db_session, payload=payload, phone_number="+15554445555"
    )
    assert len(first) == 1
    assert second == []


async def test_webhook_endpoint_accepts_json(client, db_session):
    """End-to-end: HTTP POST with JSON body lands a Message."""
    await _seed(db_session, suffix="-http", phone_number="+15555556666")
    body = _bw_inbound(
        bw_id="bw-http",
        from_phone="+15551112222",
        to_phone="+15555556666",
        text="via http",
    )
    resp = await client.post(
        "/webhooks/sms/+15555556666",
        json=body,
    )
    assert resp.status_code == 200
    msg = (
        await db_session.exec(
            select(Message).where(Message.source_id == "bw-http")
        )
    ).first()
    assert msg is not None


async def test_webhook_unknown_phone_still_200s(client):
    """Bandwidth retries on 5xx; unknown phones drop silently with 200."""
    resp = await client.post(
        "/webhooks/sms/+19999999999",
        json=_bw_inbound(
            bw_id="x",
            from_phone="+1",
            to_phone="+19999999999",
            text="hi",
        ),
    )
    assert resp.status_code == 200


async def test_webhook_malformed_json_still_200s(client):
    resp = await client.post(
        "/webhooks/sms/+15551234567",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Optional per-channel HTTP Basic Auth (CH-1)
# ---------------------------------------------------------------------------
import base64 as _base64  # noqa: E402


async def _enable_basic_auth(
    db_session, channel: SmsChannel, *, user: str, password: str
) -> None:
    """Stamp Bandwidth callback Basic-Auth creds into provider_config."""
    channel.provider_config = {
        **(channel.provider_config or {}),
        "webhook_user": user,
        "webhook_pass": password,
    }
    db_session.add(channel)
    await db_session.flush()


def _basic(user: str, password: str) -> str:
    return "Basic " + _base64.b64encode(
        f"{user}:{password}".encode()
    ).decode()


async def test_webhook_basic_auth_valid_passes(client, db_session):
    channel, *_ = await _seed(
        db_session, suffix="-ba-ok", phone_number="+15550001111"
    )
    await _enable_basic_auth(db_session, channel, user="bw", password="s3cr3t")
    resp = await client.post(
        "/webhooks/sms/+15550001111",
        json=_bw_inbound(
            bw_id="bw-ba-ok",
            from_phone="+15551112222",
            to_phone="+15550001111",
            text="authed",
        ),
        headers={"Authorization": _basic("bw", "s3cr3t")},
    )
    assert resp.status_code == 200
    msg = (
        await db_session.exec(
            select(Message).where(Message.source_id == "bw-ba-ok")
        )
    ).first()
    assert msg is not None


async def test_webhook_basic_auth_invalid_401(client, db_session):
    channel, *_ = await _seed(
        db_session, suffix="-ba-bad", phone_number="+15550002222"
    )
    await _enable_basic_auth(db_session, channel, user="bw", password="s3cr3t")
    resp = await client.post(
        "/webhooks/sms/+15550002222",
        json=_bw_inbound(
            bw_id="bw-ba-bad",
            from_phone="+15551112222",
            to_phone="+15550002222",
            text="forged",
        ),
        headers={"Authorization": _basic("bw", "wrong")},
    )
    assert resp.status_code == 401
    # The forged payload must NOT have been ingested.
    msg = (
        await db_session.exec(
            select(Message).where(Message.source_id == "bw-ba-bad")
        )
    ).first()
    assert msg is None


async def test_webhook_basic_auth_missing_401_when_configured(
    client, db_session
):
    channel, *_ = await _seed(
        db_session, suffix="-ba-miss", phone_number="+15550003333"
    )
    await _enable_basic_auth(db_session, channel, user="bw", password="s3cr3t")
    resp = await client.post(
        "/webhooks/sms/+15550003333",
        json=_bw_inbound(
            bw_id="bw-ba-miss",
            from_phone="+15551112222",
            to_phone="+15550003333",
            text="no auth",
        ),
    )
    assert resp.status_code == 401


# ===========================================================================
# Outbound — send_sms_bandwidth
# ===========================================================================
@respx.mock
async def test_send_text_posts_to_bandwidth_with_basic_auth(db_session):
    channel, inbox, conv, user = await _seed(
        db_session, suffix="-shape", phone_number="+15556667777"
    )
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="hi via bw",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()

    route = respx.post(_bw_url()).mock(
        return_value=httpx.Response(
            202,
            json={"id": "bw-out-1", "owner": "+15556667777"},
        )
    )
    ok = await send_sms_bandwidth(
        db_session, channel=channel, message=msg, to_phone="+15558881111"
    )
    assert ok is True
    request = route.calls.last.request
    expected_auth = "Basic " + base64.b64encode(b"bw-token:bw-secret").decode()
    assert request.headers.get("authorization") == expected_auth
    body = json.loads(request.content)
    assert body == {
        "to": ["+15558881111"],
        "from": "+15556667777",
        "text": "hi via bw",
        "applicationId": "bw-app-1",
    }
    await db_session.refresh(msg)
    assert msg.source_id == "bw-out-1"


@respx.mock
async def test_send_text_4xx_returns_false_no_stamp(db_session):
    channel, inbox, conv, user = await _seed(
        db_session, suffix="-fail", phone_number="+15557778888"
    )
    msg = Message(
        account_id=channel.account_id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_OUTGOING,
        content_type=0,
        content="fail",
        sender_type="User",
        sender_id=user.id,
        private=False,
    )
    db_session.add(msg)
    await db_session.flush()
    pre = msg.source_id

    respx.post(_bw_url()).mock(
        return_value=httpx.Response(
            400,
            json={
                "type": "request-validation",
                "description": "invalid",
            },
        )
    )
    ok = await send_sms_bandwidth(
        db_session, channel=channel, message=msg, to_phone="+15558889999"
    )
    assert ok is False
    await db_session.refresh(msg)
    assert msg.source_id == pre


# ===========================================================================
# Full create_message cascade
# ===========================================================================
@respx.mock
async def test_outgoing_via_create_message_hits_bandwidth(db_session):
    _channel, _inbox, conv, user = await _seed(
        db_session, suffix="-cascade", phone_number="+15559990000"
    )
    route = respx.post(_bw_url()).mock(
        return_value=httpx.Response(202, json={"id": "bw-cascade"})
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
    assert body["from"] == "+15559990000"
    # The seeded ContactInbox source_id was +15559998888.
    assert body["to"] == ["+15559998888"]
    await db_session.refresh(msg)
    assert msg.source_id == "bw-cascade"
