"""publishing: cached post metrics and daily channel snapshots

Adds ``metrics`` / ``metrics_updated_at`` / ``metrics_error`` to
``publication_targets`` (latest figures of each published post) and the
``channel_metric_snapshots`` table (one row per channel per day).

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-10-27 22:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f9a0b1c2d3e4"
down_revision: str | None = "e8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "publication_targets",
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "publication_targets",
        sa.Column("metrics_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "publication_targets",
        sa.Column("metrics_error", sa.Text(), nullable=True),
    )

    op.create_table(
        "channel_metric_snapshots",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
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
        sa.Column("network", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
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
        sa.UniqueConstraint(
            "inbox_id", "date", name="uniq_channel_metric_snapshots_inbox_date"
        ),
    )
    op.create_index(
        "index_channel_metric_snapshots_on_account_id_and_date",
        "channel_metric_snapshots",
        ["account_id", "date"],
    )
    op.create_index(
        "index_channel_metric_snapshots_on_date",
        "channel_metric_snapshots",
        ["date"],
    )


def downgrade() -> None:
    op.drop_index(
        "index_channel_metric_snapshots_on_date",
        table_name="channel_metric_snapshots",
    )
    op.drop_index(
        "index_channel_metric_snapshots_on_account_id_and_date",
        table_name="channel_metric_snapshots",
    )
    op.drop_table("channel_metric_snapshots")
    op.drop_column("publication_targets", "metrics_error")
    op.drop_column("publication_targets", "metrics_updated_at")
    op.drop_column("publication_targets", "metrics")
