"""lifecycle: contact stages, from new lead to customer (F17)

Revision ID: f9a0b1c2d3e6
Revises: e8f9a0b1c2d5
Create Date: 2026-11-17 20:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f9a0b1c2d3e6"
down_revision: str | None = "e8f9a0b1c2d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "lifecycle_settings",
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("stages", sa.JSON(), nullable=True),
        *_timestamps(),
    )
    op.create_table(
        "contact_lifecycles",
        sa.Column(
            "contact_id",
            sa.BigInteger(),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_key", sa.String(40), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "index_contact_lifecycles_on_account_stage", "contact_lifecycles", ["account_id", "stage_key"]
    )
    op.create_table(
        "contact_lifecycle_changes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_key", sa.String(40), nullable=True),
        sa.Column("to_key", sa.String(40), nullable=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "index_contact_lifecycle_changes_on_account_created",
        "contact_lifecycle_changes",
        ["account_id", "created_at"],
    )
    op.create_index(
        "index_contact_lifecycle_changes_on_contact", "contact_lifecycle_changes", ["contact_id"]
    )


def downgrade() -> None:
    op.drop_table("contact_lifecycle_changes")
    op.drop_table("contact_lifecycles")
    op.drop_table("lifecycle_settings")
