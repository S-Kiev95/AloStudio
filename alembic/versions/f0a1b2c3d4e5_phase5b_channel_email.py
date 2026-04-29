"""phase5b: channel_email

Adds the table backing ``Channel::Email``. See
:class:`app.domains.inboxes.models.EmailChannel` for the field-level
rationale; OAuth surface (provider / provider_config) ships empty in
5b and gets wired in Phase 9.

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-04-29 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f0a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "e9f0a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel_email",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("forward_to_email", sa.String(), nullable=False),
        # IMAP
        sa.Column(
            "imap_enabled",
            sa.Boolean(),
            server_default="false",
            nullable=True,
        ),
        sa.Column(
            "imap_address", sa.String(), server_default="", nullable=True
        ),
        sa.Column(
            "imap_port", sa.Integer(), server_default="0", nullable=True
        ),
        sa.Column(
            "imap_login", sa.String(), server_default="", nullable=True
        ),
        sa.Column(
            "imap_password", sa.String(), server_default="", nullable=True
        ),
        sa.Column(
            "imap_enable_ssl",
            sa.Boolean(),
            server_default="true",
            nullable=True,
        ),
        # SMTP
        sa.Column(
            "smtp_enabled",
            sa.Boolean(),
            server_default="false",
            nullable=True,
        ),
        sa.Column(
            "smtp_address", sa.String(), server_default="", nullable=True
        ),
        sa.Column(
            "smtp_port", sa.Integer(), server_default="0", nullable=True
        ),
        sa.Column(
            "smtp_login", sa.String(), server_default="", nullable=True
        ),
        sa.Column(
            "smtp_password", sa.String(), server_default="", nullable=True
        ),
        sa.Column(
            "smtp_domain", sa.String(), server_default="", nullable=True
        ),
        sa.Column(
            "smtp_authentication",
            sa.String(),
            server_default="login",
            nullable=True,
        ),
        sa.Column(
            "smtp_enable_ssl_tls",
            sa.Boolean(),
            server_default="false",
            nullable=True,
        ),
        sa.Column(
            "smtp_enable_starttls_auto",
            sa.Boolean(),
            server_default="true",
            nullable=True,
        ),
        sa.Column(
            "smtp_openssl_verify_mode",
            sa.String(),
            server_default="none",
            nullable=True,
        ),
        sa.Column(
            "verified_for_sending",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        # OAuth (Phase 9 — empty here)
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column(
            "provider_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "index_channel_email_on_email",
        "channel_email",
        ["email"],
        unique=True,
    )
    op.create_index(
        "index_channel_email_on_forward_to_email",
        "channel_email",
        ["forward_to_email"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "index_channel_email_on_forward_to_email",
        table_name="channel_email",
    )
    op.drop_index(
        "index_channel_email_on_email", table_name="channel_email"
    )
    op.drop_table("channel_email")
