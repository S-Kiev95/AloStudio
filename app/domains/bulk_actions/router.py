"""Bulk actions — ``POST /api/v1/accounts/:account_id/bulk_actions``.

Ports the Conversation slice of Chatwoot's
``Api::V1::Accounts::BulkActionsController``: apply a status and/or assignee
to many conversations in one call. Chatwoot scopes by
``Current.account.conversations.where(display_id: params[:ids])`` — any
account member, account-scoped, no per-conversation policy check — and we
mirror that. Each conversation is mutated through the same service helpers
the per-conversation endpoints use (``toggle_status`` / ``update_assignee``),
so activity rows + realtime events fire identically.

Scope: ``fields.status`` + ``fields.assignee_id`` (the two common bulk ops).
``labels`` add/remove is a documented follow-up.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.domains.conversations.models import Conversation
from app.domains.conversations.service import toggle_status, update_assignee

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/bulk_actions",
    tags=["bulk_actions"],
)


@router.post("", status_code=status.HTTP_200_OK)
async def create_bulk_action(
    payload: dict[str, Any],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Apply ``fields`` to the conversations named by ``ids`` (display ids).

    Body (mirrors Chatwoot)::

        {"type": "Conversation",
         "ids": [12, 13],
         "fields": {"status": "resolved", "assignee_id": 4}}

    ``assignee_id: null`` unassigns. Unknown / out-of-account ids are
    silently skipped (account-scoped query). Returns the display ids that
    were touched.
    """
    assert ctx.account.id is not None

    if payload.get("type", "Conversation") != "Conversation":
        return {"payload": {"updated": []}}

    raw_ids = payload.get("ids") or []
    try:
        ids = [int(i) for i in raw_ids]
    except (TypeError, ValueError):
        ids = []
    fields = payload.get("fields") or {}
    if not ids or not isinstance(fields, dict):
        return {"payload": {"updated": []}}

    new_status = fields.get("status")
    has_assignee = "assignee_id" in fields
    assignee_id = fields.get("assignee_id")

    updated: list[int] = []
    for display_id in ids:
        # Load one at a time — the same path the per-conversation endpoints
        # use, so the conversation's selectin relationships resolve cleanly
        # in async context. A single batched IN-query can leave them lazy,
        # which then trips MissingGreenlet inside the service's event
        # dispatch (it reads ``conversation.inbox``).
        conv = (
            await session.exec(
                select(Conversation).where(
                    Conversation.account_id == ctx.account.id,
                    Conversation.display_id == display_id,
                )
            )
        ).first()
        if conv is None:
            continue
        if new_status:
            await toggle_status(session, conversation=conv, status=str(new_status))
        if has_assignee:
            await update_assignee(
                session,
                conversation=conv,
                assignee_id=int(assignee_id) if assignee_id is not None else None,
            )
        updated.append(display_id)

    return {"payload": {"updated": updated}}


__all__ = ["router"]
