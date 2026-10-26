"""crm appointments agenda table

Adds the account-scoped ``appointments`` table for CRM scheduling and
``external_id`` columns on ``products`` and ``appointments`` for idempotent
Postiz CRM import.

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-10-26 00:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c6d7e8f9a0b1"
down_revision: str | None = "b5c6d7e8f9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("external_id", sa.String(), nullable=True),
    )
    op.create_unique_constraint(
        "uniq_products_account_external_id",
        "products",
        ["account_id", "external_id"],
    )

    op.create_table(
        "appointments",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
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
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "starts_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "ends_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("external_id", sa.String(), nullable=True),
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
    )
    op.create_index(
        "index_appointments_on_account_id",
        "appointments",
        ["account_id"],
    )
    op.create_index(
        "index_appointments_on_contact_id",
        "appointments",
        ["contact_id"],
    )
    op.create_index(
        "index_appointments_on_account_id_and_starts_at",
        "appointments",
        ["account_id", "starts_at"],
    )
    op.create_index(
        "ix_appointments_product_id",
        "appointments",
        ["product_id"],
    )
    op.create_index(
        "ix_appointments_created_by_id",
        "appointments",
        ["created_by_id"],
    )
    op.create_unique_constraint(
        "uniq_appointments_account_external_id",
        "appointments",
        ["account_id", "external_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uniq_appointments_account_external_id",
        "appointments",
        type_="unique",
    )
    op.drop_index("ix_appointments_created_by_id", table_name="appointments")
    op.drop_index("ix_appointments_product_id", table_name="appointments")
    op.drop_index(
        "index_appointments_on_account_id_and_starts_at",
        table_name="appointments",
    )
    op.drop_index(
        "index_appointments_on_contact_id",
        table_name="appointments",
    )
    op.drop_index(
        "index_appointments_on_account_id",
        table_name="appointments",
    )
    op.drop_table("appointments")
    op.drop_constraint(
        "uniq_products_account_external_id",
        "products",
        type_="unique",
    )
    op.drop_column("products", "external_id")
