"""assignment_policies

Adds ``assignment_policies`` + ``inbox_assignment_policies`` backing
:class:`AssignmentPolicy` / :class:`InboxAssignmentPolicy`.

Mirrors ``reference/chatwoot/db/schema.rb`` (v4.13.0).

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-07-05 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9e0f1a2b3c4"
down_revision: str | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assignment_policies",
        sa.Column(
            "id", sa.BigInteger(), primary_key=True, autoincrement=True,
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
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column(
            "assignment_order", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "conversation_priority",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "fair_distribution_limit",
            sa.Integer(),
            nullable=False,
            server_default="100",
        ),
        sa.Column(
            "fair_distribution_window",
            sa.Integer(),
            nullable=False,
            server_default="3600",
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
        "index_assignment_policies_on_account_id",
        "assignment_policies",
        ["account_id"],
    )
    op.create_index(
        "index_assignment_policies_on_enabled",
        "assignment_policies",
        ["enabled"],
    )
    op.create_index(
        "index_assignment_policies_on_account_id_and_name",
        "assignment_policies",
        ["account_id", "name"],
        unique=True,
    )

    op.create_table(
        "inbox_assignment_policies",
        sa.Column(
            "id", sa.BigInteger(), primary_key=True, autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "inbox_id",
            sa.BigInteger(),
            sa.ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assignment_policy_id",
            sa.BigInteger(),
            sa.ForeignKey("assignment_policies.id", ondelete="CASCADE"),
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
    op.create_index(
        "index_inbox_assignment_policies_on_assignment_policy_id",
        "inbox_assignment_policies",
        ["assignment_policy_id"],
    )
    op.create_index(
        "index_inbox_assignment_policies_on_inbox_id",
        "inbox_assignment_policies",
        ["inbox_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("inbox_assignment_policies")
    op.drop_table("assignment_policies")
