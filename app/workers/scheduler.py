"""Periodic scheduler — the ARQ-side port of Chatwoot's
``TriggerScheduledItemsJob``.

Ported from:
  reference/chatwoot/app/jobs/trigger_scheduled_items_job.rb
  reference/chatwoot/app/jobs/campaigns/trigger_oneoff_campaign_job.rb
  reference/chatwoot/app/jobs/conversations/reopen_snoozed_conversations_job.rb
  reference/chatwoot/config/schedule.yml

Two tasks run every 5 minutes:

  1. ``fire_due_oneoff_campaigns``  — find every ``one_off`` campaign
     in ``[now - 3d, now]`` whose ``campaign_status == active``,
     deliver it to its audience (one conversation + outgoing message
     per Contact, via ``_deliver_oneoff_campaign``), then mark it
     ``completed``.
  2. ``reopen_snoozed_conversations`` — flip every snoozed
     conversation whose ``snoozed_until <= now()`` back to ``open``.
     Mirrors ``Conversations::ReopenSnoozedConversationsJob``.

The functions are imported and called directly by tests; the ARQ
worker just wraps them in the scheduler cadence.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.campaigns.models import (
    CAMPAIGN_STATUS_ACTIVE,
    CAMPAIGN_STATUS_COMPLETED,
    CAMPAIGN_TYPE_ONE_OFF,
    Campaign,
)
from app.domains.conversations.models import (
    CONVERSATION_STATUS_SNOOZED,
    Conversation,
)

log = logging.getLogger(__name__)

# Chatwoot's window: 3 days back from now.
_ONEOFF_WINDOW_DAYS = 3


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# One-off campaigns
# ---------------------------------------------------------------------------
async def fire_due_oneoff_campaigns(session: AsyncSession) -> int:
    """Find one-off campaigns due in the [now - 3d, now] window and
    flip them to ``completed``.

    Returns the number of campaigns fired. Per-channel send pipeline
    (Twilio / SMS / WhatsApp ``OneoffCampaignService``) defers to
    follow-up; this milestone ships the state flip so the dashboard's
    "Completed" filter behaves correctly.

    Mirrors the campaign loop in
    ``TriggerScheduledItemsJob#perform``.
    """
    now = _utcnow()
    window_start = now - timedelta(days=_ONEOFF_WINDOW_DAYS)
    stmt = select(Campaign).where(
        Campaign.campaign_type == CAMPAIGN_TYPE_ONE_OFF,
        Campaign.campaign_status == CAMPAIGN_STATUS_ACTIVE,
        Campaign.scheduled_at.is_not(None),  # type: ignore[union-attr]
        Campaign.scheduled_at >= window_start,  # type: ignore[operator]
        Campaign.scheduled_at <= now,  # type: ignore[operator]
    )
    rows = list((await session.exec(stmt)).all())
    for campaign in rows:
        sent = await _deliver_oneoff_campaign(session, campaign)
        campaign.campaign_status = CAMPAIGN_STATUS_COMPLETED
        session.add(campaign)
        log.info(
            "scheduler.campaign.fired campaign_id=%s display_id=%s sent=%s",
            campaign.id,
            campaign.display_id,
            sent,
        )
    if rows:
        await session.flush()
    return len(rows)


async def _deliver_oneoff_campaign(session: AsyncSession, campaign: Campaign) -> int:
    """Create a conversation + outgoing message per audience Contact.

    Ports ``Campaigns::CampaignConversationBuilder``: for each
    ``{type: 'Contact', id: ...}`` in ``campaign.audience`` we find (or
    create) the ContactInbox in the campaign's inbox, skip it when a
    conversation is already present (idempotency — don't re-send), then
    create a fresh conversation stamped with ``campaign_id`` plus an
    outgoing message carrying the campaign body. The sender is the
    campaign's ``sender_id`` (nil → an unattributed outgoing message,
    matching ``campaign.sender`` being nil in Rails).

    A failure on one contact is logged and skipped — it never aborts the
    rest of the audience (mirrors the builder's ``rescue StandardError``).
    Returns the number of conversations actually created.
    """
    from app.domains.campaigns.builder import build_campaign_conversation
    from app.domains.contacts.models import Contact, ContactInbox
    from app.domains.contacts.service import ContactInboxBuilder
    from app.domains.inboxes.models import Inbox

    inbox = (
        await session.exec(select(Inbox).where(Inbox.id == campaign.inbox_id))
    ).first()
    if inbox is None:
        return 0

    sent = 0
    for entry in campaign.audience or []:
        if not isinstance(entry, dict) or entry.get("type") != "Contact":
            continue
        contact_id = entry.get("id")
        try:
            contact = (
                await session.exec(
                    select(Contact).where(
                        Contact.id == contact_id,
                        Contact.account_id == campaign.account_id,
                    )
                )
            ).first()
            if contact is None:
                continue
            contact_inbox = (
                await session.exec(
                    select(ContactInbox).where(
                        ContactInbox.contact_id == contact.id,
                        ContactInbox.inbox_id == inbox.id,
                    )
                )
            ).first()
            if contact_inbox is None:
                contact_inbox = await ContactInboxBuilder(
                    session=session, contact=contact, inbox=inbox
                ).perform()
            conv = await build_campaign_conversation(
                session, campaign=campaign, contact_inbox=contact_inbox
            )
            if conv is not None:
                sent += 1
        except Exception as exc:
            log.warning(
                "scheduler.campaign.contact_failed campaign_id=%s "
                "contact_id=%s err=%s",
                campaign.id,
                contact_id,
                exc,
            )
            continue
    return sent


# ---------------------------------------------------------------------------
# Reopen snoozed conversations
# ---------------------------------------------------------------------------
async def reopen_snoozed_conversations(session: AsyncSession) -> int:
    """Reopen every snoozed conversation whose ``snoozed_until`` has
    passed.

    Returns the number reopened. Mirrors
    ``Conversations::ReopenSnoozedConversationsJob`` — except the Rails
    version dispatches each as a separate background job; we batch
    inline since the operation is cheap (one UPDATE per row + a
    dispatcher event for downstream listeners).
    """
    from app.domains.conversations.service import toggle_status

    now = _utcnow()
    stmt = select(Conversation).where(
        Conversation.status == CONVERSATION_STATUS_SNOOZED,
        Conversation.snoozed_until.is_not(None),  # type: ignore[union-attr]
        Conversation.snoozed_until <= now,  # type: ignore[operator]
    )
    rows = list((await session.exec(stmt)).all())
    for conv in rows:
        await toggle_status(session, conversation=conv, status="open")
        log.info(
            "scheduler.conversation.reopened conversation_id=%s display_id=%s",
            conv.id,
            conv.display_id,
        )
    return len(rows)


# ---------------------------------------------------------------------------
# ARQ tick
# ---------------------------------------------------------------------------
async def tick_5min(ctx: dict[str, Any]) -> dict[str, int]:
    """The ARQ task body — runs every 5 minutes.

    ``ctx`` is ARQ's per-job context; we pull the cached engine off
    it via :func:`_engine_from_ctx`, open a single session for both
    tasks (transaction-per-tick mirrors Rails' implicit
    ``ActiveRecord::Base.transaction``), and report counts so the
    ARQ logs carry signal."""
    engine = _engine_from_ctx(ctx)
    sessionmaker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with sessionmaker() as session:
        campaigns_fired = await fire_due_oneoff_campaigns(session)
        conversations_reopened = await reopen_snoozed_conversations(session)
        await session.commit()

    # Instagram scheduled posts (feat/instagram-graph I.2). Runs in its
    # own session because ``fire_due_instagram_posts`` enqueues ARQ
    # jobs (side-effects outside the tick transaction).
    from app.workers.instagram import fire_due_instagram_posts

    async with sessionmaker() as ig_session:
        ig_fired = await fire_due_instagram_posts(ig_session)
        await ig_session.commit()

    log.info(
        "scheduler.tick.done campaigns_fired=%s conversations_reopened=%s "
        "instagram_posts_fired=%s",
        campaigns_fired,
        conversations_reopened,
        len(ig_fired),
    )
    return {
        "campaigns_fired": campaigns_fired,
        "conversations_reopened": conversations_reopened,
        "instagram_posts_fired": len(ig_fired),
    }


def _engine_from_ctx(ctx: dict[str, Any]) -> AsyncEngine:
    engine = ctx.get("engine")
    if engine is None:
        engine = create_async_engine(
            get_settings().database_url,
            pool_pre_ping=True,
        )
        ctx["engine"] = engine
    return engine  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# ARQ WorkerSettings
# ---------------------------------------------------------------------------
class WorkerSettings:
    """ARQ entry point — ``arq app.workers.scheduler.WorkerSettings``.

    Cadence mirrors Chatwoot's ``trigger_scheduled_items_job`` cron
    (``*/5 * * * *``). ARQ's ``cron_jobs`` schedules tasks by
    minute-of-the-hour bitmask; we set 0, 5, 10, ... to match the
    same cadence in a deployment-agnostic way (no system cron
    required).
    """

    @staticmethod
    async def on_startup(ctx: dict[str, Any]) -> None:
        ctx["engine"] = create_async_engine(
            get_settings().database_url,
            pool_pre_ping=True,
        )

    @staticmethod
    async def on_shutdown(ctx: dict[str, Any]) -> None:
        engine = ctx.get("engine")
        if engine is not None:
            await engine.dispose()

    # ``tick_5min`` is the cron task; ``publish_instagram_post_task`` is
    # enqueued on-demand (immediate publish from the REST endpoint +
    # scheduled fires from ``fire_due_instagram_posts``).
    @staticmethod
    def _functions() -> list:
        from arq import func

        from app.domains.notifications.mailer import send_notification_email_task
        from app.domains.notifications.push import send_notification_push_task
        from app.domains.portals.embeddings import reindex_article_task
        from app.workers.deliver_webhook import (
            MAX_ATTEMPTS as WEBHOOK_MAX_ATTEMPTS,
        )
        from app.workers.deliver_webhook import deliver_webhook_task
        from app.workers.instagram import publish_instagram_post_task

        return [
            tick_5min,
            publish_instagram_post_task,
            # Enqueued on-demand by the NotificationListener when an in-app
            # notification is created and the recipient wants it by email / push.
            send_notification_email_task,
            send_notification_push_task,
            # Enqueued on-demand when a Help-Center article is created/edited
            # and OpenAI embedding search is enabled.
            reindex_article_task,
            # Pin ARQ's ``max_tries`` to the webhook delivery's own cap so
            # the final attempt (which writes the dead-letter row) is never
            # preempted by ARQ's default give-up. Keeps the quarantine
            # record guaranteed even if MAX_ATTEMPTS is bumped later.
            func(deliver_webhook_task, max_tries=WEBHOOK_MAX_ATTEMPTS),
        ]

    functions = []  # type: ignore[var-annotated]  # populated via configure()
    cron_jobs: list = []  # populated below via late import
    # Populated by configure(); without it arq's CLI defaults to
    # ``RedisSettings()`` = localhost:6379, ignoring ``ARQ_REDIS_URL``.
    redis_settings: Any = None

    @classmethod
    def configure(cls) -> None:
        """Late-init: building the cron list + function list at
        class-body time would pull in arq before we know the
        deployment wants the worker. Call :meth:`configure` from the
        worker entry point."""
        from arq.connections import RedisSettings
        from arq.cron import cron

        cls.redis_settings = RedisSettings.from_dsn(
            get_settings().arq_redis_url
        )
        cls.functions = cls._functions()
        cls.cron_jobs = [
            cron(
                tick_5min,
                minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            )
        ]


__all__ = [
    "WorkerSettings",
    "fire_due_oneoff_campaigns",
    "reopen_snoozed_conversations",
    "tick_5min",
]
