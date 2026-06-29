"""CustomView ("custom_filters") HTTP endpoints.

Ports ``Api::V1::Accounts::CustomFiltersController`` — saved filter-DSL
views, private to the user who created them.

Route map (account-scoped, any member — views are per-user, not admin-gated):

  * ``GET    /api/v1/accounts/:account_id/custom_filters?filter_type=conversation``
  * ``POST   /api/v1/accounts/:account_id/custom_filters``
  * ``PATCH  /api/v1/accounts/:account_id/custom_filters/:id``
  * ``DELETE /api/v1/accounts/:account_id/custom_filters/:id``

Wire shape: ``index`` → bare array; ``create``/``update`` → bare object;
``destroy`` → ``{}`` (200, empty body).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.domains.custom_views.models import CustomView, custom_view_type_from_str
from app.domains.custom_views.presenters import present_custom_view
from app.domains.custom_views.schemas import CustomViewCreate, CustomViewUpdate

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/custom_filters",
    tags=["custom_views"],
)


def _filter_type_int(value: str | int | None) -> int:
    if isinstance(value, int):
        return value
    return custom_view_type_from_str(value)


def _blank_name_error() -> ChatwootHTTPException:
    return ChatwootHTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"message": "Name can't be blank"},
    )


@router.get("")
async def index_custom_views(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    filter_type: str | None = Query(None),
) -> list[dict[str, Any]]:
    """List the current user's saved views for this account + filter_type.

    Defaults to ``conversation`` views when ``filter_type`` is omitted."""
    assert ctx.account.id is not None
    ft = _filter_type_int(filter_type)
    rows = list(
        (
            await session.exec(
                select(CustomView)
                .where(
                    CustomView.account_id == ctx.account.id,
                    CustomView.user_id == ctx.user.id,
                    CustomView.filter_type == ft,
                )
                .order_by(CustomView.name)  # type: ignore[arg-type]
            )
        ).all()
    )
    return [present_custom_view(r) for r in rows]


@router.post("", status_code=status.HTTP_200_OK)
async def create_custom_view(
    payload: CustomViewCreate,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    name = (payload.name or "").strip()
    if not name:
        raise _blank_name_error()
    row = CustomView(
        name=name,
        filter_type=_filter_type_int(payload.filter_type),
        query=payload.query or {},
        account_id=ctx.account.id,
        user_id=ctx.user.id,  # type: ignore[arg-type]
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return present_custom_view(row)


@router.patch("/{view_id}")
async def update_custom_view(
    view_id: Annotated[int, Path()],
    payload: CustomViewUpdate,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find(session, ctx, view_id)
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise _blank_name_error()
        row.name = name
    if payload.query is not None:
        row.query = payload.query
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return present_custom_view(row)


@router.delete("/{view_id}", status_code=status.HTTP_200_OK)
async def destroy_custom_view(
    view_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    filter_type: str | None = Query(None),
) -> dict[str, Any]:
    """``DELETE /custom_filters/:id`` — 200 + empty body (matches Rails)."""
    row = await _find(session, ctx, view_id)
    await session.delete(row)
    await session.flush()
    return {}


async def _find(
    session: AsyncSession, ctx: AccountContext, view_id: int
) -> CustomView:
    row = (
        await session.exec(
            select(CustomView).where(
                CustomView.id == view_id,
                CustomView.account_id == ctx.account.id,
                CustomView.user_id == ctx.user.id,
            )
        )
    ).first()
    if row is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return row


__all__ = ["router"]
