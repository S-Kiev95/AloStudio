"""let a prepared answer belong to one publication

The library was account-wide only, so a semantic rule on any post matched
against every answer. That is right for "hacen envíos?" and wrong for an
answer that only makes sense under one reel.

``post_id`` is nullable and defaults to null, so every existing answer
stays shared and no behaviour changes until someone scopes one. The
matcher reads scoped-to-this-post plus shared, which keeps scoping
additive — nothing has to be duplicated to be reused.

CASCADE on delete: an answer written for a publication has no meaning once
the publication is gone.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
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
