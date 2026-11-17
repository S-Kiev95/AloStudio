"""conversions: report ad conversations that became leads or sales to Meta (F17)

Revision ID: e8f9a0b1c2d5
Revises: d7e8f9a0b1c4
Create Date: 2026-11-17 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8f9a0b1c2d5"
down_revision: str | None = "d7e8f9a0b1c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "conversion_settings",
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("rules", sa.JSON(), nullable=True),
        *_timestamps(),
    )
    op.create_table(
        "conversion_datasets",
        sa.Column(
            "inbox_id",
            sa.BigInteger(),
            sa.ForeignKey("inboxes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_id", sa.String(64), nullable=False),
        *_timestamps(),
    )
    op.create_table(
        "conversion_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "conversation_id",
            sa.BigInteger(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("inbox_id", sa.BigInteger(), nullable=False),
        sa.Column("event_name", sa.String(32), nullable=False),
        sa.Column("trigger", sa.String(32), nullable=False),
        sa.Column("detail", sa.String(255), nullable=True),
        sa.Column("value", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint(
            "conversation_id", "event_name", name="uniq_conversion_event_per_conversation"
        ),
    )
    op.create_index(
        "index_conversion_events_on_account_created", "conversion_events", ["account_id", "created_at"]
    )
    op.create_index("index_conversion_events_on_status", "conversion_events", ["status"])


def downgrade() -> None:
    op.drop_table("conversion_events")
    op.drop_table("conversion_datasets")
    op.drop_table("conversion_settings")
