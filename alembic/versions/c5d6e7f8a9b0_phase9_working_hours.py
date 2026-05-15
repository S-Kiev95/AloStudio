"""phase9: working_hours

Adds the ``working_hours`` table backing
:class:`app.domains.working_hours.models.WorkingHour`.

Mirrors ``reference/chatwoot/db/schema.rb`` (v4.13.0).

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-05-14 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: str | None = "b4c5d6e7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "working_hours",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "inbox_id",
            sa.BigInteger(),
            sa.ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column(
            "closed_all_day",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "open_all_day",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("open_hour", sa.Integer(), nullable=True),
        sa.Column("open_minutes", sa.Integer(), nullable=True),
        sa.Column("close_hour", sa.Integer(), nullable=True),
        sa.Column("close_minutes", sa.Integer(), nullable=True),
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
        "index_working_hours_on_account_id",
        "working_hours",
        ["account_id"],
    )
    op.create_index(
        "index_working_hours_on_inbox_id",
        "working_hours",
        ["inbox_id"],
    )


def downgrade() -> None:
    op.drop_index("index_working_hours_on_inbox_id", table_name="working_hours")
    op.drop_index("index_working_hours_on_account_id", table_name="working_hours")
    op.drop_table("working_hours")
