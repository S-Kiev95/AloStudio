"""phase10: enterprise-only schema sweep (audits + sla_policies +
applied_slas).

These three tables live in ``reference/chatwoot/db/schema.rb`` v4.13.0
and are written by ``audited`` gem hooks and the enterprise SLA
controllers respectively. The controllers + models live in
``reference/chatwoot/enterprise/`` and are out of OSS parity scope.

We ship the tables here so:
  * pg_dump → pg_restore round-trip from a Chatwoot reference works
    without column drift.
  * A future enterprise reactivation can land its SQLModel + service
    layer without needing another migration.

No SQLModel classes; no router; no service code — just the columns +
indexes byte-for-byte with the reference.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-05-14 03:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f8a9b0c1d2e3"
down_revision: str | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- audits (the ``audited`` gem table) -----------------------------
    op.create_table(
        "audits",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("auditable_id", sa.BigInteger(), nullable=True),
        sa.Column("auditable_type", sa.String(), nullable=True),
        sa.Column("associated_id", sa.BigInteger(), nullable=True),
        sa.Column("associated_type", sa.String(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("user_type", sa.String(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=True),
        sa.Column(
            "audited_changes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column("remote_address", sa.String(), nullable=True),
        sa.Column("request_uuid", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=True,
        ),
    )
    op.create_index(
        "associated_index",
        "audits",
        ["associated_type", "associated_id"],
    )
    op.create_index(
        "auditable_index",
        "audits",
        ["auditable_type", "auditable_id", "version"],
    )
    op.create_index(
        "index_audits_on_created_at", "audits", ["created_at"]
    )
    op.create_index(
        "index_audits_on_request_uuid", "audits", ["request_uuid"]
    )
    op.create_index(
        "user_index", "audits", ["user_id", "user_type"]
    )

    # ----- sla_policies ----------------------------------------------------
    op.create_table(
        "sla_policies",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "first_response_time_threshold", sa.Float(), nullable=True
        ),
        sa.Column(
            "next_response_time_threshold", sa.Float(), nullable=True
        ),
        sa.Column(
            "only_during_business_hours",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
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
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "resolution_time_threshold", sa.Float(), nullable=True
        ),
    )
    op.create_index(
        "index_sla_policies_on_account_id",
        "sla_policies",
        ["account_id"],
    )

    # ----- applied_slas ---------------------------------------------------
    op.create_table(
        "applied_slas",
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
            "sla_policy_id",
            sa.BigInteger(),
            sa.ForeignKey("sla_policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.BigInteger(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sla_status",
            sa.Integer(),
            nullable=False,
            server_default="0",
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
        "index_applied_slas_on_account_sla_policy_conversation",
        "applied_slas",
        ["account_id", "sla_policy_id", "conversation_id"],
    )
    op.create_index(
        "index_applied_slas_on_account_id",
        "applied_slas",
        ["account_id"],
    )
    op.create_index(
        "index_applied_slas_on_conversation_id",
        "applied_slas",
        ["conversation_id"],
    )
    op.create_index(
        "index_applied_slas_on_sla_policy_id",
        "applied_slas",
        ["sla_policy_id"],
    )


def downgrade() -> None:
    op.drop_table("applied_slas")
    op.drop_index(
        "index_sla_policies_on_account_id", table_name="sla_policies"
    )
    op.drop_table("sla_policies")
    for name in (
        "user_index",
        "index_audits_on_request_uuid",
        "index_audits_on_created_at",
        "auditable_index",
        "associated_index",
    ):
        op.drop_index(name, table_name="audits")
    op.drop_table("audits")
