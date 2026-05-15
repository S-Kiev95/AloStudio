"""Working hours HTTP endpoints.

Ports ``Api::V1::Accounts::WorkingHoursController`` + the inbox-side
bulk update from ``InboxesController#update_inbox_working_hours``.

Route map (admin-only):

  * ``PATCH /api/v1/accounts/{id}/working_hours/{id}``
    — Update a single row by id.
  * ``GET   /api/v1/accounts/{id}/inboxes/{iid}/working_hours``
    — Read the 7-row schedule for an inbox.
  * ``PATCH /api/v1/accounts/{id}/inboxes/{iid}/working_hours``
    — Bulk update the schedule (array of 7 dicts keyed on
    ``day_of_week``). Mirrors the bulk-update branch of Chatwoot's
    ``InboxesController#update``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.models import Inbox
from app.domains.working_hours.presenters import present_working_hour
from app.domains.working_hours.schemas import WorkingHourEnvelope
from app.domains.working_hours.service import (
    bulk_update_for_inbox,
    fetch_account_working_hour,
    list_for_inbox,
    update_working_hour,
)

# Single-row update — the literal Chatwoot route.
single_router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/working_hours",
    tags=["working-hours"],
)

# Inbox-scoped read + bulk update — the dashboard's main entry.
inbox_router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/inboxes/{inbox_id}",
    tags=["working-hours"],
)


async def _find_inbox(
    session: AsyncSession, *, account_id: int, inbox_id: int
) -> Inbox:
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.id == inbox_id, Inbox.account_id == account_id
            )
        )
    ).first()
    if inbox is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return inbox


@single_router.patch("/{working_hour_id}")
async def update_one(
    working_hour_id: Annotated[int, Path()],
    payload: WorkingHourEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    row = await fetch_account_working_hour(
        session,
        account_id=ctx.account.id,
        working_hour_id=working_hour_id,
    )
    if row is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    body = payload.working_hour.model_dump(exclude_unset=True)
    updated = await update_working_hour(
        session, working_hour=row, payload=body
    )
    return present_working_hour(updated)


@inbox_router.get("/working_hours")
async def index_for_inbox(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    inbox = await _find_inbox(
        session, account_id=ctx.account.id, inbox_id=inbox_id
    )
    rows = await list_for_inbox(session, inbox_id=inbox.id)
    return [present_working_hour(r) for r in rows]


@inbox_router.patch("/working_hours")
async def bulk_update_endpoint(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    body: Annotated[dict[str, Any], Body()],
) -> list[dict[str, Any]]:
    """Accepts ``{working_hours: [{...}, {...}, ...]}`` and bulk
    updates the inbox's 7 rows by ``day_of_week``."""
    assert ctx.account.id is not None
    inbox = await _find_inbox(
        session, account_id=ctx.account.id, inbox_id=inbox_id
    )
    schedule = body.get("working_hours")
    if not isinstance(schedule, list):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "working_hours must be an array"},
        )
    rows = await bulk_update_for_inbox(
        session, inbox=inbox, schedule=schedule
    )
    return [present_working_hour(r) for r in rows]


__all__ = ["inbox_router", "single_router"]
