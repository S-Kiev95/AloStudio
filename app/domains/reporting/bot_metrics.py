"""Bot-metrics report builder.

Port of ``V2::Reports::BotMetricsBuilder``
(reference/chatwoot/app/builders/v2/reports/bot_metrics_builder.rb).

Four numbers over a ``since..until`` window (both bounds inclusive,
matching Rails' ``where(created_at: range)``):

  * ``conversation_count`` — conversations created in a bot-activated
    inbox during the window.
  * ``message_count``      — outgoing messages during the window that
    belong to those bot conversations.
  * ``resolution_rate``    — distinct conversations with a
    ``conversation_bot_resolved`` event / conversation_count x 100 (int).
  * ``handoff_rate``       — distinct conversations with a
    ``conversation_bot_handoff`` event / conversation_count x 100 (int).

We mirror Rails' quirks exactly: the resolution/handoff numerators count
events by name across the whole account in the window (they are only ever
written for bot inboxes), *not* intersected with ``conversation_count``,
so a rate can in principle exceed 100 if more resolutions land in the
window than conversations were created in it. ``.to_i`` truncates toward
zero — Python ``int()`` does the same for these non-negative values.

An inbox is "bot-activated" when it has an *active* ``AgentBotInbox``.
Chatwoot also treats an enabled Dialogflow hook as an active bot; that
integration isn't wired in our stack yet, so it's a parity follow-up.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func as sa_func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.agent_bots.models import (
    AGENT_BOT_INBOX_STATUS_ACTIVE,
    AgentBotInbox,
)
from app.domains.conversations.models import (
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
)
from app.domains.inboxes.models import Inbox
from app.domains.reporting.models import ReportingEvent


async def _bot_activated_inbox_ids(
    session: AsyncSession, *, account_id: int
) -> list[int]:
    rows = (
        await session.exec(
            select(AgentBotInbox.inbox_id)
            .join(Inbox, Inbox.id == AgentBotInbox.inbox_id)  # type: ignore[arg-type]
            .where(
                Inbox.account_id == account_id,
                AgentBotInbox.status == AGENT_BOT_INBOX_STATUS_ACTIVE,
            )
            .distinct()
        )
    ).all()
    return [r for r in rows if r is not None]


async def _distinct_bot_event_conversations(
    session: AsyncSession,
    *,
    account_id: int,
    name: str,
    since: datetime | None,
    until: datetime | None,
) -> int:
    """Distinct conversation_ids with a named reporting event in range.

    ``JOIN conversation`` mirrors Rails' ``joins(:conversation)`` — it
    drops events whose conversation was hard-deleted."""
    stmt = (
        select(sa_func.count(sa_func.distinct(ReportingEvent.conversation_id)))
        .join(Conversation, Conversation.id == ReportingEvent.conversation_id)  # type: ignore[arg-type]
        .where(
            ReportingEvent.account_id == account_id,
            ReportingEvent.name == name,
        )
    )
    if since is not None:
        stmt = stmt.where(ReportingEvent.created_at >= since)
    if until is not None:
        stmt = stmt.where(ReportingEvent.created_at <= until)
    return int((await session.exec(stmt)).one() or 0)


async def bot_metrics(
    session: AsyncSession,
    *,
    account_id: int,
    since: datetime | None,
    until: datetime | None,
) -> dict[str, Any]:
    inbox_ids = await _bot_activated_inbox_ids(session, account_id=account_id)

    # conversation_count — conversations in bot inboxes, created in range.
    conv_stmt = select(sa_func.count(sa_func.distinct(Conversation.id))).where(
        Conversation.account_id == account_id,
        Conversation.inbox_id.in_(inbox_ids),  # type: ignore[attr-defined]
    )
    if since is not None:
        conv_stmt = conv_stmt.where(Conversation.created_at >= since)
    if until is not None:
        conv_stmt = conv_stmt.where(Conversation.created_at <= until)
    conversation_count = int(
        (await session.exec(conv_stmt)).one() or 0
    )

    # message_count — outgoing messages in range on those bot conversations.
    bot_conv_ids = select(Conversation.id).where(
        Conversation.account_id == account_id,
        Conversation.inbox_id.in_(inbox_ids),  # type: ignore[attr-defined]
    )
    if since is not None:
        bot_conv_ids = bot_conv_ids.where(Conversation.created_at >= since)
    if until is not None:
        bot_conv_ids = bot_conv_ids.where(Conversation.created_at <= until)
    msg_stmt = select(sa_func.count(sa_func.distinct(Message.id))).where(
        Message.account_id == account_id,
        Message.message_type == MESSAGE_TYPE_OUTGOING,
        Message.conversation_id.in_(bot_conv_ids),  # type: ignore[attr-defined]
    )
    if since is not None:
        msg_stmt = msg_stmt.where(Message.created_at >= since)
    if until is not None:
        msg_stmt = msg_stmt.where(Message.created_at <= until)
    message_count = int(
        (await session.exec(msg_stmt)).one() or 0
    )

    if conversation_count == 0:
        resolution_rate = 0
        handoff_rate = 0
    else:
        resolutions = await _distinct_bot_event_conversations(
            session,
            account_id=account_id,
            name="conversation_bot_resolved",
            since=since,
            until=until,
        )
        handoffs = await _distinct_bot_event_conversations(
            session,
            account_id=account_id,
            name="conversation_bot_handoff",
            since=since,
            until=until,
        )
        resolution_rate = int(resolutions / conversation_count * 100)
        handoff_rate = int(handoffs / conversation_count * 100)

    return {
        "conversation_count": conversation_count,
        "message_count": message_count,
        "resolution_rate": resolution_rate,
        "handoff_rate": handoff_rate,
    }


__all__ = ["bot_metrics"]
