"""phase8: webhooks

Adds the ``webhooks`` table backing
:class:`app.domains.webhooks.models.Webhook`.

Mirrors ``reference/chatwoot/db/schema.rb`` (v4.13.0).

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-05-13 01:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3b4c5d6e7f8"
down_revision: str | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webhooks",
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
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "webhook_type",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "subscriptions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("secret", sa.String(), nullable=True),
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
        "index_webhooks_on_account_id_and_url",
        "webhooks",
        ["account_id", "url"],
    )
    op.create_index(
        "index_webhooks_account_lookup",
        "webhooks",
        ["account_id"],
    )


def downgrade() -> None:
    op.drop_index("index_webhooks_account_lookup", table_name="webhooks")
    op.drop_constraint(
        "index_webhooks_on_account_id_and_url",
        "webhooks",
        type_="unique",
    )
    op.drop_table("webhooks")
