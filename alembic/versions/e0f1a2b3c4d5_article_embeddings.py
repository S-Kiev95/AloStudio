"""article_embeddings

Adds the ``article_embeddings`` table backing :class:`ArticleEmbedding`
for Help-Center semantic search, plus the ``vector`` extension.

Mirrors ``enterprise/app/models/article_embedding.rb`` (``vector(1536)``).
Chatwoot indexes with ``ivfflat``; we use ``hnsw`` instead — it needs no
training pass, so it stays correct when built on an empty table and as
rows trickle in on article saves (an empty ivfflat index silently tanks
recall). Same ``vector_cosine_ops`` distance.

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-07-07 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e0f1a2b3c4d5"
down_revision: str | None = "d9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "article_embeddings",
        sa.Column(
            "id", sa.BigInteger(), primary_key=True, autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "article_id",
            sa.BigInteger(),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("term", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
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
        "index_article_embeddings_on_article_id",
        "article_embeddings",
        ["article_id"],
    )
    op.execute(
        "CREATE INDEX index_article_embeddings_on_embedding "
        "ON article_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("article_embeddings")
    # Leave the ``vector`` extension in place — other objects may use it.
