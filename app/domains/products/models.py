"""Product / service catalogue model (account-scoped).

One row per product or service a client promotes. Generic on purpose —
nothing here is Instagram-specific; the IG link lives in the
``instagram_post_products`` join (instagram domain). An AI agent reads
these rows for context when answering questions about a post/story.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin


class Product(TimestampMixin, table=True):
    """A product or service in a client's catalogue."""

    __tablename__ = "products"
    __table_args__ = (
        Index("index_products_on_account_id", "account_id"),
        UniqueConstraint(
            "account_id",
            "external_id",
            name="uniq_products_account_external_id",
        ),
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
    external_id: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )

    # ------- Meta catalogue sync (F11); see app/domains/crm/meta_catalog.py
    # The id the item has in the catalogue (``retailer_id``), kept once sent
    # so a later SKU change doesn't leave the old item behind.
    meta_retailer_id: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    meta_synced_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    # Why Meta (or our own check) refused it, or None.
    meta_sync_error: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )


__all__ = ["Product"]
