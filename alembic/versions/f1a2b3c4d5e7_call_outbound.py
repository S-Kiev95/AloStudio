"""calls: the customer's answer for calls we make (F7)

Revision ID: f1a2b3c4d5e7
Revises: e0f1a2b3c4d6
Create Date: 2026-11-15 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f1a2b3c4d5e7"
down_revision: str | None = "e0f1a2b3c4d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("calls", sa.Column("sdp_answer", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("calls", "sdp_answer")
