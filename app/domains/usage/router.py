"""Spend endpoints (F6), admin only:

  * ``GET  /api/v1/accounts/{id}/usage?month=AAAA-MM`` — the month's summary.
  * ``POST /api/v1/accounts/{id}/usage/whatsapp/sync?month=AAAA-MM`` — pull
    that month's WhatsApp costs from Meta now (the worker does it every six
    hours for the last days).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.usage.limits import KINDS, limits_status, set_limit
from app.domains.usage.service import month_bounds, month_summary
from app.domains.usage.whatsapp import cloud_numbers, sync_costs

router = APIRouter(prefix="/api/v1/accounts/{account_id}/usage", tags=["usage"])


@router.get("")
async def usage_summary(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    month: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    assert ctx.account.id is not None
    return await month_summary(session, account_id=ctx.account.id, month=month)


@router.post("/whatsapp/sync")
async def sync_whatsapp(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    month: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    assert ctx.account.id is not None
    first, last, _, _ = month_bounds(month)
    last = min(last, datetime.now(UTC).date())
    errors: list[dict[str, Any]] = []
    for channel, inbox in await cloud_numbers(session, ctx.account.id):
        try:
            async with session.begin_nested():
                await sync_costs(session, channel=channel, inbox=inbox, since=first, until=last)
        except ChatwootHTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            errors.append({"inbox_id": inbox.id, "name": inbox.name, "message": detail.get("message")})
    summary = await month_summary(session, account_id=ctx.account.id, month=month)
    await session.commit()
    return {**summary, "sync_errors": errors}


class LimitBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    monthly_limit: float | None = None


@router.get("/limits")
async def get_limits(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    return {"limits": await limits_status(session, ctx.account.id)}


@router.put("/limits/{kind}")
async def put_limit(
    kind: Annotated[str, Path()],
    body: LimitBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Set a monthly cap (``null`` removes it). In the WhatsApp account's
    currency for ``whatsapp``, in USD for ``ai``."""
    assert ctx.account.id is not None
    if kind not in KINDS:
        raise ChatwootHTTPException(status_code=404, detail={"error": "Resource could not be found"})
    if body.monthly_limit is not None and not (0 <= body.monthly_limit <= 1_000_000):
        raise ChatwootHTTPException(
            status_code=422, detail={"message": "El tope va entre 0 y 1.000.000."}
        )
    await set_limit(session, ctx.account.id, kind, body.monthly_limit)
    limits = await limits_status(session, ctx.account.id)
    await session.commit()
    return {"limits": limits}


__all__ = ["router"]
