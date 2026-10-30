"""agent chat: a user's chats with the AI that drafts and schedules publications

Adds ``agent_threads`` (one per chat, private to its user) and
``agent_messages`` (the chat history the model sees, tool calls included).

Revision ID: 4e5f6a7b8c9d
Revises: 3d4e5f6a7b8c
Create Date: 2026-10-30 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "4e5f6a7b8c9d"
down_revision: str | None = "3d4e5f6a7b8c"
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
        "agent_threads",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
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
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=True),
        sa.Column("running_since", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "ix_agent_threads_account_id_user_id", "agent_threads", ["account_id", "user_id"]
    )
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "thread_id",
            sa.BigInteger(),
            sa.ForeignKey("agent_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tool_calls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tool_call_id", sa.String(), nullable=True),
        sa.Column("tool_name", sa.String(), nullable=True),
        sa.Column("tool_arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_agent_messages_thread_id", "agent_messages", ["thread_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_messages_thread_id", table_name="agent_messages")
    op.drop_table("agent_messages")
    op.drop_index("ix_agent_threads_account_id_user_id", table_name="agent_threads")
    op.drop_table("agent_threads")
