"""The AI's suggestion on a conversation, for the panel (PLAN.agente-ia.md, 2b).

In shadow mode the AI leaves its answer waiting above the composer. Whoever
can see the conversation can read it, and use it (it goes out as their own
message, carrying ``content_attributes.ai_reply_id``) or discard it.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import lazyload
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.domains.ai_agent import service
from app.domains.conversations.router import _load_conversation_by_display_id

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/conversations/{display_id}/ai_reply",
    tags=["ai_agent"],
)


@router.get("")
async def show_suggestion(
    display_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    conv = await _load_conversation_by_display_id(
        session, ctx=ctx, display_id=display_id, options=(lazyload("*"),)
    )
    reply = await service.waiting_suggestion(session, conv.id)  # type: ignore[arg-type]
    return {"ai_reply": service.present_suggestion(reply)}


@router.post("/{reply_id}/discard")
async def discard_suggestion(
    display_id: Annotated[int, Path()],
    reply_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    conv = await _load_conversation_by_display_id(
        session, ctx=ctx, display_id=display_id, options=(lazyload("*"),)
    )
    if not await service.discard_suggestion(session, conv.id, reply_id):  # type: ignore[arg-type]
        raise ChatwootHTTPException(
            status_code=409, detail={"message": "The suggestion is no longer waiting."}
        )
    return {"ai_reply": None}


__all__ = ["router"]
