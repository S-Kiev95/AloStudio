"""Label HTTP endpoints.

Ports ``Api::V1::Accounts::LabelsController``.

Route map:

  * ``GET    /api/v1/accounts/:account_id/labels``
  * ``POST   /api/v1/accounts/:account_id/labels``
  * ``GET    /api/v1/accounts/:account_id/labels/:id``
  * ``PATCH  /api/v1/accounts/:account_id/labels/:id``
  * ``DELETE /api/v1/accounts/:account_id/labels/:id``

Authorisation per ``LabelPolicy``:

  * ``index``                           — admin OR agent
  * ``show``/``create``/``update``/``destroy`` — admin only

Wire shape (matches ``labels/*.json.jbuilder``):

  * ``index`` → ``{"payload": [<label>, ...]}``
  * ``show`` / ``create`` / ``update`` → bare label object
  * ``destroy`` → ``head :ok`` (Rails: 200 + empty body, NOT 204)
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.labels.models import Label
from app.domains.labels.presenters import present_label, present_labels_index
from app.domains.labels.schemas import LabelEnvelope
from app.domains.labels.service import (
    create_label,
    destroy_label,
    update_label,
)

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/labels",
    tags=["labels"],
)


# ============================================================================
# CRUD
# ============================================================================
@router.get("")
async def index_labels(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``GET /labels`` — admin OR agent.

    Mirrors the default scope ``order(:title)`` on Label."""
    assert ctx.account.id is not None
    rows = list(
        (
            await session.exec(
                select(Label)
                .where(Label.account_id == ctx.account.id)
                .order_by(Label.title)
            )
        ).all()
    )
    return present_labels_index(rows)


@router.post("", status_code=status.HTTP_200_OK)
async def create_label_endpoint(
    payload: LabelEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /labels`` — admin only.

    Body: ``{"label": {...}}`` per ``params.require(:label)``."""
    assert ctx.account.id is not None
    body = payload.label.model_dump(exclude_unset=True)
    row = await create_label(session, account_id=ctx.account.id, payload=body)
    return present_label(row)


@router.get("/{label_id}")
async def show_label(
    label_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_label(session, ctx, label_id)
    return present_label(row)


@router.patch("/{label_id}")
async def update_label_endpoint(
    label_id: Annotated[int, Path()],
    payload: LabelEnvelope,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_label(session, ctx, label_id)
    body = payload.label.model_dump(exclude_unset=True)
    updated = await update_label(session, label=row, payload=body)
    return present_label(updated)


@router.delete("/{label_id}", status_code=status.HTTP_200_OK)
async def destroy_label_endpoint(
    label_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``DELETE /labels/:id`` — Rails ``head :ok`` (200, empty body).

    Note: NOT 204. Chatwoot's controller emits ``head :ok`` which is
    HTTP 200 with no body."""
    row = await _find_label(session, ctx, label_id)
    await destroy_label(session, label=row)
    return {}


# ============================================================================
# Helpers
# ============================================================================
async def _find_label(
    session: AsyncSession, ctx: AccountContext, label_id: int
) -> Label:
    stmt = select(Label).where(
        Label.id == label_id,
        Label.account_id == ctx.account.id,
    )
    row = (await session.exec(stmt)).first()
    if row is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return row


__all__ = ["router"]
