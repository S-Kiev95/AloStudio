"""v2.5: notifications + notification_settings

Two new tables for the in-app notifications inbox (PLAN.frontend-v2.md
§v2.5). Wire-shape-compatible with Chatwoot upstream:

  * ``notifications`` keeps the polymorphic ``primary_actor`` /
    ``secondary_actor`` columns + the int enum ``notification_type``.
  * ``notification_settings`` swaps Chatwoot's bit-packed
    ``email_flags`` / ``push_flags`` ints for two JSONB arrays of
    notification-type-strings. Cleaner in Python; the API surfaces
    the same ``selected_email_flags`` / ``selected_push_flags`` lists.

Revision ID: b1c2d3e4f5a6
Revises: f4a5b6c7d8e9
Create Date: 2026-06-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
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
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("notification_type", sa.Integer(), nullable=False),
        sa.Column("primary_actor_type", sa.String(), nullable=False),
        sa.Column("primary_actor_id", sa.BigInteger(), nullable=False),
        sa.Column("secondary_actor_type", sa.String(), nullable=True),
        sa.Column("secondary_actor_id", sa.BigInteger(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("snoozed_until", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "last_activity_at", sa.DateTime(timezone=False), nullable=True
        ),
        sa.Column(
            "meta",
            sa.JSON(),
            nullable=True,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_notifications_account_id", "notifications", ["account_id"]
    )
    op.create_index(
        "ix_notifications_user_id", "notifications", ["user_id"]
    )
    op.create_index(
        "ix_notifications_last_activity_at",
        "notifications",
        ["last_activity_at"],
    )
    op.create_index(
        "ix_notifications_performance",
        "notifications",
        ["user_id", "account_id", "snoozed_until", "read_at"],
    )

    op.create_table(
        "notification_settings",
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
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "email_subscriptions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column(
            "push_subscriptions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "account_id", "user_id", name="by_account_user"
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_settings")
    op.drop_index("ix_notifications_performance", table_name="notifications")
    op.drop_index("ix_notifications_last_activity_at", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_account_id", table_name="notifications")
    op.drop_table("notifications")
