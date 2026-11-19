"""google calendar: each agent's link and the events made for them (F17)

Revision ID: b1c2d3e4f5a8
Revises: a0b1c2d3e4f7
Create Date: 2026-11-18 19:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b1c2d3e4f5a8"
down_revision: str | None = "a0b1c2d3e4f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "google_calendar_links",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("google_email", sa.String(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        *_timestamps(),
    )
    op.create_table(
        "google_calendar_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "user_id", "source", "source_id", name="uniq_google_calendar_events_source"
        ),
    )


def downgrade() -> None:
    op.drop_table("google_calendar_events")
    op.drop_table("google_calendar_links")
