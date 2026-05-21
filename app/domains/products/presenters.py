"""Wire-shape presenter for the product catalogue."""

from __future__ import annotations

from typing import Any

from app.domains.products.models import Product


def present_product(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "account_id": product.account_id,
        "name": product.name,
        "description": product.description,
        "sku": product.sku,
        # Numeric → float for JSON (catalogue display precision).
        "price": float(product.price) if product.price is not None else None,
        "currency": product.currency,
        "url": product.url,
        "image_url": product.image_url,
        "enabled": product.enabled,
        "created_at": (
            int(product.created_at.timestamp())
            if product.created_at
            else None
        ),
    }


__all__ = ["present_product"]
