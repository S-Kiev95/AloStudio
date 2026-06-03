"""v2.9: webhook_dead_letters

Quarantine table for webhook + agent-bot deliveries that exhausted
their retry budget. Per-receiver row so an operator can see which
URLs are misbehaving without parsing the application log.

Columns:
  * ``receiver_kind`` — ``webhook`` (account-configured) or
    ``agent_bot`` (bot relay). Enum-as-string for forward-compat —
    new receiver types can land without a migration.
  * ``receiver_id`` — FK-shaped int referencing webhooks.id /
    agent_bots.id, but NOT a real FK (the receiver may have been
    deleted; we want the dead-letter row to outlive it for forensic
    visibility). Nullable for the same reason.
  * ``event_id`` — copy of the per-delivery UUID we put on the body
    so an operator can correlate a dead-letter row with the receiver
    log on their side.
  * ``body`` — the JSON payload we tried to deliver, intact. Lets an
    operator replay manually after fixing the receiver.
  * ``last_status_code`` / ``last_error`` — final attempt summary.
  * ``attempts`` — how many tries it took to give up (4 today; the
    constant can change without breaking forensic reads).

Indexes: ``(account_id, created_at DESC)`` so the dashboard's
"recent failures" view is fast.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-06-04 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webhook_dead_letters",
        sa.Column(
            "id",
            sa.Integer(),
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
        sa.Column("receiver_kind", sa.String(length=32), nullable=False),
        sa.Column("receiver_id", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=True),
        sa.Column(
            "body",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_attempted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_webhook_dead_letters_account_created",
        "webhook_dead_letters",
        ["account_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_webhook_dead_letters_receiver",
        "webhook_dead_letters",
        ["receiver_kind", "receiver_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_webhook_dead_letters_receiver",
        table_name="webhook_dead_letters",
    )
    op.drop_index(
        "ix_webhook_dead_letters_account_created",
        table_name="webhook_dead_letters",
    )
    op.drop_table("webhook_dead_letters")
