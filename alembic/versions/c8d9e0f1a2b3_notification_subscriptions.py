"""notification_subscriptions

Adds ``notification_subscriptions`` — a registered browser Push API endpoint
per user, backing :class:`NotificationSubscription`.

Mirrors ``reference/chatwoot/db/schema.rb`` (v4.13.0). We use ``JSON`` for
``subscription_attributes`` (the codebase's convention) and a ``BigInteger``
PK.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-07-05 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d9e0f1a2b3"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_subscriptions",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("identifier", sa.String(), nullable=False),
        sa.Column(
            "subscription_type",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("subscription_attributes", sa.JSON(), nullable=False),
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
        "index_notification_subscriptions_on_user_id",
        "notification_subscriptions",
        ["user_id"],
    )
    op.create_index(
        "index_notification_subscriptions_on_identifier",
        "notification_subscriptions",
        ["identifier"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "index_notification_subscriptions_on_identifier",
        table_name="notification_subscriptions",
    )
    op.drop_index(
        "index_notification_subscriptions_on_user_id",
        table_name="notification_subscriptions",
    )
    op.drop_table("notification_subscriptions")
