"""CannedResponse HTTP endpoints.

Ports ``Api::V1::Accounts::CannedResponsesController``.

Route map:

  * ``GET    /api/v1/accounts/{id}/canned_responses[?search=]``
  * ``POST   /api/v1/accounts/{id}/canned_responses``
  * ``PATCH  /api/v1/accounts/{id}/canned_responses/{id}``
  * ``DELETE /api/v1/accounts/{id}/canned_responses/{id}``  → ``head :ok`` (200)

Authorisation: ``BaseController`` — any account member. There is no
per-record policy and no ``show`` action (parity: the Rails controller
exposes only index / create / update / destroy).

Wire shape: bare ``render json:`` — the collection is a plain array and
a single resource is a plain object (no ``payload`` envelope).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.domains.canned_responses.models import CannedResponse
from app.domains.canned_responses.presenters import (
    present_canned_response,
    present_canned_responses,
)
from app.domains.canned_responses.schemas import CannedResponseEnvelope
from app.domains.canned_responses.service import (
    create_canned_response,
    destroy_canned_response,
    list_canned_responses,
    update_canned_response,
)

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/canned_responses",
    tags=["canned_responses"],
)


@router.get("")
async def index_canned_responses(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    search: str | None = Query(None),
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    rows = await list_canned_responses(
        session, account_id=ctx.account.id, search=search
    )
    return present_canned_responses(rows)


@router.post("", status_code=status.HTTP_200_OK)
async def create_canned_response_endpoint(
    payload: CannedResponseEnvelope,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    body = payload.canned_response.model_dump(exclude_unset=True)
    cr = await create_canned_response(
        session, account_id=ctx.account.id, payload=body
    )
    return present_canned_response(cr)


@router.patch("/{canned_response_id}")
async def update_canned_response_endpoint(
    canned_response_id: Annotated[int, Path()],
    payload: CannedResponseEnvelope,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    cr = await _find(session, ctx, canned_response_id)
    body = payload.canned_response.model_dump(exclude_unset=True)
    updated = await update_canned_response(session, canned=cr, payload=body)
    return present_canned_response(updated)


@router.delete("/{canned_response_id}", status_code=status.HTTP_200_OK)
async def destroy_canned_response_endpoint(
    canned_response_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``DELETE`` → Rails ``head :ok`` (HTTP 200, empty body)."""
    assert ctx.account.id is not None
    cr = await _find(session, ctx, canned_response_id)
    await destroy_canned_response(session, canned=cr)
    return {}


async def _find(
    session: AsyncSession, ctx: AccountContext, canned_response_id: int
) -> CannedResponse:
    row = (
        await session.exec(
            select(CannedResponse).where(
                CannedResponse.id == canned_response_id,
                CannedResponse.account_id == ctx.account.id,
            )
        )
    ).first()
    if row is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return row


__all__ = ["router"]
