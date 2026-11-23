"""decisions: who decides (service or local model), business context, priority owner (F10)

Revision ID: d3f5b7c9e1a2
Revises: b1c2d3e4f5a8
Create Date: 2026-11-19 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d3f5b7c9e1a2"
down_revision: str | None = "b1c2d3e4f5a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "decision_settings",
        sa.Column("provider", sa.String(16), nullable=False, server_default="api"),
    )
    op.add_column("decision_settings", sa.Column("context", sa.Text(), nullable=True))
    op.add_column(
        "decision_settings",
        sa.Column("apply_priority", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_table(
        "conversation_priority_owners",
        sa.Column(
            "conversation_id",
            sa.BigInteger(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner", sa.String(8), nullable=False),
        sa.Column("ai_level", sa.String(16), nullable=True),
        sa.Column("corrected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("corrected_level", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "index_conversation_priority_owners_on_account",
        "conversation_priority_owners",
        ["account_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "index_conversation_priority_owners_on_account", table_name="conversation_priority_owners"
    )
    op.drop_table("conversation_priority_owners")
    op.drop_column("decision_settings", "apply_priority")
    op.drop_column("decision_settings", "context")
    op.drop_column("decision_settings", "provider")
