"""V2 reports HTTP endpoints.

Ports ``Api::V2::Accounts::ReportsController`` (partial — see
``PLAN.phase7.md`` for the deferred set).

Route map (Phase 7.2 — summary + live conversations):

  * ``GET /api/v2/accounts/{id}/reports/summary``
  * ``GET /api/v2/accounts/{id}/reports/conversations?type=conversation``

The ``type`` query param routes between the two surfaces in
Chatwoot's ``/reports/conversations`` action:

  * ``type=conversation`` → live counters for the account scope.
  * any other type → ``agent_metrics`` (Phase 7.4 wiring).

Authorisation: ``check_authorization`` calls ``ReportPolicy#view?``
which permits both administrator and agent. Mirrors ``account_context``.
"""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.domains.reporting.service import (
    ScopeType,
    build_summary,
    live_conversation_metrics,
    parse_unix_range,
    previous_window,
)
from app.domains.reporting.summary_builders import (
    build_agent_summary,
    build_inbox_summary,
    build_label_summary,
    build_team_summary,
)
from app.domains.reporting.timeseries import (
    ALL_METRICS,
    avg_timeseries,
    count_timeseries,
)

router = APIRouter(
    prefix="/api/v2/accounts/{account_id}/reports",
    tags=["reports"],
)

# Live reports live under a separate prefix in Chatwoot
# (``/api/v2/accounts/{id}/live_reports/...``). One Python module
# exports both — keeps the service/timeseries code paths
# co-located with the rest of the reporting surface.
live_reports_router = APIRouter(
    prefix="/api/v2/accounts/{account_id}/live_reports",
    tags=["reports"],
)

# Per-entity summary reports — agent/team/inbox/label/channel.
summary_reports_router = APIRouter(
    prefix="/api/v2/accounts/{account_id}/summary_reports",
    tags=["reports"],
)


_SCOPE_TYPES = ("account", "inbox", "agent", "team", "label")


def _coerce_type(raw: str | None) -> ScopeType:
    if raw is None or raw == "" or raw not in _SCOPE_TYPES:
        return cast(ScopeType, "account")
    return cast(ScopeType, raw)


def _coerce_bool(raw: str | None) -> bool:
    """Mirrors Rails' ``ActiveModel::Type::Boolean.new.cast`` —
    accepts "1", "true", "TRUE" as truthy."""
    if raw is None:
        return False
    return raw.lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
_AVG_METRICS = {
    "avg_first_response_time",
    "avg_resolution_time",
    "reply_time",
}


@router.get("")
async def timeseries(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    metric: str | None = Query(None),
    type: str | None = Query(None),
    id: int | None = Query(None),
    since: str | None = Query(None),
    until: str | None = Query(None),
    timezone_offset: str | None = Query(None),
    business_hours: str | None = Query(None),
) -> list[dict[str, Any]]:
    """``GET /reports?metric=...`` — daily buckets for the line chart.

    Returns an empty list when ``metric`` isn't on the allow-list
    (mirrors Rails' ``Rails.logger.error + return {}`` fallback)."""
    assert ctx.account.id is not None
    if metric is None or metric not in ALL_METRICS:
        return []
    scope_type = _coerce_type(type)
    cur_since, cur_until = parse_unix_range(since, until)
    try:
        offset_float = float(timezone_offset) if timezone_offset else None
    except (TypeError, ValueError):
        offset_float = None
    # Carry the offset in MINUTES so sub-hour zones (IST +5:30, etc.)
    # bucket at the correct local midnight (see timeseries._date_bucket).
    offset_minutes = round(offset_float * 60) if offset_float is not None else 0
    bh = _coerce_bool(business_hours)
    if metric in _AVG_METRICS:
        return await avg_timeseries(
            session,
            account_id=ctx.account.id,
            metric=cast(Any, metric),
            type=scope_type,
            id=id,
            since=cur_since,
            until=cur_until,
            offset_minutes=offset_minutes,
            business_hours=bh,
        )
    return await count_timeseries(
        session,
        account_id=ctx.account.id,
        metric=cast(Any, metric),
        type=scope_type,
        id=id,
        since=cur_since,
        until=cur_until,
        offset_minutes=offset_minutes,
    )


@router.get("/summary")
async def summary(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    type: str | None = Query(None),
    id: int | None = Query(None),
    since: str | None = Query(None),
    until: str | None = Query(None),
    business_hours: str | None = Query(None),
    timezone_offset: str | None = Query(None),
) -> dict[str, Any]:
    """``GET /reports/summary`` — the dashboard cards.

    The wire shape merges the current-window summary with the symmetric
    prior window under ``previous``. Mirrors
    ``ReportsController#summary`` exactly."""
    assert ctx.account.id is not None
    scope_type = _coerce_type(type)
    bh = _coerce_bool(business_hours)
    cur_since, cur_until = parse_unix_range(since, until)
    prev_since, prev_until = previous_window(cur_since, cur_until)

    current = await build_summary(
        session,
        account_id=ctx.account.id,
        type=scope_type,
        id=id,
        since=cur_since,
        until=cur_until,
        business_hours=bh,
    )
    previous = await build_summary(
        session,
        account_id=ctx.account.id,
        type=scope_type,
        id=id,
        since=prev_since,
        until=prev_until,
        business_hours=bh,
    )
    return {**current, "previous": previous}


@router.get("/conversations")
async def conversations_metrics(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    type: str | None = Query(None),
) -> dict[str, int]:
    """``GET /reports/conversations?type=conversation`` — current-state
    counters used by the dashboard "live" widget when ``type=conversation``.

    Per-agent breakdowns (``type=Agent`` etc.) lands in 7.4. For now
    other types return the account-wide snapshot.
    """
    assert ctx.account.id is not None
    # Rails: ``return head :unprocessable_entity if params[:type].blank?``.
    if type is None or type == "":
        raise ChatwootHTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": "type is required"},
        )
    return await live_conversation_metrics(
        session,
        account_id=ctx.account.id,
        type=cast(ScopeType, "account"),
        id=None,
    )


# ---------------------------------------------------------------------------
# Live reports
# ---------------------------------------------------------------------------
_LIVE_GROUP_BY = {"team_id", "assignee_id"}


@live_reports_router.get("/conversation_metrics")
async def live_conversation_metrics_endpoint(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    team_id: int | None = Query(None),
) -> dict[str, int]:
    """``GET /live_reports/conversation_metrics`` — current snapshot.

    Mirrors Chatwoot's controller: ``{open, unattended, unassigned, pending}``
    counters, optionally filtered to one team."""
    assert ctx.account.id is not None
    scope: ScopeType = "team" if team_id is not None else "account"
    return await live_conversation_metrics(
        session,
        account_id=ctx.account.id,
        type=scope,
        id=team_id,
    )


@live_reports_router.get("/grouped_conversation_metrics")
async def grouped_conversation_metrics(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    group_by: str | None = Query(None),
    team_id: int | None = Query(None),
) -> Any:
    """``GET /live_reports/grouped_conversation_metrics?group_by=...``

    Returns one row per group: ``{open, unattended, unassigned, <group_by>}``.
    ``group_by`` is required and must be ``team_id`` or ``assignee_id``
    — matches Rails' explicit allow-list (422 otherwise).
    """
    assert ctx.account.id is not None
    if group_by not in _LIVE_GROUP_BY:
        raise ChatwootHTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"error": "invalid group_by"},
        )
    from sqlalchemy import case as sa_case
    from sqlalchemy import func as sa_func
    from sqlmodel import select

    from app.domains.conversations.models import (
        CONVERSATION_STATUS_OPEN,
        Conversation,
    )

    group_col = (
        Conversation.team_id
        if group_by == "team_id"
        else Conversation.assignee_id
    )
    stmt = (
        select(
            group_col.label("group_id"),
            sa_func.count(sa_func.distinct(Conversation.id)).label("open"),
            sa_func.sum(
                sa_case(
                    (Conversation.first_reply_created_at.is_(None), 1),  # type: ignore[union-attr]
                    else_=0,
                )
            ).label("unattended"),
            sa_func.sum(
                sa_case(
                    (Conversation.assignee_id.is_(None), 1),  # type: ignore[union-attr]
                    else_=0,
                )
            ).label("unassigned"),
        )
        .where(Conversation.account_id == ctx.account.id)
        .where(Conversation.status == CONVERSATION_STATUS_OPEN)
        .group_by(group_col)
    )
    if team_id is not None:
        stmt = stmt.where(Conversation.team_id == team_id)
    rows = list((await session.exec(stmt)).all())
    out: list[dict[str, Any]] = []
    for row in rows:
        gid = row[0]
        if gid is None:
            continue  # drop nulls — matches Rails' grouped count behaviour
        out.append(
            {
                "open": int(row[1] or 0),
                "unattended": int(row[2] or 0),
                "unassigned": int(row[3] or 0),
                group_by: gid,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Summary reports — per-entity
# ---------------------------------------------------------------------------
async def _entity_summary_args(
    ctx: AccountContext,
    since: str | None,
    until: str | None,
    business_hours: str | None,
):
    assert ctx.account.id is not None
    cur_since, cur_until = parse_unix_range(since, until)
    return {
        "account_id": ctx.account.id,
        "since": cur_since,
        "until": cur_until,
        "business_hours": _coerce_bool(business_hours),
    }


@summary_reports_router.get("/agent")
async def agent_summary(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    since: str | None = Query(None),
    until: str | None = Query(None),
    business_hours: str | None = Query(None),
) -> list[dict[str, Any]]:
    args = await _entity_summary_args(ctx, since, until, business_hours)
    return await build_agent_summary(session, **args)


@summary_reports_router.get("/team")
async def team_summary(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    since: str | None = Query(None),
    until: str | None = Query(None),
    business_hours: str | None = Query(None),
) -> list[dict[str, Any]]:
    args = await _entity_summary_args(ctx, since, until, business_hours)
    return await build_team_summary(session, **args)


@summary_reports_router.get("/inbox")
async def inbox_summary(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    since: str | None = Query(None),
    until: str | None = Query(None),
    business_hours: str | None = Query(None),
) -> list[dict[str, Any]]:
    args = await _entity_summary_args(ctx, since, until, business_hours)
    return await build_inbox_summary(session, **args)


@summary_reports_router.get("/label")
async def label_summary(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    since: str | None = Query(None),
    until: str | None = Query(None),
    business_hours: str | None = Query(None),
) -> list[dict[str, Any]]:
    args = await _entity_summary_args(ctx, since, until, business_hours)
    return await build_label_summary(session, **args)


__all__ = [
    "live_reports_router",
    "router",
    "summary_reports_router",
]
