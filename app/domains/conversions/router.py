"""Conversions API endpoints (F17), administrators only.

Route map, under ``/api/v1/accounts/{account_id}/conversions``:
  * ``GET  /settings``                     — on/off, currency, rules, and each
    WhatsApp number with its dataset
  * ``PUT  /settings``                     — ``{enabled, currency, rules?}``
  * ``POST /inboxes/{inbox_id}/dataset``   — ask Meta for the number's dataset
  * ``GET  /events``                       — the latest events and how they went

Errors carry ``code`` (``conversions.<code>``) for the panel to translate;
Meta's own words, when it refused, go in ``message``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.conversions import client, service
from app.domains.inboxes.models import CHANNEL_TYPE_WHATSAPP, Inbox

router = APIRouter(prefix="/api/v1/accounts/{account_id}/conversions", tags=["conversions"])

_NOT_FOUND = {"error": "Resource could not be found"}


class SettingsBody(BaseModel):
    enabled: bool
    currency: str = "USD"
    rules: dict[str, Any] | None = None


def _account_id(ctx: AccountContext) -> int:
    assert ctx.account.id is not None
    return ctx.account.id


def _fail(status_code: int, code: str, message: str | None = None) -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=status_code,
        detail={"message": message or code, "code": f"conversions.{code}"},
    )


@router.get("/settings")
async def show_settings(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    return await service.present_settings(session, _account_id(ctx))


@router.put("/settings")
async def update_settings(
    body: SettingsBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    try:
        return await service.save_settings(
            session,
            account_id=_account_id(ctx),
            enabled=body.enabled,
            currency=body.currency,
            rules=body.rules,
        )
    except ValueError as exc:
        raise _fail(422, str(exc)) from exc


@router.post("/inboxes/{inbox_id}/dataset")
async def connect_dataset(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    inbox = await session.get(Inbox, inbox_id)
    if (
        inbox is None
        or inbox.account_id != _account_id(ctx)
        or inbox.channel_type != CHANNEL_TYPE_WHATSAPP
    ):
        raise ChatwootHTTPException(status_code=404, detail=_NOT_FOUND)
    try:
        await service.connect(session, inbox)
    except client.ConversionsError as exc:
        status = 422 if exc.code == "not_connected" else 502
        raise _fail(status, exc.code, exc.detail) from exc
    return await service.present_settings(session, _account_id(ctx))


@router.get("/events")
async def list_events(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    return {"payload": await service.recent(session, account_id=_account_id(ctx))}
