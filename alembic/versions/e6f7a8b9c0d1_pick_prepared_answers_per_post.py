"""pick prepared answers per publication

d5e6f7a8b9c0 gave an answer a single ``post_id``, which turned out to be
the wrong relation: with a library of a hundred, a post wants to offer the
ten that apply, and the same answer is worth offering under several posts.
Owning it from one post cannot express either without duplicating the text
— and duplicated text has to be edited in every copy later.

Replaced by a join table. Any answer that had a ``post_id`` becomes a pick
for that post, so nothing configured under the old shape is lost, and the
column goes rather than leaving a second, dead way to say the same thing.

A post with no picks offers the whole library: absence means "everything",
so similarity matching still needs no configuration to work.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instagram_post_comment_replies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("comment_reply_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["post_id"], ["instagram_posts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["comment_reply_id"],
            ["instagram_comment_replies.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "post_id",
            "comment_reply_id",
            name="index_ig_post_replies_on_post_and_reply",
        ),
    )
    op.create_index(
        "index_ig_post_replies_on_reply",
        "instagram_post_comment_replies",
        ["comment_reply_id"],
    )

    # Carry the old single-post ownership over as a pick.
    op.execute(
        """
        INSERT INTO instagram_post_comment_replies
            (created_at, updated_at, post_id, comment_reply_id)
        SELECT now(), now(), post_id, id
        FROM instagram_comment_replies
        WHERE post_id IS NOT NULL
        """
    )

    op.drop_index(
        "index_ig_comment_replies_on_post",
        table_name="instagram_comment_replies",
    )
    op.drop_constraint(
        "instagram_comment_replies_post_id_fkey",
        "instagram_comment_replies",
        type_="foreignkey",
    )
    op.drop_column("instagram_comment_replies", "post_id")


def downgrade() -> None:
    op.add_column(
        "instagram_comment_replies",
        sa.Column("post_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "instagram_comment_replies_post_id_fkey",
        "instagram_comment_replies",
        "instagram_posts",
        ["post_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "index_ig_comment_replies_on_post",
        "instagram_comment_replies",
        ["post_id"],
    )
    # Lossy on purpose: a column holds one post, so an answer picked by
    # several keeps only the first.
    op.execute(
        """
        UPDATE instagram_comment_replies r
        SET post_id = p.post_id
        FROM (
            SELECT comment_reply_id, MIN(post_id) AS post_id
            FROM instagram_post_comment_replies
            GROUP BY comment_reply_id
        ) p
        WHERE p.comment_reply_id = r.id
        """
    )
    op.drop_index(
        "index_ig_post_replies_on_reply",
        table_name="instagram_post_comment_replies",
    )
    op.drop_table("instagram_post_comment_replies")
