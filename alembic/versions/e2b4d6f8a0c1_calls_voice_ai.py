"""calls: the voice AI answers an inbox's calls (F7 paso 3)

Revision ID: e2b4d6f8a0c1
Revises: d9f1b3c5e7a2
Create Date: 2026-11-25 22:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e2b4d6f8a0c1"
down_revision: str | None = "d9f1b3c5e7a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "calls",
        sa.Column("ai_answered", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "call_inbox_settings",
        sa.Column("ai_mode", sa.String(16), nullable=False, server_default="off"),
    )
    op.add_column("call_inbox_settings", sa.Column("ai_greeting", sa.String(500), nullable=True))
    op.add_column("call_inbox_settings", sa.Column("ai_instructions", sa.Text(), nullable=True))
    op.add_column("call_inbox_settings", sa.Column("ai_voice", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("call_inbox_settings", "ai_voice")
    op.drop_column("call_inbox_settings", "ai_instructions")
    op.drop_column("call_inbox_settings", "ai_greeting")
    op.drop_column("call_inbox_settings", "ai_mode")
    op.drop_column("calls", "ai_answered")
