"""products catalogue + instagram_post_products join

Adds the account-scoped ``products`` table and the
``instagram_post_products`` M2M join so an Instagram post/story can link
to 0..N products (CRM context for AI replies).

Plan: ``PLAN.instagram-graph.md`` (I.11 milestone).

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-21 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- products --------------------------------------------------------
    op.create_table(
        "products",
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
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sku", sa.String(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
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
        "index_products_on_account_id", "products", ["account_id"]
    )

    # ----- instagram_post_products (join) ----------------------------------
    op.create_table(
        "instagram_post_products",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "post_id",
            sa.BigInteger(),
            sa.ForeignKey("instagram_posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
    op.create_unique_constraint(
        "index_instagram_post_products_post_product",
        "instagram_post_products",
        ["post_id", "product_id"],
    )
    op.create_index(
        "index_instagram_post_products_on_product_id",
        "instagram_post_products",
        ["product_id"],
    )


def downgrade() -> None:
    op.drop_table("instagram_post_products")
    op.drop_table("products")
