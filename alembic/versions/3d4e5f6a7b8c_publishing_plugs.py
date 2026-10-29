"""publishing: plugs (automatic actions when a post reaches N likes)

Adds ``publishing_plugs`` (one per channel and kind) and
``publishing_plug_runs`` (one per plug and post, so a plug never fires twice
on the same post).

Revision ID: 3d4e5f6a7b8c
Revises: 2c3d4e5f6a7b
Create Date: 2026-10-29 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "3d4e5f6a7b8c"
down_revision: str | None = "2c3d4e5f6a7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "publishing_plugs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            sa.BigInteger(),
            sa.ForeignKey("publishing_channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("likes_threshold", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_timestamps(),
        sa.UniqueConstraint("channel_id", "kind", name="uniq_publishing_plugs_channel_kind"),
    )
    op.create_index("ix_publishing_plugs_account_id", "publishing_plugs", ["account_id"])
    op.create_table(
        "publishing_plug_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "plug_id",
            sa.BigInteger(),
            sa.ForeignKey("publishing_plugs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            sa.BigInteger(),
            sa.ForeignKey("publication_targets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint(
            "plug_id", "target_id", name="uniq_publishing_plug_runs_plug_target"
        ),
    )


def downgrade() -> None:
    op.drop_table("publishing_plug_runs")
    op.drop_index("ix_publishing_plugs_account_id", table_name="publishing_plugs")
    op.drop_table("publishing_plugs")
