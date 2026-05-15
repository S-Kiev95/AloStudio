"""phase9: campaigns

Mirrors ``reference/chatwoot/db/schema.rb`` (v4.13.0).

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-05-14 02:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7f8a9b0c1d2"
down_revision: str | None = "d6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("display_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inbox_id",
            sa.BigInteger(),
            sa.ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trigger_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "campaign_type",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "campaign_status",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "audience",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "scheduled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "trigger_only_during_business_hours",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "template_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "index_campaigns_on_account_id", "campaigns", ["account_id"]
    )
    op.create_index(
        "index_campaigns_on_inbox_id", "campaigns", ["inbox_id"]
    )
    op.create_index(
        "index_campaigns_on_campaign_status",
        "campaigns",
        ["campaign_status"],
    )
    op.create_index(
        "index_campaigns_on_campaign_type",
        "campaigns",
        ["campaign_type"],
    )
    op.create_index(
        "index_campaigns_on_scheduled_at",
        "campaigns",
        ["scheduled_at"],
    )


def downgrade() -> None:
    op.drop_index("index_campaigns_on_scheduled_at", table_name="campaigns")
    op.drop_index("index_campaigns_on_campaign_type", table_name="campaigns")
    op.drop_index("index_campaigns_on_campaign_status", table_name="campaigns")
    op.drop_index("index_campaigns_on_inbox_id", table_name="campaigns")
    op.drop_index("index_campaigns_on_account_id", table_name="campaigns")
    op.drop_table("campaigns")
