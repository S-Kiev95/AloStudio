"""phase5e: channel_instagram

Adds the table backing ``Channel::Instagram`` (the modern "Direct
Instagram Login" path; the legacy FB-page-connected IG variant lives
on :class:`FacebookPage.instagram_id`). See
:class:`app.domains.inboxes.models.InstagramChannel` for the
field-level rationale.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-06 18:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel_instagram",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("instagram_id", sa.String(), nullable=False),
        sa.Column("access_token", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "index_channel_instagram_on_instagram_id",
        "channel_instagram",
        ["instagram_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "index_channel_instagram_on_instagram_id",
        table_name="channel_instagram",
    )
    op.drop_table("channel_instagram")
