"""mcp: mcp_tokens

Adds the ``mcp_tokens`` table — API tokens issued specifically for
MCP agent clients (separate from the polymorphic ``access_tokens``
table used by the dashboard's User/AgentBot tokens).

Each token is account-scoped (an MCP agent acts on behalf of an
Account, not a User) with a permission ``scope`` (read / write /
admin) that the tool dispatch checks.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-05-18 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: str | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_tokens",
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
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column(
            "scope",
            sa.String(),
            nullable=False,
            server_default="read",
        ),
        sa.Column(
            "last_used_at", sa.DateTime(timezone=True), nullable=True
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
        "index_mcp_tokens_on_token", "mcp_tokens", ["token"]
    )
    op.create_index(
        "index_mcp_tokens_on_account_id",
        "mcp_tokens",
        ["account_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "index_mcp_tokens_on_account_id", table_name="mcp_tokens"
    )
    op.drop_constraint(
        "index_mcp_tokens_on_token", "mcp_tokens", type_="unique"
    )
    op.drop_table("mcp_tokens")
