"""billing: what each plan allows, copied from the Polar product (F2 paso 3)

Revision ID: 8f4d2b6a1c3e
Revises: 7e3c9a1f5b2d
Create Date: 2026-11-16 00:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "8f4d2b6a1c3e"
down_revision: str | None = "7e3c9a1f5b2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "account_subscriptions",
        sa.Column(
            "plan_features",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("account_subscriptions", "plan_features")
