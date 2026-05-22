"""instagram_channel_settings (connection capability metadata)

Records how a ``channel_instagram`` row was connected — ``login_type``
(facebook / instagram) drives capabilities (e.g. DELETE media is only
available on Facebook Login). Kept in a separate table so the Phase 5e
mirror model stays untouched.

Plan: ``PLAN.instagram-graph.md`` (I.10 milestone).

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-05-22 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: str | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instagram_channel_settings",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "channel_instagram_id",
            sa.BigInteger(),
            sa.ForeignKey("channel_instagram.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "login_type",
            sa.String(),
            nullable=False,
            server_default="facebook",
        ),
        sa.Column(
            "connect_method",
            sa.String(),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("page_id", sa.String(), nullable=True),
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
    op.create_unique_constraint(
        "index_instagram_channel_settings_on_channel_id",
        "instagram_channel_settings",
        ["channel_instagram_id"],
    )


def downgrade() -> None:
    op.drop_table("instagram_channel_settings")
