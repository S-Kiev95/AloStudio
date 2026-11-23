"""billing: when a renewal charge first failed, for the grace days (F2 paso 3)

Revision ID: d9f1b3c5e7a2
Revises: c8e0a2b4d6f1
Create Date: 2026-11-23 06:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d9f1b3c5e7a2"
down_revision: str | None = "c8e0a2b4d6f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "account_subscriptions",
        sa.Column("past_due_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("account_subscriptions", "past_due_at")
