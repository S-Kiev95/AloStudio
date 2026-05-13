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

router = APIRouter(
    prefix="/api/v2/accounts/{account_id}/reports",
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
@router.get("/summary")
async def summary(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    type: str | None = Query(None),
    id: int | None = Query(None),
    since: str | None = Query(None),
    until: str | None = Query(None),
    business_hours: str | None = Query(None),
    timezone_offset: str | None = Query(None),  # noqa: ARG001 — for parity
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


__all__ = ["router"]
