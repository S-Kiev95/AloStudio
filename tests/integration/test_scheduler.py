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
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
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


async def test_oneoff_delivers_to_audience(db_session):
    owner = await _seed_account(db_session, "-aud")
    inbox = await _seed_inbox(db_session, owner)
    c1 = Contact(account_id=owner.account.id, name="A", email="a@aud.example.com")
    c2 = Contact(account_id=owner.account.id, name="B", email="b@aud.example.com")
    db_session.add(c1)
    db_session.add(c2)
    await db_session.flush()

    campaign = _make_campaign(
        owner, inbox, scheduled_at=datetime.now(UTC) - timedelta(hours=1)
    )
    campaign.audience = [
        {"type": "Contact", "id": c1.id},
        {"type": "Contact", "id": c2.id},
    ]
    db_session.add(campaign)
    await db_session.flush()

    fired = await fire_due_oneoff_campaigns(db_session)
    assert fired == 1

    # One conversation per audience contact, each stamped with campaign_id
    # and carrying the campaign body as an outgoing message.
    convs = list(
        (
            await db_session.exec(
                select(Conversation).where(
                    Conversation.campaign_id == campaign.id
                )
            )
        ).all()
    )
    assert len(convs) == 2
    for conv in convs:
        msgs = list(
            (
                await db_session.exec(
                    select(Message).where(Message.conversation_id == conv.id)
                )
            ).all()
        )
        assert any(
            m.content == "Hi" and m.message_type == MESSAGE_TYPE_OUTGOING
            for m in msgs
        )


async def test_oneoff_reaches_existing_conversation_once(db_session):
    """A mass send goes to contacts who already talked to the business:
    into their latest conversation, and only once per campaign."""
    owner = await _seed_account(db_session, "-skip")
    inbox = await _seed_inbox(db_session, owner)
    contact = Contact(
        account_id=owner.account.id, name="Ana Pérez", email="a@skip.example.com"
    )
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    existing = await create_conversation(
        db_session, contact_inbox=ci, params=ConversationBuilderParams()
    )

    campaign = _make_campaign(
        owner, inbox, scheduled_at=datetime.now(UTC) - timedelta(hours=1)
    )
    campaign.message = "Hola {primer_nombre}"
    campaign.template_params = {
        "name": "promo",
        "language": "es",
        "processed_params": {"body": {"1": "{nombre}"}},
    }
    campaign.audience = [{"type": "Contact", "id": contact.id}]
    db_session.add(campaign)
    await db_session.flush()

    assert await fire_due_oneoff_campaigns(db_session) == 1
    msgs = list(
        (
            await db_session.exec(
                select(Message).where(
                    Message.conversation_id == existing.id,
                    Message.message_type == MESSAGE_TYPE_OUTGOING,
                )
            )
        ).all()
    )
    assert [m.content for m in msgs] == ["Hola Ana"]
    tpl = (msgs[0].additional_attributes or {}).get("template_params") or {}
    assert tpl.get("processed_params", {}).get("body", {}).get("1") == "Ana Pérez"

    # A second run (the campaign re-armed) doesn't message her again.
    campaign.campaign_status = CAMPAIGN_STATUS_ACTIVE
    db_session.add(campaign)
    await db_session.flush()
    await fire_due_oneoff_campaigns(db_session)
    again = (
        await db_session.exec(
            select(Message).where(
                Message.conversation_id == existing.id,
                Message.message_type == MESSAGE_TYPE_OUTGOING,
            )
        )
    ).all()
    assert len(list(again)) == 1


async def test_oneoff_label_and_inbox_audiences(db_session):
    """``Label`` reaches contacts whose conversations carry the label;
    ``Inbox`` reaches every contact of the campaign's inbox."""
    from app.domains.campaigns.service import (
        campaign_recipients,
        resolve_audience_contact_ids,
    )
    from app.domains.labels.models import Label

    owner = await _seed_account(db_session, "-lbl")
    inbox = await _seed_inbox(db_session, owner)
    label = Label(account_id=owner.account.id, title="alumnos")
    db_session.add(label)
    tagged = Contact(account_id=owner.account.id, name="Tag", email="t@lbl.example.com")
    other = Contact(account_id=owner.account.id, name="Otro", email="o@lbl.example.com")
    db_session.add(tagged)
    db_session.add(other)
    await db_session.flush()
    convs = {}
    for c in (tagged, other):
        ci = await ContactInboxBuilder(
            session=db_session, contact=c, inbox=inbox, source_id=f"src-{c.id}"
        ).perform()
        convs[c.id] = await create_conversation(
            db_session, contact_inbox=ci, params=ConversationBuilderParams()
        )
    convs[tagged.id].cached_label_list = "alumnos,vip"
    convs[other.id].cached_label_list = "alumnos-viejos"
    db_session.add(convs[tagged.id])
    db_session.add(convs[other.id])
    await db_session.flush()

    campaign = _make_campaign(
        owner, inbox, scheduled_at=datetime.now(UTC) - timedelta(hours=1)
    )
    campaign.audience = [{"type": "Label", "id": label.id}]
    db_session.add(campaign)
    await db_session.flush()
    assert await resolve_audience_contact_ids(db_session, campaign=campaign) == [tagged.id]

    campaign.audience = [{"type": "Inbox"}, {"type": "Contact", "id": tagged.id}]
    assert sorted(await resolve_audience_contact_ids(db_session, campaign=campaign)) == sorted(
        [tagged.id, other.id]
    )

    campaign.audience = [{"type": "Label", "id": label.id}]
    await fire_due_oneoff_campaigns(db_session)
    rows = await campaign_recipients(db_session, campaign=campaign)
    assert [(r["name"], r["status"]) for r in rows] == [("Tag", "sent")]


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
