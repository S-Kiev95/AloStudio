"""Integration tests for the Facebook Messenger inbound processor.

Walks Meta's Messenger payloads through ``process_facebook_webhook``
and asserts the right Contact + ContactInbox + Conversation +
Message rows land. The shared ``create_message`` cascade fires the
post-create hooks so MESSAGE_CREATED reaches the realtime layer.

Anchors:
  reference/chatwoot/app/builders/messages/facebook/message_builder.rb
  reference/chatwoot/app/jobs/webhooks/facebook_events_job.rb
  reference/chatwoot/app/jobs/webhooks/facebook_delivery_job.rb
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import respx
from sqlmodel import select

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.conversations.models import (
    MESSAGE_STATUS_DELIVERED,
    MESSAGE_STATUS_READ,
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
)
from app.domains.facebook import incoming as incoming_module
from app.domains.facebook.incoming import process_facebook_webhook
from app.domains.inboxes.models import (
    FacebookPage,
    Inbox,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram import graph

# Resolve mappers (Conversation.team forward-ref).
from app.domains.teams import models as _teams  # noqa: F401

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------
async def _seed(
    db_session, *, page_id: str = "1234567890", suffix: str = ""
) -> tuple[FacebookPage, Inbox]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@fbi.example.com",
            account_name=f"FBI{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Acme",
            channel_type="facebook",
            channel_params={
                "page_id": page_id,
                "page_access_token": "EAAxxxx-page",
            },
        ),
    ).perform()
    assert isinstance(result.channel, FacebookPage)
    return result.channel, result.inbox


def _msg_payload(
    *,
    page_id: str,
    psid: str,
    mid: str,
    text: str,
    is_echo: bool = False,
) -> dict[str, Any]:
    """Build a canonical Messenger payload with one message event."""
    sender = {"id": page_id if is_echo else psid}
    recipient = {"id": psid if is_echo else page_id}
    message: dict[str, Any] = {"mid": mid, "text": text}
    if is_echo:
        message["is_echo"] = True
    return {
        "object": "page",
        "entry": [
            {
                "id": page_id,
                "time": 1700000000,
                "messaging": [
                    {
                        "sender": sender,
                        "recipient": recipient,
                        "timestamp": 1700000001,
                        "message": message,
                    }
                ],
            }
        ],
    }


def _delivery_payload(
    *, page_id: str, psid: str, mids: list[str], read: bool = False
) -> dict[str, Any]:
    """Build a Messenger delivery / read event payload."""
    block_key = "read" if read else "delivery"
    block: dict[str, Any] = (
        {"watermark": 1700000005} if read else {"mids": mids, "watermark": 1700000005}
    )
    if read:
        block["mids"] = mids
    return {
        "object": "page",
        "entry": [
            {
                "id": page_id,
                "time": 1700000005,
                "messaging": [
                    {
                        "sender": {"id": psid},
                        "recipient": {"id": page_id},
                        "timestamp": 1700000005,
                        block_key: block,
                    }
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Inbound text
# ---------------------------------------------------------------------------
async def test_text_message_creates_contact_and_conversation(db_session):
    channel, _inbox = await _seed(db_session, page_id="P1", suffix="-text")
    payload = _msg_payload(
        page_id="P1", psid="USER_PSID_1", mid="mid-aaa", text="hello there"
    )
    out = await process_facebook_webhook(db_session, payload=payload)
    assert len(out) == 1
    msg = out[0]
    assert msg.message_type == MESSAGE_TYPE_INCOMING
    assert msg.content == "hello there"
    assert msg.source_id == "mid-aaa"

    # Contact + ContactInbox seeded keyed by PSID.
    ci = (
        await db_session.exec(
            select(ContactInbox).where(ContactInbox.source_id == "USER_PSID_1")
        )
    ).first()
    assert ci is not None
    contact = await db_session.get(Contact, ci.contact_id)
    assert contact is not None
    assert contact.account_id == channel.account_id


async def test_unknown_page_drops_silently(db_session):
    """Meta delivers webhooks to every app subscribed to a page;
    foreign pages drop without error."""
    await _seed(db_session, page_id="MINE", suffix="-foreign")
    payload = _msg_payload(
        page_id="OTHER_PAGE", psid="X", mid="m", text="hi"
    )
    out = await process_facebook_webhook(db_session, payload=payload)
    assert out == []


async def test_duplicate_mid_is_idempotent(db_session):
    """Re-delivery of the same mid drops silently (Meta retries on
    5xx; we want 200 to break the loop without double-inserting)."""
    await _seed(db_session, page_id="P2", suffix="-dup")
    payload = _msg_payload(
        page_id="P2", psid="U2", mid="mid-dup", text="hello"
    )
    first = await process_facebook_webhook(db_session, payload=payload)
    second = await process_facebook_webhook(db_session, payload=payload)
    assert len(first) == 1
    assert second == []


async def test_two_messages_share_conversation(db_session):
    """Messenger threads are durable per PSID — two events on the
    same page+PSID land on the same conversation."""
    await _seed(db_session, page_id="P3", suffix="-thread")
    await process_facebook_webhook(
        db_session,
        payload=_msg_payload(
            page_id="P3", psid="U3", mid="m-1", text="hi"
        ),
    )
    await process_facebook_webhook(
        db_session,
        payload=_msg_payload(
            page_id="P3", psid="U3", mid="m-2", text="anybody?"
        ),
    )
    convs = list((await db_session.exec(select(Conversation))).all())
    assert len(convs) == 1


async def test_a_new_contact_gets_the_name_meta_gives(db_session, monkeypatch):
    await _seed(db_session, page_id="PN", suffix="-name")

    async def named(**_kwargs):
        return "Lucía Pérez"

    monkeypatch.setattr(incoming_module, "fetch_contact_name", named)
    await process_facebook_webhook(
        db_session,
        payload=_msg_payload(page_id="PN", psid="U-name-1", mid="n-1", text="hola"),
    )
    contact = (
        await db_session.exec(select(Contact).where(Contact.name == "Lucía Pérez"))
    ).first()
    assert contact is not None


async def test_a_name_someone_set_is_kept(db_session, monkeypatch):
    await _seed(db_session, page_id="PK", suffix="-keep")
    await process_facebook_webhook(
        db_session,
        payload=_msg_payload(page_id="PK", psid="U-keep-1", mid="k-1", text="hola"),
    )
    contact = (
        await db_session.exec(select(Contact).where(Contact.name == "facebook-keep-1"))
    ).first()
    assert contact is not None
    contact.name = "Lucía del CRM"
    db_session.add(contact)
    await db_session.flush()

    async def named(**_kwargs):
        return "Otro nombre"

    monkeypatch.setattr(incoming_module, "fetch_contact_name", named)
    await process_facebook_webhook(
        db_session,
        payload=_msg_payload(page_id="PK", psid="U-keep-1", mid="k-2", text="hola"),
    )
    await db_session.refresh(contact)
    assert contact.name == "Lucía del CRM"


@respx.mock
async def test_a_refused_name_lookup_keeps_the_placeholder():
    respx.get(url__regex=r".*/U-role\?.*").mock(
        return_value=httpx.Response(400, json={"error": {"code": 100}})
    )
    assert (
        await graph.fetch_contact_name(user_id="U-role", access_token="t", fields="name")
        is None
    )


async def test_echo_lands_as_outgoing_with_no_sender(db_session):
    """``message.is_echo`` -> agent replied via FB Messenger app
    (outside Chatwoot). We mirror Rails: stamp as outgoing, no
    sender_id (the dashboard treats this as 'sent from outside')."""
    await _seed(db_session, page_id="P4", suffix="-echo")
    payload = _msg_payload(
        page_id="P4",
        psid="U4",
        mid="echo-1",
        text="from FB app",
        is_echo=True,
    )
    out = await process_facebook_webhook(db_session, payload=payload)
    assert len(out) == 1
    msg = out[0]
    assert msg.message_type == MESSAGE_TYPE_OUTGOING
    assert msg.sender_id is None
    assert msg.source_id == "echo-1"
    assert msg.content_attributes["external_echo"] is True


@respx.mock
async def test_an_echo_is_not_sent_to_the_customer_again(db_session):
    """Another responder on the Page answered: we show it, and never send it."""
    await _seed(db_session, page_id="P4b", suffix="-echo2")
    send = respx.post(url__regex=r".*/me/messages.*|.*/messages.*").mock(
        return_value=httpx.Response(200, json={"message_id": "x"})
    )
    await process_facebook_webhook(
        db_session,
        payload=_msg_payload(
            page_id="P4b", psid="U4b", mid="echo-2", text="auto", is_echo=True
        ),
    )
    assert not send.called


async def test_our_own_echo_is_skipped(db_session, monkeypatch):
    """Our send records its own message; its echo adds nothing."""
    await _seed(db_session, page_id="P4c", suffix="-echo3")
    monkeypatch.setattr(incoming_module, "get_settings", lambda: SimpleNamespace(meta_app_id="APP"))
    payload = _msg_payload(
        page_id="P4c", psid="U4c", mid="echo-3", text="mine", is_echo=True
    )
    payload["entry"][0]["messaging"][0]["message"]["app_id"] = "APP"
    assert await process_facebook_webhook(db_session, payload=payload) == []


# ---------------------------------------------------------------------------
# Delivery / read status events
# ---------------------------------------------------------------------------
async def test_delivery_event_marks_messages_delivered(db_session):
    """A delivery event with ``mids`` -> all matching outbound
    messages flip to ``delivered``."""
    _channel, _inbox = await _seed(db_session, page_id="P5", suffix="-d")
    # Seed an outbound message via the echo path (easiest way to get
    # a Message row with a known source_id).
    await process_facebook_webhook(
        db_session,
        payload=_msg_payload(
            page_id="P5",
            psid="U5",
            mid="out-1",
            text="from agent",
            is_echo=True,
        ),
    )
    msg = (
        await db_session.exec(
            select(Message).where(Message.source_id == "out-1")
        )
    ).first()
    assert msg is not None
    pre_status = msg.status

    out = await process_facebook_webhook(
        db_session,
        payload=_delivery_payload(
            page_id="P5", psid="U5", mids=["out-1"], read=False
        ),
    )
    assert len(out) == 1
    assert out[0].status == MESSAGE_STATUS_DELIVERED
    assert pre_status != MESSAGE_STATUS_DELIVERED


async def test_read_event_marks_messages_read(db_session):
    await _seed(db_session, page_id="P6", suffix="-r")
    await process_facebook_webhook(
        db_session,
        payload=_msg_payload(
            page_id="P6",
            psid="U6",
            mid="out-r",
            text="hi",
            is_echo=True,
        ),
    )
    out = await process_facebook_webhook(
        db_session,
        payload=_delivery_payload(
            page_id="P6", psid="U6", mids=["out-r"], read=True
        ),
    )
    assert len(out) == 1
    assert out[0].status == MESSAGE_STATUS_READ


async def test_status_event_for_unknown_mid_is_noop(db_session):
    await _seed(db_session, page_id="P7", suffix="-mid")
    out = await process_facebook_webhook(
        db_session,
        payload=_delivery_payload(
            page_id="P7", psid="U7", mids=["never-seen"], read=False
        ),
    )
    assert out == []


# ---------------------------------------------------------------------------
# Malformed payloads
# ---------------------------------------------------------------------------
async def test_non_page_payload_returns_empty(db_session):
    """Meta also delivers ``object: instagram`` webhooks if the IG
    handler is wired separately. We only handle ``object: page`` here."""
    out = await process_facebook_webhook(
        db_session,
        payload={"object": "instagram", "entry": []},
    )
    assert out == []


async def test_empty_payload_returns_empty(db_session):
    assert (
        await process_facebook_webhook(db_session, payload={})
    ) == []
