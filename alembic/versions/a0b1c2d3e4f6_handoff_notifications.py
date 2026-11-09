"""notifications: WhatsApp notice preferences and the bot handoff type

Adds ``whatsapp_subscriptions`` / ``whatsapp_number`` to
``notification_settings`` (opt-in, empty for everyone).

Existing users who receive at least one in-app (push) notification also get
the new ``conversation_bot_handoff`` type in ``push_subscriptions``, so a bot
handoff reaches them without visiting the settings. Users who turned every
push off stay that way.

Revision ID: a0b1c2d3e4f6
Revises: 6a7b8c9d0e1f
Create Date: 2026-11-09 20:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a0b1c2d3e4f6"
down_revision: str | None = "6a7b8c9d0e1f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_settings",
        sa.Column(
            "whatsapp_subscriptions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "notification_settings",
        sa.Column("whatsapp_number", sa.String(), nullable=True),
    )
    op.execute(
        "UPDATE notification_settings "
        "SET push_subscriptions = "
        "(push_subscriptions::jsonb || '[\"conversation_bot_handoff\"]'::jsonb)::json "
        "WHERE json_array_length(push_subscriptions) > 0 "
        "AND NOT (push_subscriptions::jsonb ? 'conversation_bot_handoff')"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE notification_settings "
        "SET push_subscriptions = "
        "(push_subscriptions::jsonb - 'conversation_bot_handoff')::json"
    )
    op.drop_column("notification_settings", "whatsapp_number")
    op.drop_column("notification_settings", "whatsapp_subscriptions")
