"""Product catalogue service — account-scoped CRUD."""

from __future__ import annotations

from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.products.models import Product


def _validate_name(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "name is required"},
        )
    if len(raw) > 255:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "name exceeds 255 chars"},
        )
    return raw


async def create_product(
    session: AsyncSession, *, account_id: int, payload: dict[str, Any]
) -> Product:
    name = _validate_name(payload.get("name"))
    product = Product(
        account_id=account_id,
        name=name,
        description=payload.get("description"),
        sku=payload.get("sku"),
        price=payload.get("price"),
        currency=payload.get("currency"),
        url=payload.get("url"),
        image_url=payload.get("image_url"),
        enabled=payload.get("enabled", True),
    )
    session.add(product)
    await session.flush()
    await session.refresh(product)
    return product


async def list_products(
    session: AsyncSession,
    *,
    account_id: int,
    enabled: bool | None = None,
    page: int = 1,
    per_page: int = 50,
) -> list[Product]:
    per_page = min(max(1, per_page), 200)
    page = max(1, page)
    stmt = select(Product).where(Product.account_id == account_id)
    if enabled is not None:
        stmt = stmt.where(Product.enabled == enabled)
    stmt = stmt.order_by(Product.id.desc())  # type: ignore[attr-defined]
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    return list((await session.exec(stmt)).all())


async def get_product(
    session: AsyncSession, *, account_id: int, product_id: int
) -> Product | None:
    return (
        await session.exec(
            select(Product).where(
                Product.id == product_id,
                Product.account_id == account_id,
            )
        )
    ).first()


async def update_product(
    session: AsyncSession, *, product: Product, payload: dict[str, Any]
) -> Product:
    if "name" in payload:
        product.name = _validate_name(payload.get("name"))
    for field in (
        "description",
        "sku",
        "price",
        "currency",
        "url",
        "image_url",
        "enabled",
    ):
        if field in payload:
            setattr(product, field, payload[field])
    session.add(product)
    await session.flush()
    await session.refresh(product)
    return product


async def delete_product(
    session: AsyncSession, *, product: Product
) -> None:
    await session.delete(product)
    await session.flush()


__all__ = [
    "create_product",
    "delete_product",
    "get_product",
    "list_products",
    "update_product",
]
