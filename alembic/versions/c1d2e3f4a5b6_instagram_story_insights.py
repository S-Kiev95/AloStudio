"""ig: story_insights column on instagram_posts

Adds a nullable ``insights`` JSONB column to ``instagram_posts`` so the
I.8 webhook receiver can stamp ``story_insights`` metrics
(impressions / reach / taps / exits / replies) onto the matching
published STORIES post when Meta fires the field on story expiry.

Plan: ``PLAN.instagram-graph.md`` (I.8 milestone).

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-05-20 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b0c1d2e3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "instagram_posts",
        sa.Column("insights", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("instagram_posts", "insights")
