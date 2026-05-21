"""Product / service catalogue model (account-scoped).

One row per product or service a client promotes. Generic on purpose —
nothing here is Instagram-specific; the IG link lives in the
``instagram_post_products`` join (instagram domain). An AI agent reads
these rows for context when answering questions about a post/story.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin


class Product(TimestampMixin, table=True):
    """A product or service in a client's catalogue."""

    __tablename__ = "products"
    __table_args__ = (
        Index("index_products_on_account_id", "account_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    description: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    sku: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    price: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(12, 2), nullable=True)
    )
    currency: str | None = Field(
        default=None, sa_column=Column(String(8), nullable=True)
    )
    url: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    image_url: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )


__all__ = ["Product"]
