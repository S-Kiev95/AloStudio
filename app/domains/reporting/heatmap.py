"""Conversation-traffic heatmap — conversations created per (date, hour).

Ports ``Api::V2::Accounts::HeatmapHelper#generate_conversations_heatmap_report``.
Chatwoot returns a spreadsheet-shaped 2D array; we return a cleaner per-date
shape (``[{date, hours: [24 counts]}]``) the dashboard renders as a heatmap.
Bucketing happens at the caller's UTC offset (in minutes) so the local
hour-of-day axis is correct — same offset handling as
``timeseries._date_bucket``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Date, Integer
from sqlalchemy import func as sa_func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Conversation


async def conversation_traffic_heatmap(
    session: AsyncSession,
    *,
    account_id: int,
    since: datetime | None,
    until: datetime | None,
    offset_minutes: int = 0,
) -> list[dict[str, Any]]:
    """Return ``[{date, hours: [24 ints]}, ...]`` ordered by date.

    Each row's ``hours[k]`` is the number of conversations created in local
    hour ``k`` on that local date.
    """
    iv = sa_func.make_interval(0, 0, 0, 0, 0, offset_minutes)
    local = sa_func.timezone(iv, Conversation.created_at)
    local_date = sa_func.cast(local, Date)
    local_hour = sa_func.cast(sa_func.extract("hour", local), Integer)

    stmt = select(local_date, local_hour, sa_func.count()).where(
        Conversation.account_id == account_id
    )
    if since is not None:
        stmt = stmt.where(Conversation.created_at >= since)
    if until is not None:
        stmt = stmt.where(Conversation.created_at < until)
    stmt = stmt.group_by(local_date, local_hour).order_by(
        local_date, local_hour
    )
    rows = (await session.exec(stmt)).all()

    by_date: dict[str, list[int]] = {}
    for row in rows:
        date_str = row[0].isoformat()
        hours = by_date.setdefault(date_str, [0] * 24)
        hours[int(row[1])] = int(row[2])
    return [{"date": ds, "hours": by_date[ds]} for ds in sorted(by_date)]


__all__ = ["conversation_traffic_heatmap"]
