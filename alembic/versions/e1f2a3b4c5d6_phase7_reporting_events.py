"""phase7: reporting_events

Adds the ``reporting_events`` table backing
:class:`app.domains.reporting.models.ReportingEvent`.

Mirrors ``reference/chatwoot/db/schema.rb`` (``reporting_events``,
v4.13.0).

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-05-12 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reporting_events",
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
            nullable=True,
        ),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "inbox_id",
            sa.Integer(),
            sa.ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column(
            "value_in_business_hours", sa.Float(), nullable=True
        ),
        sa.Column(
            "event_start_time",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "event_end_time",
            sa.DateTime(timezone=True),
            nullable=True,
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
        "index_reporting_events_on_account_id",
        "reporting_events",
        ["account_id"],
    )
    op.create_index(
        "index_reporting_events_on_conversation_id",
        "reporting_events",
        ["conversation_id"],
    )
    op.create_index(
        "index_reporting_events_on_inbox_id",
        "reporting_events",
        ["inbox_id"],
    )
    op.create_index(
        "index_reporting_events_on_user_id",
        "reporting_events",
        ["user_id"],
    )
    op.create_index(
        "index_reporting_events_on_name",
        "reporting_events",
        ["name"],
    )
    op.create_index(
        "index_reporting_events_on_created_at",
        "reporting_events",
        ["created_at"],
    )
    op.create_index(
        "index_reporting_events_for_response_distribution",
        "reporting_events",
        ["account_id", "name", "inbox_id", "created_at"],
    )
    op.create_index(
        "reporting_events__account_id__name__created_at",
        "reporting_events",
        ["account_id", "name", "created_at"],
    )


def downgrade() -> None:
    for name in (
        "reporting_events__account_id__name__created_at",
        "index_reporting_events_for_response_distribution",
        "index_reporting_events_on_created_at",
        "index_reporting_events_on_name",
        "index_reporting_events_on_user_id",
        "index_reporting_events_on_inbox_id",
        "index_reporting_events_on_conversation_id",
        "index_reporting_events_on_account_id",
    ):
        op.drop_index(name, table_name="reporting_events")
    op.drop_table("reporting_events")
