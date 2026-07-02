"""canned_responses

Adds the ``canned_responses`` table backing
:class:`app.domains.canned_responses.models.CannedResponse`.

Mirrors ``reference/chatwoot/db/schema.rb`` (table ``canned_responses``,
v4.13.0). Chatwoot's original is ``id: :serial`` with no indexes beyond
the PK; we use a ``BigInteger`` PK (the AloStudio standard) and add an
``account_id`` index since every query is account-scoped.

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-07-02 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: str | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "canned_responses",
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
        sa.Column("short_code", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
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
        "index_canned_responses_on_account_id",
        "canned_responses",
        ["account_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "index_canned_responses_on_account_id",
        table_name="canned_responses",
    )
    op.drop_table("canned_responses")
