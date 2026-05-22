"""Product catalogue HTTP endpoints (admin-only writes).

Route map:
  * ``GET    /api/v1/accounts/{id}/products``
  * ``POST   /api/v1/accounts/{id}/products``
  * ``GET    /api/v1/accounts/{id}/products/{product_id}``
  * ``PATCH  /api/v1/accounts/{id}/products/{product_id}``
  * ``DELETE /api/v1/accounts/{id}/products/{product_id}``

Read = admin OR agent; writes = admin only (mirrors the labels/macros
policy split). Own-extension, not a Chatwoot mirror.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.products import service as svc
from app.domains.products.models import Product
from app.domains.products.presenters import present_product
from app.domains.products.schemas import ProductCreate, ProductUpdate

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/products",
    tags=["products"],
)


async def _find_product(
    session: AsyncSession, ctx: AccountContext, product_id: int
) -> Product:
    assert ctx.account.id is not None
    row = await svc.get_product(
        session, account_id=ctx.account.id, product_id=product_id
    )
    if row is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return row


@router.get("")
async def index_products(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    enabled: bool | None = None,
    page: int = 1,
) -> list[dict[str, Any]]:
    assert ctx.account.id is not None
    rows = await svc.list_products(
        session, account_id=ctx.account.id, enabled=enabled, page=page
    )
    return [present_product(p) for p in rows]


@router.post("", status_code=status.HTTP_200_OK)
async def create_product_endpoint(
    payload: ProductCreate,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    row = await svc.create_product(
        session,
        account_id=ctx.account.id,
        payload=payload.model_dump(exclude_unset=True),
    )
    return present_product(row)


@router.get("/{product_id}")
async def show_product(
    product_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_product(session, ctx, product_id)
    return present_product(row)


@router.patch("/{product_id}")
async def update_product_endpoint(
    product_id: Annotated[int, Path()],
    payload: ProductUpdate,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_product(session, ctx, product_id)
    updated = await svc.update_product(
        session, product=row, payload=payload.model_dump(exclude_unset=True)
    )
    return present_product(updated)


@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
async def delete_product_endpoint(
    product_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    row = await _find_product(session, ctx, product_id)
    await svc.delete_product(session, product=row)
    return {}


__all__ = ["router"]
