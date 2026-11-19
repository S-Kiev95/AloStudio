"""handoff rules: who takes a handed-off conversation (agente-ia, paso 2a)

Revision ID: b1d3f5a7c9e2
Revises: b1c2d3e4f5a8
Create Date: 2026-11-17 20:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b1d3f5a7c9e2"
down_revision: str | None = "b1c2d3e4f5a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "handoff_rules",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column(
            "label_id", sa.BigInteger(), sa.ForeignKey("labels.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column(
            "contact_id",
            sa.BigInteger(),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("to_ai", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uniq_handoff_rules_account",
        "handoff_rules",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("scope = 'account'"),
    )
    op.create_index(
        "uniq_handoff_rules_label",
        "handoff_rules",
        ["account_id", "label_id"],
        unique=True,
        postgresql_where=sa.text("label_id IS NOT NULL"),
    )
    op.create_index(
        "uniq_handoff_rules_contact",
        "handoff_rules",
        ["account_id", "contact_id"],
        unique=True,
        postgresql_where=sa.text("contact_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uniq_handoff_rules_contact", table_name="handoff_rules")
    op.drop_index("uniq_handoff_rules_label", table_name="handoff_rules")
    op.drop_index("uniq_handoff_rules_account", table_name="handoff_rules")
    op.drop_table("handoff_rules")
