"""billing: AI credit bought in Polar (F2 paso 3)

Revision ID: 9a5e3c7b2d4f
Revises: 8f4d2b6a1c3e
Create Date: 2026-11-16 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9a5e3c7b2d4f"
down_revision: str | None = "8f4d2b6a1c3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credit_purchases",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_id", sa.String(), nullable=False, unique=True),
        sa.Column("paid_cents", sa.Integer(), nullable=False),
        sa.Column("refunded_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(12, 2), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_credit_purchases_account_id", "credit_purchases", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_credit_purchases_account_id", table_name="credit_purchases")
    op.drop_table("credit_purchases")
