"""closing: why a conversation was closed, and the account's categories (F17)

Revision ID: d7e8f9a0b1c4
Revises: c6d7e8f9a0b3
Create Date: 2026-11-17 01:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7e8f9a0b1c4"
down_revision: str | None = "c6d7e8f9a0b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "closing_settings",
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("required", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("categories", sa.JSON(), nullable=True),
        *_timestamps(),
    )
    op.create_table(
        "conversation_closings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "conversation_id",
            sa.BigInteger(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(60), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "index_conversation_closings_on_account_created",
        "conversation_closings",
        ["account_id", "created_at"],
    )
    op.create_index(
        "index_conversation_closings_on_conversation", "conversation_closings", ["conversation_id"]
    )


def downgrade() -> None:
    op.drop_table("conversation_closings")
    op.drop_table("closing_settings")
