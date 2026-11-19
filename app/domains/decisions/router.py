"""Decisions endpoints (F10), administrators only.

Route map, under ``/api/v1/accounts/{account_id}/decisions``:
  * ``GET  /settings``        — shadow mode on/off, the questions, and whether
    the installation has a decisions service set up
  * ``PUT  /settings``        — ``{enabled, questions?, provider?, context?,
    apply_priority?}``
  * ``GET  /report``          — per question: decided, agreement with people,
    mean confidence; this month's calls and cost
  * ``GET  /labeling/next``   — a decided conversation people have not labeled
    (text and questions only: never the service's answers); ``skip`` ids
  * ``POST /labels``          — ``{conversation_id, answers: {question: option}}``

``conversation_id`` is the number the panel shows (``display_id``). Errors
carry ``code`` (``decisions.<code>``) for the panel to translate.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.conversations.models import Conversation
from app.domains.decisions import service

router = APIRouter(prefix="/api/v1/accounts/{account_id}/decisions", tags=["decisions"])


class SettingsBody(BaseModel):
    enabled: bool
    questions: list[dict[str, Any]] | None = None
    # ``api`` (Jev or Laya) or ``local`` (the model on this server).
    provider: str | None = None
    context: str | None = None
    apply_priority: bool | None = None


class LabelsBody(BaseModel):
    conversation_id: int
    answers: dict[str, str]


def _account_id(ctx: AccountContext) -> int:
    assert ctx.account.id is not None
    return ctx.account.id


def _fail(code: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=422, detail={"message": code, "code": f"decisions.{code}"}
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
            questions=body.questions,
            provider=body.provider,
            context=body.context,
            apply_priority=body.apply_priority,
        )
    except ValueError as exc:
        raise _fail(str(exc)) from exc


@router.get("/report")
async def show_report(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict[str, Any]:
    return await service.report(session, account_id=_account_id(ctx), days=days)


@router.get("/labeling/next")
async def next_to_label(
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: Annotated[list[int] | None, Query()] = None,
) -> dict[str, Any]:
    item = await service.next_to_label(session, account_id=_account_id(ctx), skip=skip)
    return {"payload": item}


@router.post("/labels")
async def create_labels(
    body: LabelsBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    conversation = (
        await session.exec(
            select(Conversation).where(
                Conversation.account_id == _account_id(ctx),
                Conversation.display_id == body.conversation_id,
            )
        )
    ).first()
    if conversation is None:
        raise ChatwootHTTPException(status_code=404, detail={"error": "Resource could not be found"})
    assert ctx.user.id is not None
    try:
        saved = await service.save_labels(
            session,
            account_id=_account_id(ctx),
            user_id=ctx.user.id,
            conversation=conversation,
            answers=body.answers,
        )
    except ValueError as exc:
        raise _fail(str(exc)) from exc
    return {"saved": saved}
