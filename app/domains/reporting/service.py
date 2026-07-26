"""Report aggregation services for the v2 dashboard endpoints.

Ported from:
  reference/chatwoot/app/helpers/report_helper.rb
  reference/chatwoot/app/builders/v2/report_builder.rb
  reference/chatwoot/app/controllers/api/v2/accounts/reports_controller.rb

This module hosts the cross-cutting aggregation logic shared by the
summary, timeseries, live and per-entity reports. The wire-shape
presenters + HTTP endpoints live in :mod:`app.domains.reporting.router`.

Scopes match Chatwoot's ``ReportHelper#scope`` — when the caller
asks for ``type='inbox'`` (or agent / team / label) we add the
corresponding ``inbox_id`` / ``user_id`` / ``conversation_label`` /
team-member join. ``type='account'`` (default) returns
account-wide counts.

``business_hours=true`` swaps the ReportingEvent value column from
``value`` to ``value_in_business_hours``. Phase 7.1 makes both
columns equal until working-hours config arrives in Phase 9, so the
flag is preserved on the wire but does not affect results yet.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import func as sa_func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import (
    CONVERSATION_STATUS_OPEN,
    CONVERSATION_STATUS_PENDING,
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
)
from app.domains.labels.models import Label
from app.domains.reporting.models import ReportingEvent
from app.domains.teams.models import TeamMember

ScopeType = Literal["account", "inbox", "agent", "team", "label"]


# ---------------------------------------------------------------------------
# Scope helpers
# ---------------------------------------------------------------------------
def _apply_conversation_scope(
    stmt,
    *,
    account_id: int,
    type: ScopeType,
    id: int | None,
):
    """Scope a Conversation query by type + id.

    Mirrors ``ReportHelper#scope.conversations``:
      * type=account → all conversations on the account
      * type=inbox   → ``conversations.inbox_id == id``
      * type=agent   → ``conversations.assignee_id == id``
      * type=team    → ``conversations.team_id == id``
      * type=label   → join through conversation_labels → labels.title
                       where labels.id == id
    """
    stmt = stmt.where(Conversation.account_id == account_id)
    if type == "inbox" and id is not None:
        stmt = stmt.where(Conversation.inbox_id == id)
    elif type == "agent" and id is not None:
        stmt = stmt.where(Conversation.assignee_id == id)
    elif type == "team" and id is not None:
        stmt = stmt.where(Conversation.team_id == id)
    elif type == "label" and id is not None:
        from app.domains.conversations.models import ConversationLabel

        stmt = stmt.join(
            ConversationLabel,
            ConversationLabel.conversation_id == Conversation.id,
        ).where(ConversationLabel.label_id == id)
    return stmt


def _apply_reporting_event_scope(
    stmt,
    *,
    account_id: int,
    type: ScopeType,
    id: int | None,
):
    stmt = stmt.where(ReportingEvent.account_id == account_id)
    if type == "inbox" and id is not None:
        stmt = stmt.where(ReportingEvent.inbox_id == id)
    elif type == "agent" and id is not None:
        stmt = stmt.where(ReportingEvent.user_id == id)
    elif type == "team" and id is not None:
        # Reporting events don't carry team_id; join through conversation.
        stmt = stmt.join(
            Conversation,
            Conversation.id == ReportingEvent.conversation_id,
        ).where(Conversation.team_id == id)
    elif type == "label" and id is not None:
        from app.domains.conversations.models import ConversationLabel

        stmt = stmt.join(
            Conversation,
            Conversation.id == ReportingEvent.conversation_id,
        ).join(
            ConversationLabel,
            ConversationLabel.conversation_id == Conversation.id,
        ).where(ConversationLabel.label_id == id)
    return stmt


def _apply_message_scope(
    stmt,
    *,
    account_id: int,
    type: ScopeType,
    id: int | None,
):
    stmt = stmt.where(Message.account_id == account_id)
    if type == "inbox" and id is not None:
        stmt = stmt.where(Message.inbox_id == id)
    elif type == "agent" and id is not None:
        # Agent-scoped messages: messages sent by the agent.
        stmt = stmt.where(Message.sender_type == "User")
        stmt = stmt.where(Message.sender_id == id)
    elif type in ("team", "label") and id is not None:
        # Both require joining through conversation.
        stmt = stmt.join(
            Conversation, Conversation.id == Message.conversation_id
        )
        if type == "team":
            stmt = stmt.where(Conversation.team_id == id)
        else:
            from app.domains.conversations.models import ConversationLabel

            stmt = stmt.join(
                ConversationLabel,
                ConversationLabel.conversation_id == Conversation.id,
            ).where(ConversationLabel.label_id == id)
    return stmt


# ---------------------------------------------------------------------------
# Range helper
# ---------------------------------------------------------------------------
def parse_unix_range(
    since: str | None, until: str | None
) -> tuple[datetime | None, datetime | None]:
    """Chatwoot passes ``since`` / ``until`` as Unix seconds in the
    query string. Accept None for open-ended ranges."""
    from datetime import UTC

    def _parse(raw: str | None) -> datetime | None:
        if raw is None or raw == "":
            return None
        try:
            return datetime.fromtimestamp(int(raw), tz=UTC)
        except (TypeError, ValueError):
            return None

    return _parse(since), _parse(until)


def previous_window(
    since: datetime | None, until: datetime | None
) -> tuple[datetime | None, datetime | None]:
    """Symmetric prior window — width matches the current window."""
    if since is None or until is None:
        return None, None
    width = until - since
    return (since - width, since)


# ---------------------------------------------------------------------------
# Aggregations
# ---------------------------------------------------------------------------
async def conversations_count(
    session: AsyncSession,
    *,
    account_id: int,
    type: ScopeType,
    id: int | None,
    since: datetime | None,
    until: datetime | None,
) -> int:
    stmt = select(sa_func.count(sa_func.distinct(Conversation.id)))
    stmt = _apply_conversation_scope(
        stmt, account_id=account_id, type=type, id=id
    )
    if since is not None:
        stmt = stmt.where(Conversation.created_at >= since)
    if until is not None:
        stmt = stmt.where(Conversation.created_at <= until)
    return int((await session.exec(stmt)).one() or 0)


async def messages_count(
    session: AsyncSession,
    *,
    account_id: int,
    type: ScopeType,
    id: int | None,
    message_type: int,
    since: datetime | None,
    until: datetime | None,
) -> int:
    stmt = select(sa_func.count(sa_func.distinct(Message.id)))
    stmt = _apply_message_scope(
        stmt, account_id=account_id, type=type, id=id
    )
    stmt = stmt.where(Message.message_type == message_type)
    if since is not None:
        stmt = stmt.where(Message.created_at >= since)
    if until is not None:
        stmt = stmt.where(Message.created_at <= until)
    return int((await session.exec(stmt)).one() or 0)


async def reporting_event_count(
    session: AsyncSession,
    *,
    account_id: int,
    type: ScopeType,
    id: int | None,
    name: str,
    since: datetime | None,
    until: datetime | None,
) -> int:
    stmt = select(sa_func.count(sa_func.distinct(ReportingEvent.id)))
    stmt = _apply_reporting_event_scope(
        stmt, account_id=account_id, type=type, id=id
    )
    stmt = stmt.where(ReportingEvent.name == name)
    if since is not None:
        stmt = stmt.where(ReportingEvent.created_at >= since)
    if until is not None:
        stmt = stmt.where(ReportingEvent.created_at <= until)
    return int((await session.exec(stmt)).one() or 0)


async def reporting_event_avg(
    session: AsyncSession,
    *,
    account_id: int,
    type: ScopeType,
    id: int | None,
    name: str,
    since: datetime | None,
    until: datetime | None,
    business_hours: bool = False,
) -> float:
    """Mirror Rails' ``avg_<x>_summary``: returns 0 when no rows match,
    otherwise the average ``value`` (or ``value_in_business_hours``)
    column."""
    column = (
        ReportingEvent.value_in_business_hours
        if business_hours
        else ReportingEvent.value
    )
    stmt = select(sa_func.avg(column))
    stmt = _apply_reporting_event_scope(
        stmt, account_id=account_id, type=type, id=id
    )
    stmt = stmt.where(ReportingEvent.name == name)
    if since is not None:
        stmt = stmt.where(ReportingEvent.created_at >= since)
    if until is not None:
        stmt = stmt.where(ReportingEvent.created_at <= until)
    raw = (await session.exec(stmt)).one()
    if raw is None:
        return 0.0
    return float(raw)


# ---------------------------------------------------------------------------
# Composite — summary cards
# ---------------------------------------------------------------------------
async def build_summary(
    session: AsyncSession,
    *,
    account_id: int,
    type: ScopeType,
    id: int | None,
    since: datetime | None,
    until: datetime | None,
    business_hours: bool = False,
) -> dict[str, Any]:
    """Mirror ``V2::ReportBuilder#summary``."""
    return {
        "conversations_count": await conversations_count(
            session,
            account_id=account_id,
            type=type,
            id=id,
            since=since,
            until=until,
        ),
        "incoming_messages_count": await messages_count(
            session,
            account_id=account_id,
            type=type,
            id=id,
            message_type=MESSAGE_TYPE_INCOMING,
            since=since,
            until=until,
        ),
        "outgoing_messages_count": await messages_count(
            session,
            account_id=account_id,
            type=type,
            id=id,
            message_type=MESSAGE_TYPE_OUTGOING,
            since=since,
            until=until,
        ),
        "avg_first_response_time": await reporting_event_avg(
            session,
            account_id=account_id,
            type=type,
            id=id,
            name="first_response",
            since=since,
            until=until,
            business_hours=business_hours,
        ),
        "avg_resolution_time": await reporting_event_avg(
            session,
            account_id=account_id,
            type=type,
            id=id,
            name="conversation_resolved",
            since=since,
            until=until,
            business_hours=business_hours,
        ),
        "resolutions_count": await reporting_event_count(
            session,
            account_id=account_id,
            type=type,
            id=id,
            name="conversation_resolved",
            since=since,
            until=until,
        ),
        "reply_time": await reporting_event_avg(
            session,
            account_id=account_id,
            type=type,
            id=id,
            name="reply_time",
            since=since,
            until=until,
            business_hours=business_hours,
        ),
    }


# ---------------------------------------------------------------------------
# Live counters
# ---------------------------------------------------------------------------
async def live_conversation_metrics(
    session: AsyncSession,
    *,
    account_id: int,
    type: ScopeType,
    id: int | None,
) -> dict[str, int]:
    """Mirror ``V2::ReportBuilder#live_conversations``.

    Returns the current-state snapshot used by the dashboard's "live"
    widgets. ``open`` + ``unattended`` are returned for every scope;
    ``unassigned`` + ``pending`` only when ``type=account``.
    """
    base = select(Conversation)
    base = _apply_conversation_scope(
        base, account_id=account_id, type=type, id=id
    )
    base = base.where(Conversation.status == CONVERSATION_STATUS_OPEN)

    # Count helpers reuse the same scoped query shape.
    open_count = int(
        (
            await session.exec(
                base.with_only_columns(
                    sa_func.count(sa_func.distinct(Conversation.id))
                )
            )
        ).one()
        or 0
    )

    unattended_q = base.where(
        Conversation.first_reply_created_at.is_(None)  # type: ignore[union-attr]
    )
    unattended_count = int(
        (
            await session.exec(
                unattended_q.with_only_columns(
                    sa_func.count(sa_func.distinct(Conversation.id))
                )
            )
        ).one()
        or 0
    )

    metric: dict[str, int] = {
        "open": open_count,
        "unattended": unattended_count,
    }

    if type == "account":
        unassigned_q = base.where(Conversation.assignee_id.is_(None))  # type: ignore[union-attr]
        unassigned_count = int(
            (
                await session.exec(
                    unassigned_q.with_only_columns(
                        sa_func.count(sa_func.distinct(Conversation.id))
                    )
                )
            ).one()
            or 0
        )
        # pending is its own status — separate query.
        pending_stmt = select(
            sa_func.count(sa_func.distinct(Conversation.id))
        )
        pending_stmt = _apply_conversation_scope(
            pending_stmt, account_id=account_id, type=type, id=id
        )
        pending_stmt = pending_stmt.where(
            Conversation.status == CONVERSATION_STATUS_PENDING
        )
        pending_count = int(
            (await session.exec(pending_stmt)).one() or 0
        )
        metric["unassigned"] = unassigned_count
        metric["pending"] = pending_count

    return metric


# Mapper-config nudge for related models.
_ = (Label, TeamMember)


__all__ = [
    "ScopeType",
    "build_summary",
    "conversations_count",
    "live_conversation_metrics",
    "messages_count",
    "parse_unix_range",
    "previous_window",
    "reporting_event_avg",
    "reporting_event_count",
]
