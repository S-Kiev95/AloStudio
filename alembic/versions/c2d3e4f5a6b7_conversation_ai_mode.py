"""v2.8: conversations.ai_mode + conversations.ai_assignee

Two new columns on ``conversations`` so an external AI agent (Alicia
et al.) can flag the conversation as under its control, and our own
automation rule listener can skip the conversation while the flag is
on. Optional ``ai_assignee`` string identifies which AI is on duty
(``"alicia-v3"`` etc.) — purely informational, the UI uses it for the
"🤖 IA activa" badge.

Defaults match the no-AI baseline: ``ai_mode=false`` + ``ai_assignee
NULL`` so the migration is a no-op for existing rows.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-03 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "ai_mode",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "conversations",
        sa.Column("ai_assignee", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "ai_assignee")
    op.drop_column("conversations", "ai_mode")
