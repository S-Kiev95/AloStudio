"""decisions: shadow-mode decisions about conversations and people's labels (F10)

Revision ID: a2b3c4d5e6f9
Revises: f1a2b3c4d5e7
Create Date: 2026-11-15 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a2b3c4d5e6f9"
down_revision: str | None = "f1a2b3c4d5e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "decision_settings",
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("questions", sa.JSON(), nullable=True),
        *_timestamps(),
    )
    op.create_table(
        "conversation_decisions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "conversation_id",
            sa.BigInteger(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("question", sa.String(64), nullable=False),
        sa.Column("answer", sa.String(128), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("probabilities", sa.JSON(), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "index_conversation_decisions_on_conversation", "conversation_decisions", ["conversation_id"]
    )
    op.create_index(
        "index_conversation_decisions_on_account_question",
        "conversation_decisions",
        ["account_id", "question"],
    )
    op.create_table(
        "conversation_human_decisions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "conversation_id",
            sa.BigInteger(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question", sa.String(64), nullable=False),
        sa.Column("answer", sa.String(128), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("conversation_id", "question", name="uniq_human_decision_question"),
    )
    op.create_index(
        "index_conversation_human_decisions_on_account", "conversation_human_decisions", ["account_id"]
    )


def downgrade() -> None:
    op.drop_table("conversation_human_decisions")
    op.drop_table("conversation_decisions")
    op.drop_table("decision_settings")
