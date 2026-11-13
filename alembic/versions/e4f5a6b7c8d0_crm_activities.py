"""crm: activities and tasks (F11)

Revision ID: e4f5a6b7c8d0
Revises: d3e4f5a6b7c9
Create Date: 2026-11-13 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4f5a6b7c8d0"
down_revision: str | None = "d3e4f5a6b7c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crm_activities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), server_default="task", nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contact_id", sa.BigInteger(), sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("opportunity_id", sa.BigInteger(), sa.ForeignKey("crm_opportunities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reminded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("index_crm_activities_on_account_id", "crm_activities", ["account_id"])
    op.create_index("index_crm_activities_on_owner_id", "crm_activities", ["owner_id"])
    op.create_index("index_crm_activities_on_contact_id", "crm_activities", ["contact_id"])
    op.create_index("index_crm_activities_on_opportunity_id", "crm_activities", ["opportunity_id"])
    op.create_index(
        "index_crm_activities_pending_due", "crm_activities", ["due_at", "done_at", "reminded_at"]
    )


def downgrade() -> None:
    op.drop_table("crm_activities")
