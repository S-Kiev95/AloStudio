"""ReportingEventListener — emits :class:`ReportingEvent` rows on
dispatcher events.

Ported from:
  reference/chatwoot/app/listeners/reporting_event_listener.rb
  reference/chatwoot/app/helpers/reporting_event_helper.rb

Subscribes to the same dispatcher events as the automation +
ActionCable listeners, but only writes when the event is one of the
parity-critical four for v4.13.0 dashboards:

  * ``conversation.resolved``    → ``conversation_resolved`` (time-to-resolve)
                                   → ``conversation_bot_resolved`` when the
                                     bot resolved it with no human reply
  * ``first.reply.created``      → ``first_response`` (time-to-first-reply)
  * ``reply.created``            → ``reply_time`` (time-since-waiting)
  * ``conversation.opened``      → ``conversation_opened`` (time-since-resolve)
  * ``conversation.bot_handoff`` → ``conversation_bot_handoff`` (one per
                                     conversation; time-to-handoff)

``value_in_business_hours`` mirrors the schema but falls back to
``value`` because working-hours config lands in Phase 9. The listener
honours the same fan-out + failure-isolation contract as the other
sibling listeners.

The two ``conversation_bot_*`` rows are what the bot-metrics report
(:func:`app.domains.reporting.bot_metrics.bot_metrics`) counts. An inbox
counts as bot-activated when it has an *active* ``AgentBotInbox``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.agent_bots.models import (
    AGENT_BOT_INBOX_STATUS_ACTIVE,
    AgentBotInbox,
)
from app.domains.conversations import events as ev
from app.domains.conversations.models import (
    MESSAGE_TYPE_OUTGOING,
    SENDER_TYPE_USER,
    Conversation,
    Message,
)
from app.domains.inboxes.models import Inbox
from app.domains.reporting.models import ReportingEvent
from app.domains.working_hours.service import (
    business_hours_between,
    list_for_inbox,
)

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _seconds_between(a: datetime | None, b: datetime | None) -> float:
    """Mirror Rails' ``b.to_i - a.to_i`` — returns 0 when either side
    is missing so the dashboard math stays well-defined."""
    if a is None or b is None:
        return 0.0
    return float(int(b.timestamp()) - int(a.timestamp()))


# ---------------------------------------------------------------------------
# Listener entry point
# ---------------------------------------------------------------------------
async def fan_out_to_reporting(
    session: AsyncSession,
    event_name: str,
    **payload: Any,
) -> None:
    """Single entry point called from :func:`broadcast_event`."""
    if event_name == ev.CONVERSATION_RESOLVED:
        await _on_conversation_resolved(session, payload)
    elif event_name == ev.FIRST_REPLY_CREATED:
        await _on_first_reply_created(session, payload)
    elif event_name == ev.REPLY_CREATED:
        await _on_reply_created(session, payload)
    elif event_name == ev.CONVERSATION_OPENED:
        await _on_conversation_opened(session, payload)
    elif event_name == ev.CONVERSATION_BOT_HANDOFF:
        await _on_conversation_bot_handoff(session, payload)


# ---------------------------------------------------------------------------
# Business-hours helper (Phase 9.1)
# ---------------------------------------------------------------------------
async def _business_hours_value(
    session: AsyncSession,
    *,
    inbox_id: int | None,
    start: datetime | None,
    end: datetime | None,
    raw_value: float,
) -> float:
    """Resolve ``value_in_business_hours`` for one event.

    Falls back to ``raw_value`` when:
      * inbox_id is missing
      * inbox has no working_hours_enabled flag
      * inbox has no working_hours rows

    This is what makes Phase 7's ``value_in_business_hours`` column
    finally meaningful — until 9.1, it always equalled ``value``."""
    if inbox_id is None:
        return raw_value
    inbox = await session.get(Inbox, inbox_id)
    if inbox is None or not inbox.working_hours_enabled:
        return raw_value
    rows = await list_for_inbox(session, inbox_id=inbox_id)
    if not rows:
        return raw_value
    return business_hours_between(
        rows=rows,
        timezone_name=inbox.timezone,
        start=start,
        end=end,
    )


# ---------------------------------------------------------------------------
# Per-event handlers
# ---------------------------------------------------------------------------
async def _on_conversation_resolved(
    session: AsyncSession, payload: dict[str, Any]
) -> None:
    conversation = payload.get("conversation")
    if not isinstance(conversation, Conversation):
        return
    end = _utcnow()
    duration = _seconds_between(conversation.created_at, end)
    bh_value = await _business_hours_value(
        session,
        inbox_id=conversation.inbox_id,
        start=conversation.created_at,
        end=end,
        raw_value=duration,
    )
    event = ReportingEvent(
        name="conversation_resolved",
        value=duration,
        value_in_business_hours=bh_value,
        account_id=conversation.account_id,
        inbox_id=conversation.inbox_id,
        user_id=conversation.assignee_id,
        conversation_id=conversation.id,
        event_start_time=conversation.created_at,
        event_end_time=end,
    )
    session.add(event)
    await _maybe_add_bot_resolved(session, conversation, event)
    await session.flush()


async def _maybe_add_bot_resolved(
    session: AsyncSession,
    conversation: Conversation,
    resolved_event: ReportingEvent,
) -> None:
    """Mirror ``ReportingEventListener#create_bot_resolved_event``.

    A resolution counts as *bot-resolved* only when the inbox has an
    active bot and no human agent ever replied on the record (no outgoing
    ``User`` message). The row is a copy of the ``conversation_resolved``
    event with a different ``name``."""
    if conversation.inbox_id is None:
        return
    if not await _inbox_has_active_bot(session, conversation.inbox_id):
        return
    if await _has_human_outgoing_message(session, conversation.id):
        return
    session.add(
        ReportingEvent(
            name="conversation_bot_resolved",
            value=resolved_event.value,
            value_in_business_hours=resolved_event.value_in_business_hours,
            account_id=resolved_event.account_id,
            inbox_id=resolved_event.inbox_id,
            user_id=resolved_event.user_id,
            conversation_id=resolved_event.conversation_id,
            event_start_time=resolved_event.event_start_time,
            event_end_time=resolved_event.event_end_time,
        )
    )


async def _on_first_reply_created(
    session: AsyncSession, payload: dict[str, Any]
) -> None:
    message = payload.get("message")
    if not isinstance(message, Message):
        return
    conversation = message.conversation
    if not isinstance(conversation, Conversation):
        return
    start = await _last_non_human_activity(session, conversation)
    duration = _seconds_between(start, message.created_at)
    bh_value = await _business_hours_value(
        session,
        inbox_id=conversation.inbox_id,
        start=start,
        end=message.created_at,
        raw_value=duration,
    )
    event = ReportingEvent(
        name="first_response",
        value=duration,
        value_in_business_hours=bh_value,
        account_id=conversation.account_id,
        inbox_id=conversation.inbox_id,
        user_id=message.sender_id,
        conversation_id=conversation.id,
        event_start_time=start,
        event_end_time=message.created_at,
    )
    session.add(event)
    await session.flush()


async def _on_reply_created(
    session: AsyncSession, payload: dict[str, Any]
) -> None:
    """``reply.created`` carries ``waiting_since`` in the event payload —
    set by :func:`app.domains.conversations.service._update_waiting_since`
    just before dispatch."""
    message = payload.get("message")
    waiting_since = payload.get("waiting_since")
    if not isinstance(message, Message):
        return
    if waiting_since is None:
        return
    conversation = message.conversation
    if not isinstance(conversation, Conversation):
        return
    duration = _seconds_between(waiting_since, message.created_at)
    bh_value = await _business_hours_value(
        session,
        inbox_id=conversation.inbox_id,
        start=waiting_since,
        end=message.created_at,
        raw_value=duration,
    )
    event = ReportingEvent(
        name="reply_time",
        value=duration,
        value_in_business_hours=bh_value,
        account_id=conversation.account_id,
        inbox_id=conversation.inbox_id,
        user_id=conversation.assignee_id,
        conversation_id=conversation.id,
        event_start_time=waiting_since,
        event_end_time=message.created_at,
    )
    session.add(event)
    await session.flush()


async def _on_conversation_opened(
    session: AsyncSession, payload: dict[str, Any]
) -> None:
    """Reopen event — value = seconds since the most recent
    ``conversation_resolved`` event on this conversation. First-time
    open emits value=0 (mirrors Rails)."""
    conversation = payload.get("conversation")
    if not isinstance(conversation, Conversation):
        return
    end = _utcnow()
    last_resolved = (
        await session.exec(
            select(ReportingEvent)
            .where(
                ReportingEvent.conversation_id == conversation.id,
                ReportingEvent.name == "conversation_resolved",
                ReportingEvent.event_end_time.is_not(None),  # type: ignore[union-attr]
            )
            .order_by(ReportingEvent.event_end_time.desc())  # type: ignore[union-attr]
            .limit(1)
        )
    ).first()
    if last_resolved is not None and last_resolved.event_end_time is not None:
        start = last_resolved.event_end_time
        duration = _seconds_between(start, end)
    else:
        start = conversation.created_at
        duration = 0.0
    bh_value = await _business_hours_value(
        session,
        inbox_id=conversation.inbox_id,
        start=start,
        end=end,
        raw_value=duration,
    )
    event = ReportingEvent(
        name="conversation_opened",
        value=duration,
        value_in_business_hours=bh_value,
        account_id=conversation.account_id,
        inbox_id=conversation.inbox_id,
        user_id=conversation.assignee_id,
        conversation_id=conversation.id,
        event_start_time=start,
        event_end_time=end,
    )
    session.add(event)
    await session.flush()


async def _on_conversation_bot_handoff(
    session: AsyncSession, payload: dict[str, Any]
) -> None:
    """``conversation.bot_handoff`` → ``conversation_bot_handoff``.

    Deduped to one row per conversation: the raw report counts handoffs
    with ``DISTINCT conversation_id``, so a second handoff would not move
    that number but would skew any per-event rollup. Mirrors the Rails
    listener's ``find_by ... return if present`` guard.
    """
    conversation = payload.get("conversation")
    if not isinstance(conversation, Conversation):
        return
    existing = (
        await session.exec(
            select(ReportingEvent.id)
            .where(
                ReportingEvent.conversation_id == conversation.id,
                ReportingEvent.name == "conversation_bot_handoff",
            )
            .limit(1)
        )
    ).first()
    if existing is not None:
        return
    end = _utcnow()
    duration = _seconds_between(conversation.created_at, end)
    bh_value = await _business_hours_value(
        session,
        inbox_id=conversation.inbox_id,
        start=conversation.created_at,
        end=end,
        raw_value=duration,
    )
    event = ReportingEvent(
        name="conversation_bot_handoff",
        value=duration,
        value_in_business_hours=bh_value,
        account_id=conversation.account_id,
        inbox_id=conversation.inbox_id,
        user_id=conversation.assignee_id,
        conversation_id=conversation.id,
        event_start_time=conversation.created_at,
        event_end_time=end,
    )
    session.add(event)
    await session.flush()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _inbox_has_active_bot(session: AsyncSession, inbox_id: int) -> bool:
    """Mirror ``Inbox#active_bot?`` (agent-bot arm).

    True when an *active* ``AgentBotInbox`` is attached. Chatwoot also
    treats an enabled Dialogflow hook as an active bot; that integration
    isn't wired here yet (parity follow-up)."""
    row = (
        await session.exec(
            select(AgentBotInbox.id)
            .where(
                AgentBotInbox.inbox_id == inbox_id,
                AgentBotInbox.status == AGENT_BOT_INBOX_STATUS_ACTIVE,
            )
            .limit(1)
        )
    ).first()
    return row is not None


async def _has_human_outgoing_message(
    session: AsyncSession, conversation_id: int | None
) -> bool:
    """True when a human agent sent an outgoing message on the record —
    mirrors ``messages.exists?(message_type: :outgoing, sender_type:
    'User')``."""
    if conversation_id is None:
        return False
    row = (
        await session.exec(
            select(Message.id)
            .where(
                Message.conversation_id == conversation_id,
                Message.message_type == MESSAGE_TYPE_OUTGOING,
                Message.sender_type == SENDER_TYPE_USER,
            )
            .limit(1)
        )
    ).first()
    return row is not None


async def _last_non_human_activity(
    session: AsyncSession, conversation: Conversation
) -> datetime | None:
    """Mirror ``ReportingEventHelper#last_non_human_activity``.

    Returns the timestamp of the most recent bot/reopen activity on the
    conversation, falling back to ``conversation.created_at`` when no
    such activity exists. The first-response timer measures from this
    anchor.
    """
    event = (
        await session.exec(
            select(ReportingEvent)
            .where(
                ReportingEvent.conversation_id == conversation.id,
                ReportingEvent.name.in_(  # type: ignore[union-attr]
                    ["conversation_bot_handoff", "conversation_opened"]
                ),
                ReportingEvent.event_end_time.is_not(None),  # type: ignore[union-attr]
            )
            .order_by(ReportingEvent.event_end_time.desc())  # type: ignore[union-attr]
            .limit(1)
        )
    ).first()
    if event is not None and event.event_end_time is not None:
        return event.event_end_time
    return conversation.created_at


__all__ = ["fan_out_to_reporting"]
