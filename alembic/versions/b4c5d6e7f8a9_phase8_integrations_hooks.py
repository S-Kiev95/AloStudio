"""phase8: integrations_hooks

Mirrors ``reference/chatwoot/db/schema.rb`` (v4.13.0).

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-05-13 02:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4c5d6e7f8a9"
down_revision: str | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integrations_hooks",
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
            "inbox_id",
            sa.Integer(),
            sa.ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("app_id", sa.String(), nullable=False),
        sa.Column(
            "hook_type",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "status",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("reference_id", sa.String(), nullable=True),
        sa.Column("access_token", sa.String(), nullable=True),
        sa.Column(
            "settings",
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


def downgrade() -> None:
    op.drop_table("integrations_hooks")
