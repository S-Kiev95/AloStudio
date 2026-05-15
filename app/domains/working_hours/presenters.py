"""Wire-shape presenter for WorkingHour."""

from __future__ import annotations

from typing import Any

from app.domains.working_hours.models import WorkingHour


def present_working_hour(row: WorkingHour) -> dict[str, Any]:
    return {
        "id": row.id,
        "inbox_id": row.inbox_id,
        "account_id": row.account_id,
        "day_of_week": row.day_of_week,
        "closed_all_day": row.closed_all_day,
        "open_all_day": row.open_all_day,
        "open_hour": row.open_hour,
        "open_minutes": row.open_minutes,
        "close_hour": row.close_hour,
        "close_minutes": row.close_minutes,
    }


__all__ = ["present_working_hour"]
