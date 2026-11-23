"""Contact lifecycle endpoints (F17).

Route map, under ``/api/v1/accounts/{account_id}/lifecycle``:
  * ``GET  /settings``                — on/off and the stages (anyone in the
    account: the stage picker needs them)
  * ``PUT  /settings``                — ``{enabled, stages?}`` (admins)
  * ``GET  /contacts/{contact_id}``   — the contact's stage, when and by whom
  * ``PUT  /contacts/{contact_id}``   — ``{stage_key, conversation_id?}``
    (the conversation's number, to leave a line in it)
  * ``GET  /report?days=``            — contacts per stage, and how many
    entered each in ``days``

Errors carry ``code`` (``lifecycle.<code>``) for the panel to translate.
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
from app.domains.contacts.models import Contact
from app.domains.conversations.models import Conversation
from app.domains.lifecycle import service

router = APIRouter(prefix="/api/v1/accounts/{account_id}/lifecycle", tags=["lifecycle"])

_NOT_FOUND = {"error": "Resource could not be found"}


class SettingsBody(BaseModel):
    enabled: bool
    stages: list[dict[str, Any]] | None = None


class StageBody(BaseModel):
    stage_key: str | None = None
    conversation_id: int | None = None


def _account_id(ctx: AccountContext) -> int:
    assert ctx.account.id is not None
    return ctx.account.id


def _fail(code: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=422, detail={"message": code, "code": f"lifecycle.{code}"}
    )


async def _contact(session: AsyncSession, ctx: AccountContext, contact_id: int) -> Contact:
    contact = await session.get(Contact, contact_id)
    if contact is None or contact.account_id != _account_id(ctx):
        raise ChatwootHTTPException(status_code=404, detail=_NOT_FOUND)
    return contact


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
            session, account_id=_account_id(ctx), enabled=body.enabled, stages=body.stages
        )
    except ValueError as exc:
        raise _fail(str(exc)) from exc


@router.get("/contacts/{contact_id}")
async def show_contact_stage(
    contact_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    contact = await _contact(session, ctx, contact_id)
    assert contact.id is not None
    return await service.contact_stage(session, account_id=_account_id(ctx), contact_id=contact.id)


@router.put("/contacts/{contact_id}")
async def update_contact_stage(
    contact_id: Annotated[int, Path()],
    body: StageBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    contact = await _contact(session, ctx, contact_id)
    conversation = None
    if body.conversation_id is not None:
        conversation = (
            await session.exec(
                select(Conversation).where(
                    Conversation.account_id == _account_id(ctx),
                    Conversation.display_id == body.conversation_id,
                )
            )
        ).first()
    try:
        return await service.set_stage(
            session,
            account_id=_account_id(ctx),
            contact=contact,
            stage_key=body.stage_key,
            user=ctx.user,
            conversation=conversation,
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
