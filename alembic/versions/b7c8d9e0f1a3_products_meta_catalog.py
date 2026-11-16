"""crm: products synced to a Meta catalogue (F11)

Revision ID: b7c8d9e0f1a3
Revises: a6b7c8d9e0f2
Create Date: 2026-11-14 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7c8d9e0f1a3"
down_revision: str | None = "a6b7c8d9e0f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("products", sa.Column("meta_retailer_id", sa.String(), nullable=True))
    op.add_column(
        "products", sa.Column("meta_synced_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("products", sa.Column("meta_sync_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "meta_sync_error")
    op.drop_column("products", "meta_synced_at")
    op.drop_column("products", "meta_retailer_id")
