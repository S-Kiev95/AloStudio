"""AI help while writing (F17).

Route map, under ``/api/v1/accounts/{account_id}/writing_assist``:
  * ``GET``  — whether it is on, its actions and languages (anyone in the
    account: the composer shows the button by it)
  * ``POST`` — ``{action, text?, language?, conversation_id?}`` → ``{text}``:
    the draft rewritten, or with ``summarize`` a note about the conversation
    (its number), for whoever can see it

Errors carry ``code`` (``writing_assist.<code>``) for the panel to translate.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.domains.conversations.models import Conversation
from app.domains.conversations.permission import can_view_conversation
from app.domains.writing_assist import service

router = APIRouter(prefix="/api/v1/accounts/{account_id}/writing_assist", tags=["writing_assist"])

_NOT_FOUND = {"error": "Resource could not be found"}


class AssistBody(BaseModel):
    action: str
    text: str | None = None
    language: str | None = None
    conversation_id: int | None = None


def _fail(code: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=422, detail={"message": code, "code": f"writing_assist.{code}"}
    )


@router.get("")
async def show(
    ctx: Annotated[AccountContext, Depends(account_context)],
) -> dict[str, Any]:
    return service.present()


@router.post("")
async def assist(
    body: AssistBody,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    if not service.enabled():
        raise _fail("disabled")
    account_id, user_id = ctx.account.id, ctx.user.id
    assert account_id is not None and user_id is not None
    try:
        if body.action != service.SUMMARIZE:
            text = await service.rewrite(
                session,
                account_id=account_id,
                action=body.action,
                text=body.text,
                language=body.language,
            )
            return {"text": text}
        conversation = (
            await session.exec(
                select(Conversation).where(
                    Conversation.account_id == account_id,
                    Conversation.display_id == body.conversation_id,
                )
            )
        ).first()
        if conversation is None or not await can_view_conversation(
            session, account_id=account_id, user_id=user_id, conversation=conversation
        ):
            raise ChatwootHTTPException(status_code=404, detail=_NOT_FOUND)
        text = await service.summarize(
            session, account_id=account_id, conversation=conversation, language=body.language
        )
    except ValueError as exc:
        raise _fail(str(exc)) from exc
    return {"text": text}
