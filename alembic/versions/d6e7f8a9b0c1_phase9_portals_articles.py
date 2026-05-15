"""phase9: portals + categories + articles

Mirrors ``reference/chatwoot/db/schema.rb`` (v4.13.0).

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-05-14 01:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d6e7f8a9b0c1"
down_revision: str | None = "c5d6e7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- portals --------------------------------------------------------
    op.create_table(
        "portals",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("custom_domain", sa.String(), nullable=True),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("homepage_link", sa.String(), nullable=True),
        sa.Column("page_title", sa.String(), nullable=True),
        sa.Column("header_text", sa.Text(), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='{"allowed_locales": ["en"]}',
        ),
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("channel_web_widget_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "ssl_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
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
        "index_portals_on_slug", "portals", ["slug"]
    )
    op.create_unique_constraint(
        "index_portals_on_custom_domain",
        "portals",
        ["custom_domain"],
    )
    op.create_index(
        "index_portals_on_channel_web_widget_id",
        "portals",
        ["channel_web_widget_id"],
    )

    # ----- categories -----------------------------------------------------
    op.create_table(
        "categories",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "portal_id",
            sa.Integer(),
            sa.ForeignKey("portals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column(
            "locale",
            sa.String(),
            nullable=False,
            server_default="en",
        ),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("parent_category_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "associated_category_id", sa.BigInteger(), nullable=True
        ),
        sa.Column(
            "icon",
            sa.String(),
            nullable=False,
            server_default="",
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
        "index_categories_on_slug_and_locale_and_portal_id",
        "categories",
        ["slug", "locale", "portal_id"],
    )
    op.create_index(
        "index_categories_on_locale_and_account_id",
        "categories",
        ["locale", "account_id"],
    )
    op.create_index(
        "index_categories_on_locale", "categories", ["locale"]
    )
    op.create_index(
        "index_categories_on_parent_category_id",
        "categories",
        ["parent_category_id"],
    )
    op.create_index(
        "index_categories_on_associated_category_id",
        "categories",
        ["associated_category_id"],
    )
    # Self-FKs come after creation.
    op.create_foreign_key(
        "fk_categories_parent_category_id",
        "categories",
        "categories",
        ["parent_category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_categories_associated_category_id",
        "categories",
        "categories",
        ["associated_category_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ----- articles -------------------------------------------------------
    op.create_table(
        "articles",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "portal_id",
            sa.Integer(),
            sa.ForeignKey("portals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("folder_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "views",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "author_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("associated_article_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column(
            "locale",
            sa.String(),
            nullable=False,
            server_default="en",
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
        "index_articles_on_slug", "articles", ["slug"]
    )
    op.create_index(
        "index_articles_on_account_id", "articles", ["account_id"]
    )
    op.create_index(
        "index_articles_on_portal_id", "articles", ["portal_id"]
    )
    op.create_index(
        "index_articles_on_author_id", "articles", ["author_id"]
    )
    op.create_index(
        "index_articles_on_status", "articles", ["status"]
    )
    op.create_index(
        "index_articles_on_views", "articles", ["views"]
    )
    op.create_index(
        "index_articles_on_associated_article_id",
        "articles",
        ["associated_article_id"],
    )
    op.create_foreign_key(
        "fk_articles_associated_article_id",
        "articles",
        "articles",
        ["associated_article_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_articles_associated_article_id",
        "articles",
        type_="foreignkey",
    )
    op.drop_table("articles")
    op.drop_constraint(
        "fk_categories_associated_category_id",
        "categories",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_categories_parent_category_id",
        "categories",
        type_="foreignkey",
    )
    op.drop_table("categories")
    op.drop_table("portals")
