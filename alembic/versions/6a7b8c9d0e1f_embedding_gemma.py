"""embedding gemma: local-model vectors next to the OpenAI ones (F9)

Additive only. The ``vector(1536)`` columns and every existing value stay as
they are; the new columns fill in through dual writes and the backfill task,
and an account reads them only once it is switched to ``gemma``.

* ``instagram_comment_replies.embedding_gemma`` — vector(768)
* ``article_embeddings.embedding_gemma`` — vector(768), plus ``model``
  (``openai`` for the existing term rows)
* ``instagram_post_autoreplies.max_distance_gemma`` — per-rule threshold on
  the local model's scale; existing ``max_distance`` values are not
  converted.

Revision ID: 6a7b8c9d0e1f
Revises: 5f6a7b8c9d0e
Create Date: 2026-11-09 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "6a7b8c9d0e1f"
down_revision: str | None = "5f6a7b8c9d0e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "instagram_comment_replies",
        sa.Column("embedding_gemma", Vector(768), nullable=True),
    )
    op.add_column(
        "article_embeddings",
        sa.Column("embedding_gemma", Vector(768), nullable=True),
    )
    op.add_column(
        "article_embeddings",
        sa.Column("model", sa.String(), nullable=False, server_default="openai"),
    )
    op.add_column(
        "instagram_post_autoreplies",
        sa.Column("max_distance_gemma", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    # Whole-article rows written by the local model have no OpenAI vector;
    # without the ``model`` column they would read as empty term rows.
    article_embeddings = sa.table("article_embeddings", sa.column("model", sa.String()))
    op.execute(article_embeddings.delete().where(article_embeddings.c.model == "gemma"))
    op.drop_column("instagram_post_autoreplies", "max_distance_gemma")
    op.drop_column("article_embeddings", "model")
    op.drop_column("article_embeddings", "embedding_gemma")
    op.drop_column("instagram_comment_replies", "embedding_gemma")
