"""Closing notes endpoints (F17).

Route map, under ``/api/v1/accounts/{account_id}/closing_notes``:
  * ``GET  /settings``        — on/off, required, the categories (anyone in the
    account: the close button needs them)
  * ``PUT  /settings``        — ``{enabled, required, categories?}`` (admins)
  * ``POST /{display_id}``    — resolve the conversation with ``{category?,
    note?}`` (whoever can see it)
  * ``GET  /report?days=``    — closings by category (anyone in the account,
    like the other reports)

Errors carry ``code`` (``closing.<code>``) for the panel to translate.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.closing import service
from app.domains.conversations.models import Conversation
from app.domains.conversations.permission import can_view_conversation

router = APIRouter(prefix="/api/v1/accounts/{account_id}/closing_notes", tags=["closing_notes"])

_NOT_FOUND = {"error": "Resource could not be found"}


class SettingsBody(BaseModel):
    enabled: bool
    required: bool = False
    categories: list[str] | None = None


class CloseBody(BaseModel):
    category: str | None = None
    note: str | None = None


def _account_id(ctx: AccountContext) -> int:
    assert ctx.account.id is not None
    return ctx.account.id


def _fail(code: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=422, detail={"message": code, "code": f"closing.{code}"}
    )


@router.get("/settings")
async def show_settings(
    ctx: Annotated[AccountContext, Depends(account_context)],
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
            required=body.required,
            categories=body.categories,
        )
    except ValueError as exc:
        raise _fail(str(exc)) from exc


@router.get("/report")
async def show_report(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict[str, Any]:
    return await service.report(session, account_id=_account_id(ctx), days=days)


@router.post("/{display_id}")
async def close_conversation(
    display_id: Annotated[int, Path()],
    body: CloseBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    conversation = (
        await session.exec(
            select(Conversation).where(
                Conversation.account_id == _account_id(ctx),
                Conversation.display_id == display_id,
            )
        )
    ).first()
    assert ctx.user.id is not None
    if conversation is None or not await can_view_conversation(
        session, account_id=_account_id(ctx), user_id=ctx.user.id, conversation=conversation
    ):
        raise ChatwootHTTPException(status_code=404, detail=_NOT_FOUND)
    try:
        closing = await service.close(
            session,
            conversation=conversation,
            user_id=ctx.user.id,
            category=body.category,
            note=body.note,
        )
    except ValueError as exc:
        raise _fail(str(exc)) from exc
    return {
        "status": "resolved",
        "category": closing.category if closing else None,
        "note": closing.note if closing else None,
    }
