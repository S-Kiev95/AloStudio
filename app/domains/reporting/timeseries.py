"""Timeseries aggregation for the dashboard line chart.

Ported from:
  reference/chatwoot/app/builders/v2/reports/timeseries/count_report_builder.rb
  reference/chatwoot/app/builders/v2/reports/timeseries/average_report_builder.rb
  reference/chatwoot/app/builders/v2/report_builder.rb (legacy ``timeseries`` path)

The ``GET /api/v2/accounts/{id}/reports`` endpoint takes
``metric=<name>`` and returns a daily-bucketed series:

    [{"value": <number>, "timestamp": <unix_seconds>}, ...]

Avg metrics (``avg_first_response_time``, ``avg_resolution_time``,
``reply_time``) additionally include a ``count`` per bucket — Rails'
``V2::ReportBuilder#build`` branches on the metric name to decide.

Count metrics:
  * conversations_count        → conversations.created_at buckets
  * incoming_messages_count    → incoming messages
  * outgoing_messages_count    → outgoing messages
  * resolutions_count          → reporting_events name=conversation_resolved
  * bot_resolutions_count      → conversation_bot_resolved (always 0 in 7.x;
                                 Phase 8 emits the rows)
  * bot_handoffs_count         → conversation_bot_handoff (DISTINCT
                                 conversation_id; always 0 in 7.x)

Avg metrics:
  * avg_first_response_time    → avg(value) over first_response events
  * avg_resolution_time        → avg(value) over conversation_resolved
  * reply_time                 → avg(value) over reply_time events

Bucketing: we use ``date_trunc('day', column AT TIME ZONE tz)`` so the
bucket boundaries land at midnight in the caller's timezone (matches
Rails' ``group_by_period(..., time_zone: tz)``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from typing import Any, Literal

from sqlalchemy import (
    Float,
    case,
    cast,
    func as sa_func,
    text,
)
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import (
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
)
from app.domains.reporting.models import ReportingEvent
from app.domains.reporting.service import (
    ScopeType,
    _apply_conversation_scope,
    _apply_message_scope,
    _apply_reporting_event_scope,
)

CountMetric = Literal[
    "conversations_count",
    "incoming_messages_count",
    "outgoing_messages_count",
    "resolutions_count",
    "bot_resolutions_count",
    "bot_handoffs_count",
]

AvgMetric = Literal[
    "avg_first_response_time",
    "avg_resolution_time",
    "reply_time",
]

ALL_METRICS: tuple[str, ...] = (
    "conversations_count",
    "incoming_messages_count",
    "outgoing_messages_count",
    "resolutions_count",
    "bot_resolutions_count",
    "bot_handoffs_count",
    "avg_first_response_time",
    "avg_resolution_time",
    "reply_time",
)

# Avg metric -> ReportingEvent name.
_AVG_TO_EVENT: dict[str, str] = {
    "avg_first_response_time": "first_response",
    "avg_resolution_time": "conversation_resolved",
    "reply_time": "reply_time",
}


def timezone_from_offset(offset: float | None) -> str:
    """Mirror ``TimezoneHelper#timezone_name_from_offset``.

    Rails resolves ``ActiveSupport::TimeZone[offset].name`` from a
    float-degrees offset. We synthesise an ISO-8601 ``Etc/GMT±N`` zone
    name that Postgres' ``date_trunc`` accepts — same bucket math.
    """
    if offset is None:
        return "UTC"
    # Convert hours-offset to integer GMT zone. Postgres uses POSIX
    # convention (Etc/GMT+N is N hours WEST), so we invert the sign.
    try:
        hours = int(round(float(offset)))
    except (TypeError, ValueError):
        return "UTC"
    if hours == 0:
        return "UTC"
    return f"Etc/GMT{'+' if hours < 0 else '-'}{abs(hours)}"


async def count_timeseries(
    session: AsyncSession,
    *,
    account_id: int,
    metric: CountMetric,
    type: ScopeType,
    id: int | None,
    since: datetime | None,
    until: datetime | None,
    tz: str = "UTC",
) -> list[dict[str, Any]]:
    """Build the daily bucket list for a count-style metric."""
    if metric == "conversations_count":
        # Bucket by Conversation.created_at, scoped by type+id.
        bucket = _date_bucket(Conversation.created_at, tz)
        stmt = select(
            bucket.label("bucket"),
            sa_func.count(sa_func.distinct(Conversation.id)).label("value"),
        )
        stmt = _apply_conversation_scope(
            stmt, account_id=account_id, type=type, id=id
        )
        if since is not None:
            stmt = stmt.where(Conversation.created_at >= since)
        if until is not None:
            stmt = stmt.where(Conversation.created_at <= until)
        stmt = stmt.group_by(bucket).order_by(bucket)
        rows = list((await session.exec(stmt)).all())
        return _serialize(rows, with_count=False)

    if metric in ("incoming_messages_count", "outgoing_messages_count"):
        message_type = (
            MESSAGE_TYPE_INCOMING
            if metric == "incoming_messages_count"
            else MESSAGE_TYPE_OUTGOING
        )
        bucket = _date_bucket(Message.created_at, tz)
        stmt = select(
            bucket.label("bucket"),
            sa_func.count(sa_func.distinct(Message.id)).label("value"),
        )
        stmt = _apply_message_scope(
            stmt, account_id=account_id, type=type, id=id
        )
        stmt = stmt.where(Message.message_type == message_type)
        if since is not None:
            stmt = stmt.where(Message.created_at >= since)
        if until is not None:
            stmt = stmt.where(Message.created_at <= until)
        stmt = stmt.group_by(bucket).order_by(bucket)
        rows = list((await session.exec(stmt)).all())
        return _serialize(rows, with_count=False)

    # Remaining count metrics are over reporting_events.
    event_name = {
        "resolutions_count": "conversation_resolved",
        "bot_resolutions_count": "conversation_bot_resolved",
        "bot_handoffs_count": "conversation_bot_handoff",
    }[metric]

    bucket = _date_bucket(ReportingEvent.created_at, tz)
    stmt = select(
        bucket.label("bucket"),
        sa_func.count(sa_func.distinct(ReportingEvent.id)).label("value"),
    )
    stmt = _apply_reporting_event_scope(
        stmt, account_id=account_id, type=type, id=id
    )
    stmt = stmt.where(ReportingEvent.name == event_name)
    if since is not None:
        stmt = stmt.where(ReportingEvent.created_at >= since)
    if until is not None:
        stmt = stmt.where(ReportingEvent.created_at <= until)
    stmt = stmt.group_by(bucket).order_by(bucket)
    rows = list((await session.exec(stmt)).all())
    return _serialize(rows, with_count=False)


async def avg_timeseries(
    session: AsyncSession,
    *,
    account_id: int,
    metric: AvgMetric,
    type: ScopeType,
    id: int | None,
    since: datetime | None,
    until: datetime | None,
    tz: str = "UTC",
    business_hours: bool = False,
) -> list[dict[str, Any]]:
    """Daily buckets of ``avg(value)`` for a ReportingEvent-backed
    average metric. Each bucket also carries ``count`` so the
    dashboard can compute response-rate denominators."""
    event_name = _AVG_TO_EVENT[metric]
    value_col = (
        ReportingEvent.value_in_business_hours
        if business_hours
        else ReportingEvent.value
    )
    bucket = _date_bucket(ReportingEvent.created_at, tz)
    stmt = select(
        bucket.label("bucket"),
        sa_func.avg(cast(value_col, Float)).label("value"),
        sa_func.count(sa_func.distinct(ReportingEvent.id)).label("count"),
    )
    stmt = _apply_reporting_event_scope(
        stmt, account_id=account_id, type=type, id=id
    )
    stmt = stmt.where(ReportingEvent.name == event_name)
    if since is not None:
        stmt = stmt.where(ReportingEvent.created_at >= since)
    if until is not None:
        stmt = stmt.where(ReportingEvent.created_at <= until)
    stmt = stmt.group_by(bucket).order_by(bucket)
    rows = list((await session.exec(stmt)).all())
    return _serialize(rows, with_count=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _date_bucket(column: Any, tz: str):
    """Build the ``date_trunc('day', column AT TIME ZONE tz)`` expression.

    Postgres' ``AT TIME ZONE`` flips the column from timestamptz to
    timestamp in the given zone; ``date_trunc('day', ...)`` then snaps
    to midnight in that zone. The output is a timestamp at the bucket
    boundary — :func:`_serialize` casts back to unix seconds.
    """
    return sa_func.date_trunc(
        "day", sa_func.timezone(tz, column)
    )


def _serialize(
    rows: list[Any], *, with_count: bool
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        bucket = row[0]
        value = row[1]
        # The bucket comes back as a naive datetime (Postgres strips
        # the tz after ``date_trunc``). Treat it as UTC seconds —
        # matches Rails' ``event_date.in_time_zone(timezone).to_i``
        # because both sides agree the bucket boundary is the midnight
        # moment.
        if bucket is None:
            timestamp = 0
        else:
            if isinstance(bucket, datetime):
                # tz-naive → assume UTC
                if bucket.tzinfo is None:
                    bucket = bucket.replace(tzinfo=UTC)
                timestamp = int(bucket.timestamp())
            else:
                timestamp = 0
        entry: dict[str, Any] = {
            "value": float(value) if value is not None else 0,
            "timestamp": timestamp,
        }
        if with_count:
            entry["count"] = int(row[2] or 0)
        out.append(entry)
    return out


__all__ = [
    "ALL_METRICS",
    "AvgMetric",
    "CountMetric",
    "avg_timeseries",
    "count_timeseries",
    "timezone_from_offset",
]
