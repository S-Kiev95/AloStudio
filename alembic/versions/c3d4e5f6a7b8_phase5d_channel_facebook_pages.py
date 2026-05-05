"""phase5d: channel_facebook_pages

Adds the table backing ``Channel::FacebookPage``. See
:class:`app.domains.inboxes.models.FacebookPage` for the field-level
rationale.

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-02 03:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel_facebook_pages",
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
        sa.Column("page_id", sa.String(), nullable=False),
        sa.Column("page_access_token", sa.String(), nullable=False),
        sa.Column("user_access_token", sa.String(), nullable=False),
        sa.Column("instagram_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "index_channel_facebook_pages_on_page_id",
        "channel_facebook_pages",
        ["page_id"],
    )
    op.create_index(
        "index_channel_facebook_pages_on_page_id_and_account_id",
        "channel_facebook_pages",
        ["page_id", "account_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "index_channel_facebook_pages_on_page_id_and_account_id",
        table_name="channel_facebook_pages",
    )
    op.drop_index(
        "index_channel_facebook_pages_on_page_id",
        table_name="channel_facebook_pages",
    )
    op.drop_table("channel_facebook_pages")
