"""calls: tell the customer we call back after a call nobody answered (F7)

Revision ID: c6d7e8f9a0b3
Revises: b4c5d6e7f8a1
Create Date: 2026-11-16 23:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c6d7e8f9a0b3"
down_revision: str | None = "b4c5d6e7f8a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "call_inbox_settings",
        sa.Column("missed_call_reply", sa.Boolean(), server_default="true", nullable=False),
    )
    op.add_column(
        "call_inbox_settings", sa.Column("missed_call_text", sa.String(1024), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("call_inbox_settings", "missed_call_text")
    op.drop_column("call_inbox_settings", "missed_call_reply")
