"""Integration tests for the Instagram inbound processor.

Walks Meta's IG webhook payloads through ``process_instagram_webhook``
and asserts the right Contact + ContactInbox + Conversation +
Message rows land. Echo handling + read-event status updates are
covered alongside the canonical text-message path.

Anchors:
  reference/chatwoot/app/jobs/webhooks/instagram_events_job.rb
  reference/chatwoot/app/builders/messages/instagram/message_builder.rb
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlmodel import select

from app.core.storage import object_url
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.conversations.models import (
    MESSAGE_STATUS_READ,
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Attachment,
    Conversation,
)
from app.domains.inboxes.models import (
    Inbox,
    InstagramChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram.incoming import (
    UNSENT_CONTENT,
    process_instagram_webhook,
)
from app.domains.teams import models as _teams  # noqa: F401  (mapper)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------
async def _seed(
    db_session,
    *,
    instagram_id: str = "17841405822304914",
    suffix: str = "",
) -> tuple[InstagramChannel, Inbox]:
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@igi.example.com",
            account_name=f"IGI{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Acme IG",
            channel_type="instagram",
            channel_params={
                "instagram_id": instagram_id,
                "access_token": "EAAxxxx-ig",
                "expires_at": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
            },
        ),
    ).perform()
    assert isinstance(result.channel, InstagramChannel)
    return result.channel, result.inbox


def _msg_payload(
    *,
    instagram_id: str,
    igsid: str,
    mid: str,
    text: str,
    is_echo: bool = False,
) -> dict[str, Any]:
    sender = {"id": instagram_id if is_echo else igsid}
    recipient = {"id": igsid if is_echo else instagram_id}
    message: dict[str, Any] = {"mid": mid, "text": text}
    if is_echo:
        message["is_echo"] = True
    return {
        "object": "instagram",
        "entry": [
            {
                "id": instagram_id,
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


def _read_payload(
    *, instagram_id: str, igsid: str, mid: str
) -> dict[str, Any]:
    return {
        "object": "instagram",
        "entry": [
            {
                "id": instagram_id,
                "time": 1700000005,
                "messaging": [
                    {
                        "sender": {"id": igsid},
                        "recipient": {"id": instagram_id},
                        "timestamp": 1700000005,
                        "read": {"mid": mid, "watermark": 1700000005},
                    }
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Inbound text
# ---------------------------------------------------------------------------
async def test_text_creates_contact_and_conversation(db_session):
    channel, _inbox = await _seed(
        db_session, instagram_id="IG-1", suffix="-text"
    )
    out = await process_instagram_webhook(
        db_session,
        payload=_msg_payload(
            instagram_id="IG-1",
            igsid="IGSID-AAA",
            mid="ig.mid.1",
            text="hi from IG",
        ),
    )
    assert len(out) == 1
    msg = out[0]
    assert msg.message_type == MESSAGE_TYPE_INCOMING
    assert msg.content == "hi from IG"
    assert msg.source_id == "ig.mid.1"

    ci = (
        await db_session.exec(
            select(ContactInbox).where(ContactInbox.source_id == "IGSID-AAA")
        )
    ).first()
    assert ci is not None
    contact = await db_session.get(Contact, ci.contact_id)
    assert contact is not None
    assert contact.account_id == channel.account_id


async def test_unknown_instagram_id_drops_silently(db_session):
    await _seed(db_session, instagram_id="MINE", suffix="-foreign")
    out = await process_instagram_webhook(
        db_session,
        payload=_msg_payload(
            instagram_id="OTHER", igsid="X", mid="m", text="hi"
        ),
    )
    assert out == []


async def test_duplicate_mid_is_idempotent(db_session):
    await _seed(db_session, instagram_id="IG-2", suffix="-dup")
    payload = _msg_payload(
        instagram_id="IG-2", igsid="IGSID-DUP", mid="ig.dup", text="once"
    )
    first = await process_instagram_webhook(db_session, payload=payload)
    second = await process_instagram_webhook(db_session, payload=payload)
    assert len(first) == 1
    assert second == []


async def test_echo_lands_as_outgoing_with_no_sender(db_session):
    await _seed(db_session, instagram_id="IG-3", suffix="-echo")
    payload = _msg_payload(
        instagram_id="IG-3",
        igsid="IGSID-ECHO",
        mid="ig.echo.1",
        text="from IG app",
        is_echo=True,
    )
    out = await process_instagram_webhook(db_session, payload=payload)
    assert len(out) == 1
    assert out[0].message_type == MESSAGE_TYPE_OUTGOING
    assert out[0].sender_id is None


async def test_two_messages_share_conversation(db_session):
    """IG threads are durable per-IGSID — second event lands on the
    same conversation."""
    await _seed(db_session, instagram_id="IG-4", suffix="-thread")
    await process_instagram_webhook(
        db_session,
        payload=_msg_payload(
            instagram_id="IG-4", igsid="IGSID-T", mid="m-1", text="hi"
        ),
    )
    await process_instagram_webhook(
        db_session,
        payload=_msg_payload(
            instagram_id="IG-4", igsid="IGSID-T", mid="m-2", text="anybody?"
        ),
    )
    convs = list((await db_session.exec(select(Conversation))).all())
    assert len(convs) == 1


# ---------------------------------------------------------------------------
# Read events
# ---------------------------------------------------------------------------
async def test_read_event_marks_message_as_read(db_session):
    await _seed(db_session, instagram_id="IG-5", suffix="-read")
    # Seed an outbound via echo path so we have a Message row with a
    # known source_id.
    await process_instagram_webhook(
        db_session,
        payload=_msg_payload(
            instagram_id="IG-5",
            igsid="IGSID-R",
            mid="ig.out.read",
            text="hi",
            is_echo=True,
        ),
    )
    out = await process_instagram_webhook(
        db_session,
        payload=_read_payload(
            instagram_id="IG-5", igsid="IGSID-R", mid="ig.out.read"
        ),
    )
    assert len(out) == 1
    assert out[0].status == MESSAGE_STATUS_READ


async def test_read_event_for_unknown_mid_is_noop(db_session):
    await _seed(db_session, instagram_id="IG-6", suffix="-mid")
    out = await process_instagram_webhook(
        db_session,
        payload=_read_payload(
            instagram_id="IG-6", igsid="IGSID-X", mid="never-seen"
        ),
    )
    assert out == []


# ---------------------------------------------------------------------------
# Malformed payloads
# ---------------------------------------------------------------------------
def _unsent_payload(*, instagram_id: str, igsid: str, mid: str) -> dict[str, Any]:
    payload = _msg_payload(instagram_id=instagram_id, igsid=igsid, mid=mid, text="")
    payload["entry"][0]["messaging"][0]["message"] = {"mid": mid, "is_deleted": True}
    return payload


async def test_unsent_message_loses_its_text(db_session):
    await _seed(db_session, instagram_id="IG-U1", suffix="-unsent1")
    created = await process_instagram_webhook(
        db_session,
        payload=_msg_payload(
            instagram_id="IG-U1", igsid="IGSID-U1", mid="ig.u1", text="Mi telefono"
        ),
    )

    out = await process_instagram_webhook(
        db_session,
        payload=_unsent_payload(instagram_id="IG-U1", igsid="IGSID-U1", mid="ig.u1"),
    )

    assert [m.id for m in out] == [created[0].id]
    assert out[0].content == UNSENT_CONTENT
    assert out[0].content_attributes["deleted"] is True


async def test_unsent_message_removes_its_files(db_session, monkeypatch):
    removed: list[str] = []

    async def _record(key: str) -> None:
        removed.append(key)

    monkeypatch.setattr("app.domains.instagram.media.delete_object", _record)
    await _seed(db_session, instagram_id="IG-U2", suffix="-unsent2")
    created = await process_instagram_webhook(
        db_session,
        payload=_msg_payload(
            instagram_id="IG-U2", igsid="IGSID-U2", mid="ig.u2", text="Foto"
        ),
    )
    msg = created[0]
    for url in (object_url("accounts/1/instagram/abc.jpg"), "https://example.com/a"):
        db_session.add(
            Attachment(
                account_id=msg.account_id,
                message_id=msg.id,
                file_type=0,
                external_url=url,
            )
        )
    await db_session.flush()

    await process_instagram_webhook(
        db_session,
        payload=_unsent_payload(instagram_id="IG-U2", igsid="IGSID-U2", mid="ig.u2"),
    )

    left = await db_session.exec(
        select(Attachment).where(Attachment.message_id == msg.id)
    )
    assert left.all() == []
    assert removed == ["accounts/1/instagram/abc.jpg"]


async def test_unsent_unknown_message_creates_nothing(db_session):
    await _seed(db_session, instagram_id="IG-U3", suffix="-unsent3")

    out = await process_instagram_webhook(
        db_session,
        payload=_unsent_payload(instagram_id="IG-U3", igsid="IGSID-U3", mid="ig.u3"),
    )

    assert out == []
    contacts = await db_session.exec(
        select(ContactInbox).where(ContactInbox.source_id == "IGSID-U3")
    )
    assert contacts.all() == []


async def test_non_instagram_object_returns_empty(db_session):
    out = await process_instagram_webhook(
        db_session,
        payload={"object": "page", "entry": []},
    )
    assert out == []


async def test_empty_payload_returns_empty(db_session):
    assert (
        await process_instagram_webhook(db_session, payload={})
    ) == []
