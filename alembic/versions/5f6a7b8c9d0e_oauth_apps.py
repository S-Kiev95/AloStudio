"""oauth apps: AloStudio as an OAuth 2.0 authorization server

Adds ``oauth_applications`` (registered clients), ``oauth_authorization_codes``
(the consent's single-use codes) and ``oauth_tokens`` (access and refresh
tokens). Secrets, codes and tokens are stored hashed.

Revision ID: 5f6a7b8c9d0e
Revises: 4e5f6a7b8c9d
Create Date: 2026-10-30 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "5f6a7b8c9d0e"
down_revision: str | None = "4e5f6a7b8c9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def _fk(column: str, target: str, *, nullable: bool = False, ondelete: str = "CASCADE") -> sa.Column:
    return sa.Column(
        column,
        sa.BigInteger(),
        sa.ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
    )


def upgrade() -> None:
    op.create_table(
        "oauth_applications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        _fk("account_id", "accounts.id"),
        _fk("created_by_id", "users.id", nullable=True, ondelete="SET NULL"),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=False),
        sa.Column("client_secret_hash", sa.String(), nullable=True),
        sa.Column("redirect_uris", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("client_id", name="uniq_oauth_applications_client_id"),
    )
    op.create_index("ix_oauth_applications_account_id", "oauth_applications", ["account_id"])
    op.create_table(
        "oauth_authorization_codes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        _fk("application_id", "oauth_applications.id"),
        _fk("account_id", "accounts.id"),
        _fk("user_id", "users.id"),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("redirect_uri", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("code_challenge", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("code_hash", name="uniq_oauth_authorization_codes_code_hash"),
    )
    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        _fk("application_id", "oauth_applications.id"),
        _fk("account_id", "accounts.id"),
        _fk("user_id", "users.id"),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("access_token_hash", sa.String(), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_token_hash", sa.String(), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("access_token_hash", name="uniq_oauth_tokens_access_token_hash"),
        sa.UniqueConstraint("refresh_token_hash", name="uniq_oauth_tokens_refresh_token_hash"),
    )
    op.create_index(
        "ix_oauth_tokens_grant", "oauth_tokens", ["application_id", "account_id", "user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_oauth_tokens_grant", table_name="oauth_tokens")
    op.drop_table("oauth_tokens")
    op.drop_table("oauth_authorization_codes")
    op.drop_index("ix_oauth_applications_account_id", table_name="oauth_applications")
    op.drop_table("oauth_applications")
