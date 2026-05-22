"""merge mcp_tokens + instagram heads

Revision ID: f4a5b6c7d8e9
Revises: a9b0c1d2e3f4, e3f4a5b6c7d8
Create Date: 2026-05-22 16:18:09.040458
"""
from __future__ import annotations

from collections.abc import Sequence

revision: str = 'f4a5b6c7d8e9'
down_revision: str | Sequence[str] | None = ('a9b0c1d2e3f4', 'e3f4a5b6c7d8')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
