"""move comment auto-reply from the account to the publication

The per-channel switch shipped in b3c4d5e6f7a8 was at the wrong level: a
promotional reel and an ordinary photo want different answers, and the
"comentá X y te lo paso" mechanic is inherently about one post. Rules now
hang off the publication, and can answer publicly or by DM.

The three per-channel columns are dropped rather than left behind: nothing
had them configured (every channel was "off" with no text), and leaving a
second, dead way to configure the same feature is worse than removing it.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instagram_post_autoreplies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "match_type", sa.String(), nullable=False, server_default="keyword"
        ),
        sa.Column("keywords", sa.Text(), nullable=True),
        sa.Column("reply_text", sa.Text(), nullable=True),
        sa.Column(
            "delivery", sa.String(), nullable=False, server_default="public"
        ),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["post_id"], ["instagram_posts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "index_ig_post_autoreplies_on_post",
        "instagram_post_autoreplies",
        ["post_id", "enabled"],
    )

    for col in (
        "comment_autoreply_max_distance",
        "comment_autoreply_text",
        "comment_autoreply_mode",
    ):
        op.drop_column("instagram_channel_settings", col)


def downgrade() -> None:
    op.add_column(
        "instagram_channel_settings",
        sa.Column(
            "comment_autoreply_mode",
            sa.String(),
            nullable=False,
            server_default="off",
        ),
    )
    op.add_column(
        "instagram_channel_settings",
        sa.Column("comment_autoreply_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "instagram_channel_settings",
        sa.Column(
            "comment_autoreply_max_distance",
            sa.Float(),
            nullable=False,
            server_default="0.35",
        ),
    )
    op.drop_index(
        "index_ig_post_autoreplies_on_post",
        table_name="instagram_post_autoreplies",
    )
    op.drop_table("instagram_post_autoreplies")
