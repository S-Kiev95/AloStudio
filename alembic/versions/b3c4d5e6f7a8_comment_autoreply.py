"""instagram comment auto-reply — per-inbox mode + prepared answers

Three pieces: the per-inbox switch on instagram_channel_settings, a library
of prepared answers embedded with the same pgvector/1536 setup the
Help-Center search uses, and an idempotency marker on the comment so a
redelivered webhook cannot answer the same person twice in public.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- per-inbox switch ---------------------------------------------------
    # Defaults to "off": upgrading must never make an account start
    # answering its audience on its own.
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

    # --- idempotency marker -------------------------------------------------
    op.add_column(
        "instagram_comments",
        sa.Column("auto_replied_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- prepared answers ---------------------------------------------------
    op.create_table(
        "instagram_comment_replies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("reply", sa.Text(), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default="true"
        ),
        # Null until embedded — an answer without an embedding is simply
        # never matched, so a failed embedding call degrades to "not offered
        # yet" rather than breaking the matcher.
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "index_ig_comment_replies_on_account",
        "instagram_comment_replies",
        ["account_id", "enabled"],
    )


def downgrade() -> None:
    op.drop_index(
        "index_ig_comment_replies_on_account",
        table_name="instagram_comment_replies",
    )
    op.drop_table("instagram_comment_replies")
    op.drop_column("instagram_comments", "auto_replied_at")
    for col in (
        "comment_autoreply_max_distance",
        "comment_autoreply_text",
        "comment_autoreply_mode",
    ):
        op.drop_column("instagram_channel_settings", col)
