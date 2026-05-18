"""Integration tests for the Phase 10 scheduler.

Tests run the two task functions directly against a real session.
The ARQ wrapper (``tick_5min``) is exercised in passing via the
function it calls.

Anchors:
  reference/chatwoot/app/jobs/trigger_scheduled_items_job.rb
  reference/chatwoot/app/jobs/campaigns/trigger_oneoff_campaign_job.rb
  reference/chatwoot/app/jobs/conversations/reopen_snoozed_conversations_job.rb
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.campaigns.models import (
    CAMPAIGN_STATUS_ACTIVE,
    CAMPAIGN_STATUS_COMPLETED,
    CAMPAIGN_TYPE_ONE_OFF,
    CAMPAIGN_TYPE_ONGOING,
    Campaign,
)
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    CONVERSATION_STATUS_OPEN,
    CONVERSATION_STATUS_SNOOZED,
    Conversation,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
    toggle_status,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.workers.scheduler import (
    fire_due_oneoff_campaigns,
    reopen_snoozed_conversations,
)

pytestmark = pytest.mark.integration


async def _seed_account(db_session, suffix: str):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@sch.example.com",
            account_name=f"SCH{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


async def _seed_inbox(db_session, owner):
    return (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="API",
                channel_type="api",
                channel_params={"webhook_url": "https://x.example.com"},
            ),
        ).perform()
    ).inbox


def _make_campaign(
    owner,
    inbox,
    *,
    campaign_type: int = CAMPAIGN_TYPE_ONE_OFF,
    status: int = CAMPAIGN_STATUS_ACTIVE,
    scheduled_at: datetime | None = None,
    display_id: int = 1,
) -> Campaign:
    return Campaign(
        display_id=display_id,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        title="Test",
        message="Hi",
        campaign_type=campaign_type,
        campaign_status=status,
        scheduled_at=scheduled_at,
    )


# ---------------------------------------------------------------------------
# Campaign scheduler
# ---------------------------------------------------------------------------
async def test_fires_oneoff_due_in_window(db_session):
    owner = await _seed_account(db_session, "-fc")
    inbox = await _seed_inbox(db_session, owner)
    one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    c = _make_campaign(owner, inbox, scheduled_at=one_hour_ago)
    db_session.add(c)
    await db_session.flush()
    await db_session.refresh(c)

    fired = await fire_due_oneoff_campaigns(db_session)
    assert fired == 1
    await db_session.refresh(c)
    assert c.campaign_status == CAMPAIGN_STATUS_COMPLETED


async def test_does_not_fire_future_oneoff(db_session):
    owner = await _seed_account(db_session, "-fu")
    inbox = await _seed_inbox(db_session, owner)
    in_an_hour = datetime.now(UTC) + timedelta(hours=1)
    c = _make_campaign(owner, inbox, scheduled_at=in_an_hour)
    db_session.add(c)
    await db_session.flush()

    fired = await fire_due_oneoff_campaigns(db_session)
    assert fired == 0
    await db_session.refresh(c)
    assert c.campaign_status == CAMPAIGN_STATUS_ACTIVE


async def test_does_not_fire_stale_oneoff(db_session):
    """Anything older than the 3-day window stays alone — Chatwoot
    intentionally lets ancient campaigns expire."""
    owner = await _seed_account(db_session, "-st")
    inbox = await _seed_inbox(db_session, owner)
    five_days_ago = datetime.now(UTC) - timedelta(days=5)
    c = _make_campaign(owner, inbox, scheduled_at=five_days_ago)
    db_session.add(c)
    await db_session.flush()

    fired = await fire_due_oneoff_campaigns(db_session)
    assert fired == 0
    await db_session.refresh(c)
    assert c.campaign_status == CAMPAIGN_STATUS_ACTIVE


async def test_does_not_fire_ongoing_campaigns(db_session):
    """Ongoing campaigns never get touched by the scheduler — they
    fire via the widget trigger pipeline instead."""
    owner = await _seed_account(db_session, "-og")
    inbox = await _seed_inbox(db_session, owner)
    c = _make_campaign(
        owner,
        inbox,
        campaign_type=CAMPAIGN_TYPE_ONGOING,
        scheduled_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(c)
    await db_session.flush()

    fired = await fire_due_oneoff_campaigns(db_session)
    assert fired == 0
    await db_session.refresh(c)
    assert c.campaign_status == CAMPAIGN_STATUS_ACTIVE


async def test_does_not_refire_completed_oneoff(db_session):
    owner = await _seed_account(db_session, "-cmp")
    inbox = await _seed_inbox(db_session, owner)
    c = _make_campaign(
        owner,
        inbox,
        status=CAMPAIGN_STATUS_COMPLETED,
        scheduled_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(c)
    await db_session.flush()

    fired = await fire_due_oneoff_campaigns(db_session)
    assert fired == 0


# ---------------------------------------------------------------------------
# Snoozed conversation reopen
# ---------------------------------------------------------------------------
async def test_reopens_due_snoozed_conversation(db_session):
    owner = await _seed_account(db_session, "-sn")
    inbox = await _seed_inbox(db_session, owner)
    contact = Contact(account_id=owner.account.id, name="X")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    # Snooze with a past timestamp.
    await toggle_status(
        db_session,
        conversation=conv,
        status="snoozed",
        snoozed_until=datetime.now(UTC) - timedelta(minutes=10),
    )
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    assert fresh.status == CONVERSATION_STATUS_SNOOZED

    reopened = await reopen_snoozed_conversations(db_session)
    assert reopened == 1

    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    assert fresh.status == CONVERSATION_STATUS_OPEN


async def test_does_not_reopen_future_snooze(db_session):
    owner = await _seed_account(db_session, "-fs")
    inbox = await _seed_inbox(db_session, owner)
    contact = Contact(account_id=owner.account.id, name="X")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    await toggle_status(
        db_session,
        conversation=conv,
        status="snoozed",
        snoozed_until=datetime.now(UTC) + timedelta(hours=2),
    )

    reopened = await reopen_snoozed_conversations(db_session)
    assert reopened == 0
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    assert fresh.status == CONVERSATION_STATUS_SNOOZED


async def test_does_not_touch_open_conversations(db_session):
    owner = await _seed_account(db_session, "-op")
    inbox = await _seed_inbox(db_session, owner)
    contact = Contact(account_id=owner.account.id, name="X")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    # Conversation defaults to open; no reopen action.
    reopened = await reopen_snoozed_conversations(db_session)
    assert reopened == 0
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    assert fresh.status == CONVERSATION_STATUS_OPEN
