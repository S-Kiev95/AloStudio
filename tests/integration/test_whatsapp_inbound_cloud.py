"""Integration tests for the WhatsApp Cloud webhook processor.

Walks Meta webhook payloads through :func:`process_cloud_webhook`
and asserts the right Contact + ContactInbox + Conversation +
Message rows land. The shared :func:`create_message` cascade fires
the same post-create hooks as agent-side flows (last_activity_at
bump, MESSAGE_CREATED dispatch).

Anchors:
  reference/chatwoot/app/services/whatsapp/incoming_message_whatsapp_cloud_service.rb
  reference/chatwoot/app/services/whatsapp/incoming_message_base_service.rb
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlmodel import select

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.conversations.models import (
    MESSAGE_STATUS_FAILED,
    MESSAGE_STATUS_READ,
    MESSAGE_TYPE_INCOMING,
    Conversation,
    Message,
)
from app.domains.inboxes.models import (
    WHATSAPP_PROVIDER_CLOUD,
    Inbox,
    WhatsappChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams

# Resolve mappers (Conversation.team forward-ref) before first DB op.
from app.domains.teams import models as _teams  # noqa: F401
from app.domains.whatsapp.incoming_cloud import process_cloud_webhook

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------
async def _seed_inbox(
    db_session, *, phone_number: str = "+15558881212", suffix: str = ""
) -> tuple[WhatsappChannel, Inbox]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@wac.example.com",
            account_name=f"WAC{suffix}",
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
                "phone_number": phone_number,
                "provider": WHATSAPP_PROVIDER_CLOUD,
                "provider_config": {
                    "api_key": "EAAxxxx",
                    "phone_number_id": "p1",
                    "business_account_id": "b1",
                },
            },
        ),
    ).perform()
    assert isinstance(result.channel, WhatsappChannel)
    return result.channel, result.inbox


def _text_message_payload(
    *,
    from_phone: str,
    wamid: str,
    body: str,
    profile_name: str | None = None,
    timestamp: str = "1700000000",
) -> dict[str, Any]:
    """Build a Cloud-shaped webhook with one text message."""
    contacts: list[dict[str, Any]] = []
    if profile_name:
        contacts.append({
            "profile": {"name": profile_name},
            "wa_id": from_phone,
        })
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "biz-id",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "+15551112233"},
                            "contacts": contacts,
                            "messages": [
                                {
                                    "from": from_phone,
                                    "id": wamid,
                                    "timestamp": timestamp,
                                    "type": "text",
                                    "text": {"body": body},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _status_payload(
    *, wamid: str, status: str, errors: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": wamid,
        "status": status,
        "timestamp": "1700000000",
        "recipient_id": "5557654321",
    }
    if errors:
        body["errors"] = errors
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "biz-id",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "+15551112233"},
                            "statuses": [body],
                        },
                    }
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Text-message ingest
# ---------------------------------------------------------------------------
async def test_text_message_creates_contact_conversation_and_message(
    db_session,
):
    channel, inbox = await _seed_inbox(db_session, suffix="-text")
    payload = _text_message_payload(
        from_phone="5551234567",
        wamid="wamid.aaa",
        body="hi there",
        profile_name="Diana",
    )
    out = await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=payload
    )
    assert len(out) == 1
    msg = out[0]
    assert msg.message_type == MESSAGE_TYPE_INCOMING
    assert msg.content == "hi there"
    assert msg.source_id == "wamid.aaa"

    contact = (
        await db_session.exec(
            select(Contact).where(Contact.phone_number == "+5551234567")
        )
    ).first()
    assert contact is not None
    assert contact.name == "Diana"

    # ContactInbox keyed by phone.
    ci = (
        await db_session.exec(
            select(ContactInbox).where(
                ContactInbox.contact_id == contact.id,
                ContactInbox.inbox_id == inbox.id,
            )
        )
    ).first()
    assert ci is not None
    assert ci.source_id == "+5551234567"


async def test_duplicate_wamid_is_idempotent(db_session):
    channel, inbox = await _seed_inbox(db_session, suffix="-dup")
    payload = _text_message_payload(
        from_phone="5552223344", wamid="wamid.dup", body="once"
    )
    first = await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=payload
    )
    second = await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=payload
    )
    assert len(first) == 1
    assert second == []
    rows = list(
        (
            await db_session.exec(
                select(Message).where(Message.source_id == "wamid.dup")
            )
        ).all()
    )
    assert len(rows) == 1


async def test_unprocessable_message_types_are_dropped(db_session):
    channel, inbox = await _seed_inbox(db_session, suffix="-react")
    # Reaction + ephemeral types: Chatwoot drops these at the front of
    # the processor.
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "biz",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "from": "5553334455",
                                    "id": "wamid.react",
                                    "type": "reaction",
                                    "reaction": {"emoji": "👍", "message_id": "wamid.aaa"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    out = await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=payload
    )
    assert out == []


async def test_button_reply_uses_button_title(db_session):
    """``button`` payload — Meta's interactive-button replies. Body
    text should be the button title."""
    channel, inbox = await _seed_inbox(db_session, suffix="-button")
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "biz",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "from": "5554445566",
                                    "id": "wamid.btn",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {
                                            "id": "btn-1",
                                            "title": "Yes please",
                                        },
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    out = await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=payload
    )
    assert len(out) == 1
    assert out[0].content == "Yes please"


async def test_two_messages_from_same_sender_share_conversation(db_session):
    """A second incoming from a familiar phone reuses the existing
    Conversation rather than minting a new one."""
    channel, inbox = await _seed_inbox(db_session, suffix="-share")
    await process_cloud_webhook(
        db_session,
        channel=channel,
        inbox=inbox,
        payload=_text_message_payload(
            from_phone="5557778899", wamid="wamid.s1", body="hello"
        ),
    )
    await process_cloud_webhook(
        db_session,
        channel=channel,
        inbox=inbox,
        payload=_text_message_payload(
            from_phone="5557778899", wamid="wamid.s2", body="anybody?"
        ),
    )
    convs = list(
        (await db_session.exec(select(Conversation))).all()
    )
    assert len(convs) == 1


# ---------------------------------------------------------------------------
# Status events
# ---------------------------------------------------------------------------
async def test_status_event_updates_message_status(db_session):
    """Send a message via the inbound path (which assigns a WAMID via
    ``source_id``) then deliver a ``status: read`` event to update it."""
    channel, inbox = await _seed_inbox(db_session, suffix="-status")
    # Seed: simulate an outbound message we sent that Meta echoed
    # back. Easiest: insert a Message row directly with a known WAMID.
    await process_cloud_webhook(
        db_session,
        channel=channel,
        inbox=inbox,
        payload=_text_message_payload(
            from_phone="5550000111", wamid="wamid.outbound", body="hi"
        ),
    )

    out = await process_cloud_webhook(
        db_session,
        channel=channel,
        inbox=inbox,
        payload=_status_payload(wamid="wamid.outbound", status="read"),
    )
    assert len(out) == 1
    msg = out[0]
    assert msg.status == MESSAGE_STATUS_READ


async def test_status_failed_stashes_error(db_session):
    channel, inbox = await _seed_inbox(db_session, suffix="-fail")
    await process_cloud_webhook(
        db_session,
        channel=channel,
        inbox=inbox,
        payload=_text_message_payload(
            from_phone="5550000222", wamid="wamid.fail", body="hi"
        ),
    )
    out = await process_cloud_webhook(
        db_session,
        channel=channel,
        inbox=inbox,
        payload=_status_payload(
            wamid="wamid.fail",
            status="failed",
            errors=[{"code": 131_014, "title": "(#131014) Message Failed"}],
        ),
    )
    assert len(out) == 1
    msg = out[0]
    assert msg.status == MESSAGE_STATUS_FAILED
    err = (msg.content_attributes or {}).get("external_error", "")
    assert "131014" in err


async def test_status_event_for_unknown_message_is_noop(db_session):
    channel, inbox = await _seed_inbox(db_session, suffix="-unknown")
    out = await process_cloud_webhook(
        db_session,
        channel=channel,
        inbox=inbox,
        payload=_status_payload(wamid="wamid.never-seen", status="sent"),
    )
    assert out == []


# ---------------------------------------------------------------------------
# Malformed payloads
# ---------------------------------------------------------------------------
async def test_empty_payload_returns_empty(db_session):
    channel, inbox = await _seed_inbox(db_session, suffix="-empty")
    assert await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload={}
    ) == []
    assert await process_cloud_webhook(
        db_session,
        channel=channel,
        inbox=inbox,
        payload={"entry": []},
    ) == []
