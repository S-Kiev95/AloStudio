"""ig: instagram publishing + moderation tables

Adds three tables on top of the Phase 5e ``channel_instagram`` row:

  * instagram_posts            — one row per dashboard publish request
  * instagram_post_containers  — one Meta container per ``POST /media``
  * instagram_comments         — local mirror of comments on owned media

Plan: ``PLAN.instagram-graph.md`` (I.1 milestone). Verified spec
references included in the model docstrings.

Revision ID: b0c1d2e3f4a5
Revises: f8a9b0c1d2e3
Create Date: 2026-05-18 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b0c1d2e3f4a5"
down_revision: str | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----- instagram_posts -------------------------------------------------
    op.create_table(
        "instagram_posts",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inbox_id",
            sa.BigInteger(),
            sa.ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_instagram_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "channel_instagram.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "state",
            sa.String(),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("media_type", sa.String(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column(
            "source",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("ig_media_id", sa.String(), nullable=True),
        sa.Column("ig_permalink", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "scheduled_for",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "index_instagram_posts_on_account_id",
        "instagram_posts",
        ["account_id"],
    )
    op.create_index(
        "index_instagram_posts_on_channel_instagram_id",
        "instagram_posts",
        ["channel_instagram_id"],
    )
    op.create_index(
        "index_instagram_posts_on_state",
        "instagram_posts",
        ["state"],
    )
    op.create_index(
        "index_instagram_posts_on_scheduled_for",
        "instagram_posts",
        ["scheduled_for"],
    )

    # ----- instagram_post_containers --------------------------------------
    op.create_table(
        "instagram_post_containers",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "post_id",
            sa.BigInteger(),
            sa.ForeignKey("instagram_posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ig_container_id", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "status_code",
            sa.String(),
            nullable=False,
            server_default="IN_PROGRESS",
        ),
        sa.Column(
            "poll_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "index_instagram_post_containers_on_post_id",
        "instagram_post_containers",
        ["post_id"],
    )
    op.create_index(
        "index_instagram_post_containers_on_status_code",
        "instagram_post_containers",
        ["status_code"],
    )
    op.create_unique_constraint(
        "index_instagram_post_containers_post_position",
        "instagram_post_containers",
        ["post_id", "position"],
    )

    # ----- instagram_comments ---------------------------------------------
    op.create_table(
        "instagram_comments",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.BigInteger(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_instagram_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "channel_instagram.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("ig_comment_id", sa.String(), nullable=False),
        sa.Column("ig_media_id", sa.String(), nullable=False),
        sa.Column("parent_comment_id", sa.String(), nullable=True),
        sa.Column("from_username", sa.String(), nullable=True),
        sa.Column("from_id", sa.String(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column(
            "hidden",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "conversation_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "conversations.id", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        sa.Column(
            "ig_created_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint(
        "index_instagram_comments_on_ig_comment_id",
        "instagram_comments",
        ["ig_comment_id"],
    )
    op.create_index(
        "index_instagram_comments_on_channel_instagram_id",
        "instagram_comments",
        ["channel_instagram_id"],
    )
    op.create_index(
        "index_instagram_comments_on_ig_media_id",
        "instagram_comments",
        ["ig_media_id"],
    )
    op.create_index(
        "index_instagram_comments_on_parent_comment_id",
        "instagram_comments",
        ["parent_comment_id"],
    )
    op.create_index(
        "index_instagram_comments_on_conversation_id",
        "instagram_comments",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_table("instagram_comments")
    op.drop_table("instagram_post_containers")
    op.drop_table("instagram_posts")
