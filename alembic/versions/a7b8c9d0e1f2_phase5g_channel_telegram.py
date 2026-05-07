"""phase5g: channel_telegram

Adds the table backing ``Channel::Telegram``. See
:class:`app.domains.inboxes.models.TelegramChannel` for the
field-level rationale.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-06 20:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel_telegram",
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
        sa.Column("bot_token", sa.String(), nullable=False),
        sa.Column("bot_name", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "index_channel_telegram_on_bot_token",
        "channel_telegram",
        ["bot_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "index_channel_telegram_on_bot_token",
        table_name="channel_telegram",
    )
    op.drop_table("channel_telegram")
