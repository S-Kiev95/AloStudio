"""Integration tests for the ReportingEventListener.

The listener writes a :class:`ReportingEvent` row on the four
dispatcher events the v4.13.0 dashboards consume. Each test seeds a
conversation/message, performs the triggering action, and asserts the
event was emitted with the right ``name`` + ``value`` shape.

Anchors:
  reference/chatwoot/app/listeners/reporting_event_listener.rb
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    Conversation,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
    toggle_status,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.reporting.models import ReportingEvent
from app.domains.teams import models as _teams  # noqa: F401  (mapper)

pytestmark = pytest.mark.integration


async def _seed_account(db_session, suffix: str):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@rep.example.com",
            account_name=f"Rep{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


async def _seed_conversation(db_session, owner) -> Conversation:
    inbox = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API",
            channel_type="api",
            channel_params={"webhook_url": "https://x.example.com"},
        ),
    ).perform()
    contact = Contact(account_id=owner.account.id, name="X")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox.inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    return await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )


async def _events_for(
    db_session, conv: Conversation, name: str | None = None
) -> list[ReportingEvent]:
    stmt = select(ReportingEvent).where(
        ReportingEvent.conversation_id == conv.id
    )
    if name is not None:
        stmt = stmt.where(ReportingEvent.name == name)
    stmt = stmt.order_by(ReportingEvent.id.asc())  # type: ignore[attr-defined]
    return list((await db_session.exec(stmt)).all())


# ---------------------------------------------------------------------------
# conversation_resolved
# ---------------------------------------------------------------------------
async def test_resolve_emits_conversation_resolved_event(db_session):
    owner = await _seed_account(db_session, "-res")
    conv = await _seed_conversation(db_session, owner)
    # Backdate ``created_at`` so the value is non-zero.
    conv.created_at = datetime.now(UTC) - timedelta(seconds=60)
    db_session.add(conv)
    await db_session.flush()

    await toggle_status(db_session, conversation=conv, status="resolved")

    events = await _events_for(db_session, conv, name="conversation_resolved")
    assert len(events) == 1
    event = events[0]
    assert event.account_id == owner.account.id
    assert event.inbox_id == conv.inbox_id
    assert event.value >= 60.0
    # value_in_business_hours falls back to value (no working_hours yet).
    assert event.value_in_business_hours == event.value
    assert event.event_start_time == conv.created_at
    assert event.event_end_time is not None


async def test_resolve_emits_user_id_when_assigned(db_session):
    owner = await _seed_account(db_session, "-ass")
    conv = await _seed_conversation(db_session, owner)
    conv.assignee_id = owner.user.id
    db_session.add(conv)
    await db_session.flush()

    await toggle_status(db_session, conversation=conv, status="resolved")
    events = await _events_for(db_session, conv, name="conversation_resolved")
    assert len(events) == 1
    assert events[0].user_id == owner.user.id


# ---------------------------------------------------------------------------
# conversation_opened — first-time vs reopen
# ---------------------------------------------------------------------------
async def test_first_open_emits_zero_value(db_session):
    """Re-opening a never-resolved conversation (toggle_status into
    open from pending) emits a 0-valued conversation_opened event."""
    owner = await _seed_account(db_session, "-fo")
    conv = await _seed_conversation(db_session, owner)
    # Drop the conversation back into pending to set the stage for an
    # ``open`` transition.
    await toggle_status(db_session, conversation=conv, status="pending")
    # Now flip to open.
    await toggle_status(db_session, conversation=conv, status="open")
    events = await _events_for(db_session, conv, name="conversation_opened")
    assert len(events) == 1
    assert events[0].value == 0.0


async def test_reopen_emits_time_since_resolve(db_session):
    owner = await _seed_account(db_session, "-ro")
    conv = await _seed_conversation(db_session, owner)
    await toggle_status(db_session, conversation=conv, status="resolved")
    # Backdate the resolved event so the reopen value is non-zero.
    resolved = (
        await _events_for(db_session, conv, name="conversation_resolved")
    )[0]
    resolved.event_end_time = datetime.now(UTC) - timedelta(seconds=120)
    db_session.add(resolved)
    await db_session.flush()
    await toggle_status(db_session, conversation=conv, status="open")
    opened = await _events_for(db_session, conv, name="conversation_opened")
    assert len(opened) == 1
    assert opened[0].value >= 120.0


# ---------------------------------------------------------------------------
# first_response
# ---------------------------------------------------------------------------
async def test_first_agent_reply_emits_first_response_event(db_session):
    owner = await _seed_account(db_session, "-fr")
    conv = await _seed_conversation(db_session, owner)
    # Backdate conversation so first_response has a meaningful baseline.
    conv.created_at = datetime.now(UTC) - timedelta(seconds=45)
    conv.waiting_since = conv.created_at
    db_session.add(conv)
    await db_session.flush()
    # Incoming contact message — does not fire first_response.
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="hi there",
            message_type="incoming",
        ),
        user_id=None,
    )
    # Agent reply — fires first_reply_created → ReportingEvent.
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="hello, how can I help?",
            message_type="outgoing",
        ),
        user_id=owner.user.id,
    )
    events = await _events_for(db_session, conv, name="first_response")
    assert len(events) == 1
    assert events[0].user_id == owner.user.id
    # Value should be roughly 45 seconds (give a tolerance for flakiness).
    assert events[0].value >= 45.0


# ---------------------------------------------------------------------------
# reply_time
# ---------------------------------------------------------------------------
async def test_subsequent_agent_reply_emits_reply_time_event(db_session):
    """The second agent reply (after a contact message) fires
    ``reply.created`` with waiting_since, producing a ``reply_time`` row."""
    owner = await _seed_account(db_session, "-rt")
    conv = await _seed_conversation(db_session, owner)
    conv.created_at = datetime.now(UTC) - timedelta(seconds=10)
    conv.waiting_since = conv.created_at
    db_session.add(conv)
    await db_session.flush()

    # First agent reply consumes the first_response event.
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="hello",
            message_type="outgoing",
        ),
        user_id=owner.user.id,
    )
    # Contact follow-up sets waiting_since.
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="thanks",
            message_type="incoming",
        ),
        user_id=None,
    )
    # Backdate waiting_since to ensure a non-zero reply_time value.
    await db_session.refresh(conv)
    conv.waiting_since = datetime.now(UTC) - timedelta(seconds=30)
    db_session.add(conv)
    await db_session.flush()
    # Second agent reply fires reply.created with the waiting_since payload.
    await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="here you go",
            message_type="outgoing",
        ),
        user_id=owner.user.id,
    )
    events = await _events_for(db_session, conv, name="reply_time")
    assert len(events) == 1
    assert events[0].value >= 30.0


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------
async def test_unrelated_events_do_not_emit(db_session):
    """Status changes that are not in the parity-critical four do not
    produce ReportingEvent rows."""
    owner = await _seed_account(db_session, "-iso")
    conv = await _seed_conversation(db_session, owner)
    # snoozed status — no reporting event.
    await toggle_status(
        db_session,
        conversation=conv,
        status="snoozed",
        snoozed_until=datetime.now(UTC) + timedelta(hours=1),
    )
    events = await _events_for(db_session, conv)
    assert events == []
