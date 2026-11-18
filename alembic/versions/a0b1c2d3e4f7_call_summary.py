"""calls: AI summary of each transcribed call (F17)

Revision ID: a0b1c2d3e4f7
Revises: f9a0b1c2d3e6
Create Date: 2026-11-18 17:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a0b1c2d3e4f7"
down_revision: str | None = "f9a0b1c2d3e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("calls", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "calls",
        sa.Column("summary_attempts", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("calls", "summary_attempts")
    op.drop_column("calls", "summary")
