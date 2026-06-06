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

Bucketing: we snap to local midnight for a fixed UTC offset (in
minutes, so sub-hour zones work) and emit the true unix seconds of that
boundary — see :func:`_date_bucket`. Matches Rails'
``group_by_period(..., time_zone: tz)`` + ``.to_i``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import (
    Float,
    cast,
)
from sqlalchemy import (
    func as sa_func,
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


async def count_timeseries(
    session: AsyncSession,
    *,
    account_id: int,
    metric: CountMetric,
    type: ScopeType,
    id: int | None,
    since: datetime | None,
    until: datetime | None,
    offset_minutes: int = 0,
) -> list[dict[str, Any]]:
    """Build the daily bucket list for a count-style metric."""
    if metric == "conversations_count":
        # Bucket by Conversation.created_at, scoped by type+id.
        bucket = _date_bucket(Conversation.created_at, offset_minutes)
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
        bucket = _date_bucket(Message.created_at, offset_minutes)
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

    bucket = _date_bucket(ReportingEvent.created_at, offset_minutes)
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
    offset_minutes: int = 0,
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
    bucket = _date_bucket(ReportingEvent.created_at, offset_minutes)
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
def _date_bucket(column: Any, offset_minutes: int):
    """Build the daily-bucket expression as **true unix seconds of the
    local midnight**, for a fixed UTC offset in minutes.

    Three steps, all in SQL:

      1. ``timezone(offset, col)`` — convert the ``timestamptz`` column
         to the wall-clock time at ``offset``, as a naive timestamp.
      2. ``date_trunc('day', …)`` — snap to local midnight (naive).
      3. ``timezone(offset, …)`` — re-interpret that naive midnight as
         being at ``offset``, yielding the absolute ``timestamptz`` of
         the bucket boundary; ``extract(epoch …)`` gives unix seconds.

    Using a numeric **offset in minutes** (not an ``Etc/GMT±N`` zone
    name) preserves sub-hour offsets — IST (+5:30), Nepal (+5:45),
    Newfoundland (-3:30) bucket at the correct local midnight. And
    applying the offset on the way out (step 3) emits the *true*
    midnight-in-offset epoch — matching Rails' ``…in_time_zone(tz).to_i``
    — so a client in that offset renders the correct day. (The previous
    version rounded to whole hours AND labelled the naive midnight as
    UTC, which shifted the chart's day-axis by the offset for non-UTC
    accounts.)

    ``offset_minutes`` is a server-derived int (parsed from the
    ``timezone_offset`` query param), so inlining it as an interval
    literal carries no injection risk.
    """
    iv = sa_func.make_interval(0, 0, 0, 0, 0, offset_minutes)
    local_naive = sa_func.timezone(iv, column)
    day_naive = sa_func.date_trunc("day", local_naive)
    boundary_tz = sa_func.timezone(iv, day_naive)
    return sa_func.extract("epoch", boundary_tz)


def _serialize(
    rows: list[Any], *, with_count: bool
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        # ``row[0]`` is already the bucket boundary in unix seconds
        # (see :func:`_date_bucket`) — no datetime reconstruction needed.
        bucket = row[0]
        value = row[1]
        timestamp = int(bucket) if bucket is not None else 0
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
]
