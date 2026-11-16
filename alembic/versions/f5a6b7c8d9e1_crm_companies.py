"""crm: companies (F11)

``contacts.company_id`` already exists (kept from Chatwoot's schema, no
foreign key); this adds the table it points to. The column stays without a
foreign key: the app clears it when a company is deleted.

Revision ID: f5a6b7c8d9e1
Revises: e4f5a6b7c8d0
Create Date: 2026-11-13 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f5a6b7c8d9e1"
down_revision: str | None = "e4f5a6b7c8d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crm_companies",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("website", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("tax_id", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("index_crm_companies_on_account_id", "crm_companies", ["account_id"])
    # Whatever an older import left in contacts.company_id points nowhere.
    op.execute("UPDATE contacts SET company_id = NULL WHERE company_id IS NOT NULL")


def downgrade() -> None:
    op.drop_table("crm_companies")
