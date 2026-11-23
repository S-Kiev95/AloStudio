"""crm: the Meta catalogue sync is chosen product by product (F11)

Products already sent to the catalogue stay in it; the rest start off.

Revision ID: e4a6c8b0d2f4
Revises: d3f5b7c9e1a2
Create Date: 2026-11-22 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4a6c8b0d2f4"
down_revision: str | None = "d3f5b7c9e1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("meta_sync", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    products = sa.table(
        "products",
        sa.column("meta_sync", sa.Boolean()),
        sa.column("meta_retailer_id", sa.String()),
    )
    op.execute(
        products.update().where(products.c.meta_retailer_id.is_not(None)).values(meta_sync=True)
    )


def downgrade() -> None:
    op.drop_column("products", "meta_sync")
