"""usage: monthly spend caps per account (F6)

Revision ID: d9e0f1a2b3c5
Revises: c8d9e0f1a2b4
Create Date: 2026-11-14 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d9e0f1a2b3c5"
down_revision: str | None = "c8d9e0f1a2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_limits",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("monthly_limit", sa.Numeric(12, 2), nullable=False),
        sa.Column("notified_month", sa.String(7), nullable=True),
        sa.Column("notified_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("account_id", "kind", name="uniq_usage_limits_kind"),
    )


def downgrade() -> None:
    op.drop_table("usage_limits")
