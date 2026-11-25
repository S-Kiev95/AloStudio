# ruff: noqa: F811  (pytest fixtures imported from the onboarding tests)
"""WhatsApp coexistence (F2): a WhatsApp Business app number connected by
Embedded Signup keeps working on the phone.

* The popup names only the WABA: the number is the one on the app, it is
  not registered again, and its contacts and history are requested.
* ``smb_message_echoes``: what the business answers from the phone shows
  in the conversation and is never sent again.
* ``history``: old chats land quietly (resolved, original dates).
* ``smb_app_state_sync``: the phone's contacts.
* ``account_update``: a disconnected number is marked, and unmarked when
  it reconnects.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from sqlmodel import select

from app.domains.contacts.models import Contact
from app.domains.conversations.models import (
    CONVERSATION_STATUS_RESOLVED,
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
)
from app.domains.inboxes.models import Inbox, WhatsappChannel
from tests.integration.test_multitenant_onboarding import (  # noqa: F401  (fixtures)
    GRAPH,
    _account,
    _channel_for,
    _meta,
    _whatsapp_inbox,
    client,
    multitenant,
)

pytestmark = pytest.mark.integration


def _coexistence_meta(mock: respx.MockRouter) -> dict[str, respx.Route]:
    routes = _meta(mock)
    routes["phones"] = mock.get(f"{GRAPH}/waba-1/phone_numbers").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "pn-1",
                        "display_phone_number": "+598 92 111 222",
                        "verified_name": "Tienda Uno",
                        "code_verification_status": "NOT_VERIFIED",
                        "platform_type": "CLOUD_API",
                        "is_on_biz_app": True,
                    }
                ]
            },
        )
    )
    routes["app_data"] = mock.post(f"{GRAPH}/pn-1/smb_app_data").mock(
        return_value=httpx.Response(
            200, json={"messaging_product": "whatsapp", "request_id": "req-1"}
        )
    )
    return routes


async def test_a_business_app_number_connects_and_asks_for_its_data(client, db_session):
    a, headers = await _account(db_session, "-coex")
    with respx.mock(assert_all_called=False) as mock:
        routes = _coexistence_meta(mock)
        resp = await client.post(
            f"/api/v1/accounts/{a.account.id}/whatsapp/embedded_signup",
            headers=headers,
            json={"code": "code-1", "waba_id": "waba-1"},
        )
    assert resp.status_code == 200, resp.text

    channel = await _channel_for(db_session, "+59892111222")
    assert channel is not None
    config = channel.provider_config
    assert config["phone_number_id"] == "pn-1"
    assert config["coexistence"] is True
    assert config["coexistence_sync"]["contacts"] == "requested"
    assert config["coexistence_sync"]["history"] == "requested"
    # Already registered on the app: no registration, even if Meta says
    # the code is not verified.
    assert not routes["register"].called
    kinds = [json.loads(c.request.content)["sync_type"] for c in routes["app_data"].calls]
    assert kinds == ["smb_app_state_sync", "history"]


async def test_a_failed_sync_request_still_connects_the_number(client, db_session):
    a, headers = await _account(db_session, "-coex-fail")
    with respx.mock(assert_all_called=False) as mock:
        routes = _coexistence_meta(mock)
        routes["app_data"].mock(return_value=httpx.Response(500, json={}))
        resp = await client.post(
            f"/api/v1/accounts/{a.account.id}/whatsapp/embedded_signup",
            headers=headers,
            json={"code": "code-1", "waba_id": "waba-1"},
        )
    assert resp.status_code == 200, resp.text
    channel = await _channel_for(db_session, "+59892111222")
    assert channel is not None
    assert channel.provider_config["coexistence_sync"]["history"] == "failed"


async def test_without_a_number_a_waba_with_several_is_refused(client, db_session):
    a, headers = await _account(db_session, "-coex-many")
    with respx.mock(assert_all_called=False) as mock:
        routes = _meta(mock)
        routes["phones"].mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "pn-1", "display_phone_number": "+598 92 111 222"},
                        {"id": "pn-2", "display_phone_number": "+598 92 333 444"},
                    ]
                },
            )
        )
        resp = await client.post(
            f"/api/v1/accounts/{a.account.id}/whatsapp/embedded_signup",
            headers=headers,
            json={"code": "code-1", "waba_id": "waba-1"},
        )
    assert resp.status_code == 422
    assert await _channel_for(db_session, "+59892111222") is None


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------
BUSINESS = "59891000009"


async def _coexistence_inbox(db_session, suffix: str) -> tuple[Any, Inbox]:
    owner, _ = await _account(db_session, suffix)
    inbox = await _whatsapp_inbox(db_session, owner, phone=f"+{BUSINESS}", number_id="pn-c")
    channel = await db_session.get(WhatsappChannel, inbox.channel_id)
    channel.provider_config = {**channel.provider_config, "coexistence": True}
    db_session.add(channel)
    await db_session.flush()
    return owner, inbox


async def _post(client, field: str, value: dict[str, Any], *, entry_id: str = "waba-x") -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"id": entry_id, "changes": [{"field": field, "value": value}]}],
    }
    resp = await client.post("/webhooks/whatsapp", content=json.dumps(payload))
    assert resp.status_code == 200


def _metadata() -> dict[str, str]:
    return {"display_phone_number": BUSINESS, "phone_number_id": "pn-c"}


async def _messages(db_session, inbox: Inbox) -> list[Message]:
    return list(
        (
            await db_session.exec(
                select(Message).where(Message.inbox_id == inbox.id).order_by(Message.created_at)
            )
        ).all()
    )


async def test_a_reply_from_the_phone_shows_in_the_conversation(client, db_session, monkeypatch):
    sent: list[int] = []

    async def _no_send(session, *, message, conversation):
        sent.append(message.id)

    monkeypatch.setattr("app.domains.conversations.service._maybe_send_outbound_whatsapp", _no_send)
    _, inbox = await _coexistence_inbox(db_session, "-coex-echo")
    await _post(
        client,
        "smb_message_echoes",
        {
            "messaging_product": "whatsapp",
            "metadata": _metadata(),
            "message_echoes": [
                {
                    "from": BUSINESS,
                    "to": "59899111222",
                    "id": "wamid.echo1",
                    "timestamp": "1739230955",
                    "type": "text",
                    "text": {"body": "Te lo mando hoy"},
                }
            ],
        },
    )
    rows = await _messages(db_session, inbox)
    assert [(m.content, m.message_type) for m in rows] == [
        ("Te lo mando hoy", MESSAGE_TYPE_OUTGOING)
    ]
    assert rows[0].content_attributes.get("external_echo") is True
    assert sent == []
    # Delivered twice by Meta: kept once.
    await _post(
        client,
        "smb_message_echoes",
        {
            "messaging_product": "whatsapp",
            "metadata": _metadata(),
            "message_echoes": [
                {
                    "from": BUSINESS,
                    "to": "59899111222",
                    "id": "wamid.echo1",
                    "type": "text",
                    "text": {"body": "Te lo mando hoy"},
                }
            ],
        },
    )
    assert len(await _messages(db_session, inbox)) == 1


async def test_history_lands_quietly_with_its_dates(client, db_session):
    _, inbox = await _coexistence_inbox(db_session, "-coex-hist")
    await _post(
        client,
        "history",
        {
            "messaging_product": "whatsapp",
            "metadata": _metadata(),
            "history": [
                {
                    "metadata": {"phase": 1, "chunk_order": 1, "progress": 100},
                    "threads": [
                        {
                            "id": "59899333444",
                            "messages": [
                                {
                                    "from": BUSINESS,
                                    "id": "wamid.h1",
                                    "timestamp": "1739230955",
                                    "type": "text",
                                    "text": {"body": "Hola, ¿en qué te ayudo?"},
                                    "history_context": {"status": "read"},
                                },
                                {
                                    "from": BUSINESS,
                                    "id": "wamid.h2",
                                    "timestamp": "1739230960",
                                    "type": "media_placeholder",
                                    "history_context": {"status": "read"},
                                },
                                {
                                    "from": "59899333444",
                                    "id": "wamid.h3",
                                    "timestamp": "1739230970",
                                    "type": "text",
                                    "text": {"body": "¿Tienen turnos?"},
                                    "history_context": {"status": "read"},
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    )
    rows = await _messages(db_session, inbox)
    assert [(m.content, m.message_type) for m in rows] == [
        ("Hola, ¿en qué te ayudo?", MESSAGE_TYPE_OUTGOING),
        ("¿Tienen turnos?", MESSAGE_TYPE_INCOMING),
    ]
    assert rows[0].created_at.timestamp() == 1739230955
    conversation = await db_session.get(Conversation, rows[0].conversation_id)
    assert conversation.status == CONVERSATION_STATUS_RESOLVED
    channel = await db_session.get(WhatsappChannel, inbox.channel_id)
    assert channel.provider_config["coexistence_sync"]["history"] == "done"


async def test_declined_history_is_noted(client, db_session):
    _, inbox = await _coexistence_inbox(db_session, "-coex-decl")
    await _post(
        client,
        "history",
        {
            "messaging_product": "whatsapp",
            "metadata": _metadata(),
            "history": [{"errors": [{"code": 2593109, "title": "History sync is turned off"}]}],
        },
    )
    channel = await db_session.get(WhatsappChannel, inbox.channel_id)
    assert channel.provider_config["coexistence_sync"]["history"] == "declined"
    assert await _messages(db_session, inbox) == []


async def test_the_phone_contacts_become_contacts(client, db_session):
    owner, _ = await _coexistence_inbox(db_session, "-coex-contacts")
    await _post(
        client,
        "smb_app_state_sync",
        {
            "messaging_product": "whatsapp",
            "metadata": _metadata(),
            "state_sync": [
                {
                    "type": "contact",
                    "contact": {
                        "full_name": "Pablo Morales",
                        "first_name": "Pablo",
                        "phone_number": "59899555666",
                    },
                    "action": "add",
                    "metadata": {"timestamp": "1738346006"},
                },
                {
                    "type": "contact",
                    "contact": {"phone_number": "59899777888"},
                    "action": "remove",
                    "metadata": {"timestamp": "1738346006"},
                },
            ],
        },
    )
    contacts = (
        await db_session.exec(select(Contact).where(Contact.account_id == owner.account.id))
    ).all()
    assert {(c.phone_number, c.name) for c in contacts} == {("+59899555666", "Pablo Morales")}


async def test_a_disconnected_number_is_marked_until_it_reconnects(client, db_session):
    _, inbox = await _coexistence_inbox(db_session, "-coex-off")
    await _post(
        client,
        "account_update",
        {
            "event": "PARTNER_REMOVED",
            "waba_info": {"waba_id": "waba-x", "owner_business_id": "biz-1"},
            "disconnection_info": {"reason": "PRIMARY_INACTIVITY", "initiated_by": "SYSTEM"},
        },
        entry_id="partner-1",
    )
    channel = await db_session.get(WhatsappChannel, inbox.channel_id)
    await db_session.refresh(channel)
    off = channel.provider_config["coexistence_disconnected"]
    assert off["reason"] == "PRIMARY_INACTIVITY" and off["initiated_by"] == "SYSTEM"

    await _post(client, "account_update", {"event": "ACCOUNT_RECONNECTED"}, entry_id="waba-x")
    await db_session.refresh(channel)
    assert "coexistence_disconnected" not in channel.provider_config
