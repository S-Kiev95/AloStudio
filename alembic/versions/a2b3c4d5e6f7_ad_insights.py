"""ad insights — cached Meta Marketing API spend/delivery per ad per day

Day granularity because reports run over arbitrary windows, and spend only
lines up with a conversation count when both are summed over the same days.

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ad_insights",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("ad_id", sa.String(), nullable=False),
        sa.Column("ad_name", sa.String(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        # NUMERIC, not float: this feeds a cost-per-result figure summed over
        # a month of daily rows.
        sa.Column(
            "spend", sa.Numeric(14, 4), nullable=False, server_default="0"
        ),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column(
            "impressions", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("clicks", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reach", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "raw",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        # The sync upserts on this key so a re-run over an overlapping range
        # corrects figures rather than double-counting them.
        sa.UniqueConstraint(
            "account_id", "ad_id", "date", name="uniq_ad_insight_per_day"
        ),
    )
    op.create_index(
        "index_ad_insights_on_account_date", "ad_insights", ["account_id", "date"]
    )
    op.create_index("index_ad_insights_on_ad_id", "ad_insights", ["ad_id"])


def downgrade() -> None:
    op.drop_index("index_ad_insights_on_ad_id", table_name="ad_insights")
    op.drop_index("index_ad_insights_on_account_date", table_name="ad_insights")
    op.drop_table("ad_insights")
