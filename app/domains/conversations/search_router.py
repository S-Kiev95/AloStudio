"""``GET /api/v1/accounts/{account_id}/search/messages`` — F8.

Same path as Chatwoot's ``SearchController#messages``; the body is ours,
built for jumping to the message (see :mod:`message_search`).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.domains.conversations.message_search import search_messages

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/search", tags=["search"]
)


@router.get("/messages")
async def search_messages_endpoint(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: Annotated[str, Query(min_length=1, max_length=200)],
    conversation_id: Annotated[
        int | None, Query(description="display_id: search inside one conversation")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> dict[str, Any]:
    assert ctx.account.id is not None
    return await search_messages(
        session,
        account_id=ctx.account.id,
        current_user_id=ctx.user.id,  # type: ignore[arg-type]
        q=q,
        conversation_display_id=conversation_id,
        page=page,
    )


__all__ = ["router"]
