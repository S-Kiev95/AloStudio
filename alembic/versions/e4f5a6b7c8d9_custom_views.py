"""saved views: custom_views

Backs the ``custom_filters`` route — named filter-DSL views, private to
the user who saved them. ``query`` holds the filter payload
(``{"payload": [<condition>, ...]}``); ``filter_type`` is the int enum
(conversation=0, contact=1).

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-06-29 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "custom_views",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "filter_type",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "query",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "index_custom_views_on_account_id", "custom_views", ["account_id"]
    )
    op.create_index(
        "index_custom_views_on_user_id", "custom_views", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("index_custom_views_on_user_id", table_name="custom_views")
    op.drop_index(
        "index_custom_views_on_account_id", table_name="custom_views"
    )
    op.drop_table("custom_views")
