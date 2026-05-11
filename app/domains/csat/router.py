"""Dashboard CSAT endpoints — `/api/v1/accounts/{id}/csat_survey_responses`.

Ports ``Api::V1::Accounts::CsatSurveyResponsesController``.

Route map:

  * ``GET /api/v1/accounts/{id}/csat_survey_responses``           — list
  * ``GET /api/v1/accounts/{id}/csat_survey_responses/metrics``  — counts
  * ``GET /api/v1/accounts/{id}/csat_survey_responses/download`` — CSV
    (deferred — Phase 7 owns the reporting/export plumbing)

Wire shape:
  * ``index`` → top-level JSON array (Rails ``json.array!``)
  * ``metrics`` → bare ``{total_count, ratings_count, total_sent_messages_count}``

Authorization: ``check_authorization`` invokes ``CsatSurveyResponsePolicy``
in Rails, which permits both administrator and agent
(``@account_user.administrator? || @account_user.agent?``). We mirror
with ``account_context`` (no admin gate).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.domains.contacts.models import Contact
from app.domains.conversations.models import Conversation
from app.domains.csat.presenters import present_response
from app.domains.csat.service import (
    list_responses_for_account,
    metrics_for_account,
)
from app.domains.inboxes.presenters import present_agent
from app.domains.users.models import AccountUser, User

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/csat_survey_responses",
    tags=["csat"],
)


async def _present_agent_for(
    session: AsyncSession, *, account_id: int, user_id: int | None
) -> dict[str, Any] | None:
    if user_id is None:
        return None
    user = await session.get(User, user_id)
    if user is None:
        return None
    au = (
        await session.exec(
            select(AccountUser).where(
                AccountUser.account_id == account_id,
                AccountUser.user_id == user_id,
            )
        )
    ).first()
    return present_agent(
        account_id=account_id,
        account_user_availability=au.availability if au is not None else None,
        account_user_auto_offline=au.auto_offline if au is not None else None,
        user=user,
    )


def _parse_ts(raw: str | None) -> datetime | None:
    """Accept Unix seconds OR ISO-8601; Chatwoot accepts either via
    ``DateRangeHelper#range`` so dashboards on both vintages keep
    working."""
    if not raw:
        return None
    try:
        return datetime.fromtimestamp(int(raw))
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("")
async def index_responses(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    rating: int | None = Query(None),
    user_ids: list[int] | None = Query(None),
    inbox_id: int | None = Query(None),
    team_id: int | None = Query(None),
    since: str | None = Query(None),
    until: str | None = Query(None),
    page: int = Query(1, ge=1),
) -> list[dict[str, Any]]:
    """``GET /csat_survey_responses`` → top-level array of resources."""
    assert ctx.account.id is not None
    rows = await list_responses_for_account(
        session,
        account_id=ctx.account.id,
        rating=rating,
        user_ids=user_ids,
        inbox_id=inbox_id,
        team_id=team_id,
        range_start=_parse_ts(since),
        range_end=_parse_ts(until),
        page=page,
    )
    bodies: list[dict[str, Any]] = []
    for r in rows:
        contact = await session.get(Contact, r.contact_id)
        conv = await session.get(Conversation, r.conversation_id)
        assigned = await _present_agent_for(
            session,
            account_id=ctx.account.id,
            user_id=r.assigned_agent_id,
        )
        updated_by = await _present_agent_for(
            session,
            account_id=ctx.account.id,
            user_id=r.review_notes_updated_by_id,
        )
        bodies.append(
            present_response(
                r,
                contact=contact,
                conversation=conv,
                assigned_agent=assigned,
                review_notes_updated_by=updated_by,
            )
        )
    return bodies


@router.get("/metrics")
async def metrics(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    since: str | None = Query(None),
    until: str | None = Query(None),
) -> dict[str, Any]:
    """``GET /csat_survey_responses/metrics`` — aggregate counts."""
    assert ctx.account.id is not None
    return await metrics_for_account(
        session,
        account_id=ctx.account.id,
        range_start=_parse_ts(since),
        range_end=_parse_ts(until),
    )


__all__ = ["router"]
