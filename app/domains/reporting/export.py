"""Summary-report export tables.

Turns the per-entity summary builders into a ``(headers, rows)`` grid
the CSV / XLSX serialisers can render.

Agent rows carry only a ``user_id`` (the builder mirrors Rails, which
resolves the display name client-side), so we join ``User`` to fill the
name here. Team / inbox / label rows already carry their own ``name``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.reporting.summary_builders import (
    build_ad_summary,
    build_agent_summary,
    build_inbox_summary,
    build_label_summary,
    build_team_summary,
)
from app.domains.users.models import User

EXPORT_SCOPES: tuple[str, ...] = ("agent", "team", "inbox", "label", "ad")

_BUILDERS = {
    "agent": build_agent_summary,
    "team": build_team_summary,
    "inbox": build_inbox_summary,
    "label": build_label_summary,
    "ad": build_ad_summary,
}

_HEADERS = [
    "ID",
    "Nombre",
    "Conversaciones",
    "Resueltas",
    "Resolución promedio (s)",
    "Primera respuesta promedio (s)",
    "Respuesta promedio (s)",
]


async def _agent_names(
    session: AsyncSession, ids: list[int]
) -> dict[int, str]:
    if not ids:
        return {}
    users = (
        await session.exec(select(User).where(User.id.in_(ids)))  # type: ignore[union-attr]
    ).all()
    return {u.id: (u.name or "") for u in users}


def _round(value: Any) -> float:
    return round(float(value or 0), 1)


async def build_summary_export(
    session: AsyncSession,
    *,
    account_id: int,
    scope: str,
    since: datetime | None,
    until: datetime | None,
    business_hours: bool = False,
) -> tuple[list[str], list[list[Any]]]:
    """Return ``(headers, rows)`` for the given summary ``scope``."""
    summary = await _BUILDERS[scope](
        session,
        account_id=account_id,
        since=since,
        until=until,
        business_hours=business_hours,
    )
    if scope == "agent":
        names = await _agent_names(session, [r["id"] for r in summary])
    else:
        names = {r["id"]: (r.get("name") or "") for r in summary}
    table: list[list[Any]] = [
        [
            r["id"],
            names.get(r["id"], ""),
            r["conversations_count"],
            r["resolved_conversations_count"],
            _round(r["avg_resolution_time"]),
            _round(r["avg_first_response_time"]),
            _round(r["avg_reply_time"]),
        ]
        for r in summary
    ]
    return list(_HEADERS), table


__all__ = ["EXPORT_SCOPES", "build_summary_export"]
