"""calls: WhatsApp voice calls answered from the browser (F7)

Revision ID: d9e0f1a2b3c5
Revises: c8d9e0f1a2b4
Create Date: 2026-11-14 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d9e0f1a2b3c5"
down_revision: str | None = "c8d9e0f1a2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calls",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inbox_id", sa.BigInteger(), sa.ForeignKey("inboxes.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "conversation_id",
            sa.BigInteger(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("contact_id", sa.BigInteger(), sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("message_id", sa.BigInteger(), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(16), server_default="whatsapp", nullable=False),
        sa.Column("provider_call_id", sa.String(), nullable=False),
        sa.Column("direction", sa.String(8), server_default="inbound", nullable=False),
        sa.Column("status", sa.String(16), server_default="ringing", nullable=False),
        sa.Column("from_number", sa.String(), nullable=True),
        sa.Column("to_number", sa.String(), nullable=True),
        sa.Column("sdp_offer", sa.Text(), nullable=True),
        sa.Column("answered_by_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("end_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("index_calls_on_account_id_and_status", "calls", ["account_id", "status"])
    op.create_index("index_calls_on_provider_call_id", "calls", ["provider_call_id"], unique=True)
    op.create_index("index_calls_on_conversation_id", "calls", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("calls")
