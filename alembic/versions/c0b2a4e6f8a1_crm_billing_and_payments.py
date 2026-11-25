"""crm: billing terms, installments, payments and allocations (cobranzas)

Adds payment terms and due date to ``crm_opportunities``, plus tables for
installments (``crm_installments``), client payments (``crm_payments``) and
payment allocations (``crm_payment_allocations``).

Revision ID: c0b2a4e6f8a1
Revises: f5b7d9e1a3c5
Create Date: 2026-11-24 22:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c0b2a4e6f8a1"
down_revision: str | None = "f5b7d9e1a3c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("crm_opportunities", sa.Column("payment_terms", sa.String(16), nullable=True))
    op.add_column("crm_opportunities", sa.Column("due_on", sa.Date(), nullable=True))

    op.create_table(
        "crm_installments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            sa.BigInteger(),
            sa.ForeignKey("crm_opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "opportunity_id", "number", name="uq_crm_installments_opportunity_number"
        ),
    )
    op.create_index("index_crm_installments_on_account_id", "crm_installments", ["account_id"])
    op.create_index(
        "index_crm_installments_on_opportunity_id", "crm_installments", ["opportunity_id"]
    )
    op.create_index(
        "index_crm_installments_on_account_due_on", "crm_installments", ["account_id", "due_on"]
    )

    op.create_table(
        "crm_payments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            sa.BigInteger(),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("method", sa.String(16), nullable=False, server_default="cash"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("index_crm_payments_on_account_id", "crm_payments", ["account_id"])
    op.create_index(
        "index_crm_payments_on_account_contact", "crm_payments", ["account_id", "contact_id"]
    )
    op.create_index(
        "index_crm_payments_on_account_paid_on", "crm_payments", ["account_id", "paid_on"]
    )

    op.create_table(
        "crm_payment_allocations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "payment_id",
            sa.BigInteger(),
            sa.ForeignKey("crm_payments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            sa.BigInteger(),
            sa.ForeignKey("crm_opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "installment_id",
            sa.BigInteger(),
            sa.ForeignKey("crm_installments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "index_crm_payment_allocations_on_account_id", "crm_payment_allocations", ["account_id"]
    )
    op.create_index(
        "index_crm_payment_allocations_on_payment_id", "crm_payment_allocations", ["payment_id"]
    )
    op.create_index(
        "index_crm_payment_allocations_on_opportunity_id",
        "crm_payment_allocations",
        ["opportunity_id"],
    )
    op.create_index(
        "index_crm_payment_allocations_on_installment_id",
        "crm_payment_allocations",
        ["installment_id"],
    )


def downgrade() -> None:
    op.drop_table("crm_payment_allocations")
    op.drop_table("crm_payments")
    op.drop_table("crm_installments")
    op.drop_column("crm_opportunities", "due_on")
    op.drop_column("crm_opportunities", "payment_terms")
