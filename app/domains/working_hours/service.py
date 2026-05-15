"""WorkingHour service — defaults, validation, schedule mutations,
business-hours arithmetic.

Ported from:
  reference/chatwoot/app/models/working_hour.rb
  reference/chatwoot/app/models/concerns/out_of_offisable.rb
  reference/chatwoot/app/controllers/api/v1/accounts/working_hours_controller.rb
  reference/chatwoot/app/helpers/reporting_event_helper.rb (business_hours)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone as _timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.models import Inbox
from app.domains.working_hours.models import (
    OFFISABLE_ATTRS,
    WorkingHour,
)

log = logging.getLogger(__name__)

# Mirror Rails' default schedule from ``create_default_working_hours``:
# Sun + Sat closed, Mon-Fri 09:00→17:00.
_DEFAULT_SCHEDULE: tuple[dict[str, Any], ...] = (
    {"day_of_week": 0, "closed_all_day": True, "open_all_day": False},
    {
        "day_of_week": 1,
        "open_hour": 9,
        "open_minutes": 0,
        "close_hour": 17,
        "close_minutes": 0,
        "open_all_day": False,
        "closed_all_day": False,
    },
    {
        "day_of_week": 2,
        "open_hour": 9,
        "open_minutes": 0,
        "close_hour": 17,
        "close_minutes": 0,
        "open_all_day": False,
        "closed_all_day": False,
    },
    {
        "day_of_week": 3,
        "open_hour": 9,
        "open_minutes": 0,
        "close_hour": 17,
        "close_minutes": 0,
        "open_all_day": False,
        "closed_all_day": False,
    },
    {
        "day_of_week": 4,
        "open_hour": 9,
        "open_minutes": 0,
        "close_hour": 17,
        "close_minutes": 0,
        "open_all_day": False,
        "closed_all_day": False,
    },
    {
        "day_of_week": 5,
        "open_hour": 9,
        "open_minutes": 0,
        "close_hour": 17,
        "close_minutes": 0,
        "open_all_day": False,
        "closed_all_day": False,
    },
    {"day_of_week": 6, "closed_all_day": True, "open_all_day": False},
)


# ---------------------------------------------------------------------------
# Validation + defaults
# ---------------------------------------------------------------------------
def _validate_hour(value: Any, *, field: str, max_val: int) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or value < 0 or value > max_val:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": f"{field} is invalid"},
        )
    return value


def _normalise_one(raw: dict[str, Any]) -> dict[str, Any]:
    """Mirror ``before_validation :ensure_open_all_day_hours``."""
    cleaned: dict[str, Any] = {
        key: raw.get(key) for key in OFFISABLE_ATTRS if key in raw
    }
    if bool(cleaned.get("open_all_day")) and bool(cleaned.get("closed_all_day")):
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": "open_all_day and closed_all_day cannot be true at the same time"
            },
        )
    if cleaned.get("open_all_day"):
        cleaned["open_hour"] = 0
        cleaned["open_minutes"] = 0
        cleaned["close_hour"] = 23
        cleaned["close_minutes"] = 59
    if not cleaned.get("closed_all_day"):
        # Validate ranges + close-after-open when the day has explicit hours.
        oh = _validate_hour(cleaned.get("open_hour"), field="open_hour", max_val=23)
        om = _validate_hour(
            cleaned.get("open_minutes"), field="open_minutes", max_val=59
        )
        ch = _validate_hour(
            cleaned.get("close_hour"), field="close_hour", max_val=23
        )
        cm = _validate_hour(
            cleaned.get("close_minutes"), field="close_minutes", max_val=59
        )
        if (
            oh is not None
            and om is not None
            and ch is not None
            and cm is not None
        ):
            if oh * 60 + om >= ch * 60 + cm:
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={
                        "message": "Closing time cannot be before opening time"
                    },
                )
    return cleaned


# ---------------------------------------------------------------------------
# Defaults (after_create inbox hook)
# ---------------------------------------------------------------------------
async def create_default_working_hours(
    session: AsyncSession, *, inbox: Inbox
) -> list[WorkingHour]:
    """Mirror ``OutOfOffisable#create_default_working_hours``."""
    rows: list[WorkingHour] = []
    for tmpl in _DEFAULT_SCHEDULE:
        row = WorkingHour(
            inbox_id=inbox.id,
            account_id=inbox.account_id,
            day_of_week=tmpl["day_of_week"],
            closed_all_day=bool(tmpl.get("closed_all_day", False)),
            open_all_day=bool(tmpl.get("open_all_day", False)),
            open_hour=tmpl.get("open_hour"),
            open_minutes=tmpl.get("open_minutes"),
            close_hour=tmpl.get("close_hour"),
            close_minutes=tmpl.get("close_minutes"),
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    for r in rows:
        await session.refresh(r)
    return rows


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------
async def list_for_inbox(
    session: AsyncSession, *, inbox_id: int
) -> list[WorkingHour]:
    stmt = (
        select(WorkingHour)
        .where(WorkingHour.inbox_id == inbox_id)
        .order_by(WorkingHour.day_of_week.asc())  # type: ignore[attr-defined]
    )
    return list((await session.exec(stmt)).all())


async def fetch_account_working_hour(
    session: AsyncSession, *, account_id: int, working_hour_id: int
) -> WorkingHour | None:
    return (
        await session.exec(
            select(WorkingHour).where(
                WorkingHour.id == working_hour_id,
                WorkingHour.account_id == account_id,
            )
        )
    ).first()


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------
async def update_working_hour(
    session: AsyncSession,
    *,
    working_hour: WorkingHour,
    payload: dict[str, Any],
) -> WorkingHour:
    """Single-row update (mirrors ``PATCH /working_hours/{id}``)."""
    cleaned = _normalise_one(payload)
    for key, value in cleaned.items():
        if key in OFFISABLE_ATTRS:
            setattr(working_hour, key, value)
    session.add(working_hour)
    await session.flush()
    await session.refresh(working_hour)
    return working_hour


async def bulk_update_for_inbox(
    session: AsyncSession,
    *,
    inbox: Inbox,
    schedule: list[dict[str, Any]],
) -> list[WorkingHour]:
    """Mirror ``OutOfOffisable#update_working_hours``.

    Accepts an array of {day_of_week + offisable attrs} dicts and
    updates each row matched by day_of_week. Unknown days are
    silently ignored (matches Rails' ``find_by`` returning nil)."""
    rows = await list_for_inbox(session, inbox_id=inbox.id)
    by_day: dict[int, WorkingHour] = {r.day_of_week: r for r in rows}
    for entry in schedule:
        if not isinstance(entry, dict):
            continue
        day = entry.get("day_of_week")
        if not isinstance(day, int) or day not in by_day:
            continue
        cleaned = _normalise_one(entry)
        for key, value in cleaned.items():
            if key in OFFISABLE_ATTRS:
                setattr(by_day[day], key, value)
        session.add(by_day[day])
    await session.flush()
    # Re-fetch in stable order for the return.
    return await list_for_inbox(session, inbox_id=inbox.id)


# ---------------------------------------------------------------------------
# Business-hours arithmetic
# ---------------------------------------------------------------------------
def _resolve_zone(tz_name: str | None) -> _timezone:
    if not tz_name:
        return _timezone.utc
    try:
        return ZoneInfo(tz_name)  # type: ignore[return-value]
    except ZoneInfoNotFoundError:
        return _timezone.utc


def _row_intervals_for_day(row: WorkingHour) -> tuple[int, int] | None:
    """Return ``(open_minute, close_minute)`` for a single day's
    schedule, or None when the day is fully closed."""
    if row.closed_all_day:
        return None
    if row.open_all_day:
        return (0, 24 * 60)
    if (
        row.open_hour is None
        or row.open_minutes is None
        or row.close_hour is None
        or row.close_minutes is None
    ):
        return None
    return (
        row.open_hour * 60 + row.open_minutes,
        row.close_hour * 60 + row.close_minutes,
    )


def business_hours_between(
    *,
    rows: list[WorkingHour],
    timezone_name: str | None,
    start: datetime | None,
    end: datetime | None,
) -> float:
    """Total seconds inside working hours between ``start`` and ``end``.

    Mirrors ``ReportingEventHelper#business_hours``. Returns 0.0 when
    either bound is missing, the inbox lacks a schedule, or the
    interval spans backward.

    Algorithm: convert start/end to the inbox's timezone, then walk
    each calendar-day in the range and intersect that day's
    ``[start-of-day .. end-of-day]`` window with the configured
    schedule for ``day_of_week``. Sum the per-day intersections in
    seconds.
    """
    if start is None or end is None or not rows:
        return 0.0
    if end <= start:
        return 0.0

    zone = _resolve_zone(timezone_name)
    by_day: dict[int, WorkingHour] = {r.day_of_week: r for r in rows}
    cursor = start.astimezone(zone)
    end_local = end.astimezone(zone)

    total_seconds = 0.0
    # Walk day boundaries until we pass ``end_local``.
    while cursor < end_local:
        midnight = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
        next_midnight = midnight.replace()
        # advance by 1 day (handles DST by adding 24h then snapping
        # to the local midnight — acceptable approximation for a v1
        # business-hours math; DST audits defer to Phase 10).
        from datetime import timedelta

        next_midnight = midnight + timedelta(days=1)
        # day_of_week: Python Mon=0..Sun=6; Chatwoot Sun=0..Sat=6.
        dow_py = midnight.weekday()  # Mon=0
        dow_cw = (dow_py + 1) % 7  # Sun=0
        row = by_day.get(dow_cw)
        if row is not None:
            interval = _row_intervals_for_day(row)
            if interval is not None:
                open_m, close_m = interval
                day_open = midnight + timedelta(minutes=open_m)
                day_close = midnight + timedelta(minutes=close_m)
                window_start = max(cursor, day_open)
                window_end = min(end_local, day_close)
                if window_end > window_start:
                    total_seconds += (
                        window_end - window_start
                    ).total_seconds()
        cursor = next_midnight
    return float(total_seconds)


__all__ = [
    "OFFISABLE_ATTRS",
    "WorkingHour",
    "bulk_update_for_inbox",
    "business_hours_between",
    "create_default_working_hours",
    "fetch_account_working_hour",
    "list_for_inbox",
    "update_working_hour",
]
