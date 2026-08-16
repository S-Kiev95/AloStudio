"""let a rule set how close a prepared answer has to be

The threshold was one number for the whole installation, and the first
value picked for it stayed silent on the paraphrases the feature exists to
catch. Which way to err is not a global fact: a post promoting one link
would rather answer a near-miss, a post about prices would rather stay
quiet.

Nullable, and null does not mean "use today's number" — it means "follow
the installation default", so the rules nobody tuned keep tracking the
tuned value instead of freezing it at write time.

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instagram_post_autoreplies",
        sa.Column("max_distance", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("instagram_post_autoreplies", "max_distance")
