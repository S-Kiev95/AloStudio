"""usage: what each account consumes and costs (F6)

Revision ID: c8d9e0f1a2b4
Revises: b7c8d9e0f1a3
Create Date: 2026-11-14 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8d9e0f1a2b4"
down_revision: str | None = "b7c8d9e0f1a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("inbox_id", sa.BigInteger(), nullable=True),
        sa.Column("campaign_id", sa.BigInteger(), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("pricing_type", sa.String(64), nullable=True),
        sa.Column("billable", sa.Boolean(), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost", sa.Numeric(14, 6), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("account_id", "kind", "source_id", name="uniq_usage_records_source"),
    )
    op.create_index(
        "index_usage_records_on_account_occurred", "usage_records", ["account_id", "occurred_at"]
    )
    op.create_table(
        "whatsapp_cost_days",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("inbox_id", sa.BigInteger(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("pricing_category", sa.String(64), nullable=False),
        sa.Column("pricing_type", sa.String(64), nullable=False),
        sa.Column("country", sa.String(8), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost", sa.Numeric(14, 6), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "inbox_id",
            "day",
            "pricing_category",
            "pricing_type",
            "country",
            name="uniq_whatsapp_cost_days_bucket",
        ),
    )
    op.create_index(
        "index_whatsapp_cost_days_on_account_day", "whatsapp_cost_days", ["account_id", "day"]
    )


def downgrade() -> None:
    op.drop_index("index_whatsapp_cost_days_on_account_day", table_name="whatsapp_cost_days")
    op.drop_table("whatsapp_cost_days")
    op.drop_index("index_usage_records_on_account_occurred", table_name="usage_records")
    op.drop_table("usage_records")
