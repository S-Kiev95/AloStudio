"""billing: when the admins were told about the plan's AI cap (F2 paso 3)

Revision ID: c8e0a2b4d6f1
Revises: a6b8d0f2c4e1
Create Date: 2026-11-23 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8e0a2b4d6f1"
down_revision: str | None = "a6b8d0f2c4e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "account_subscriptions",
        sa.Column("cap_notified_month", sa.String(length=7), nullable=True),
    )
    op.add_column(
        "account_subscriptions",
        sa.Column("cap_notified_level", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("account_subscriptions", "cap_notified_level")
    op.drop_column("account_subscriptions", "cap_notified_month")
