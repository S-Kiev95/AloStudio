"""message embeddings: meaning-based search over old conversations (F8)

One EmbeddingGemma vector per message worth searching, so "lo que hablamos
del pago en cuotas" finds "¿puedo pagarlo en 3 veces?" without sharing a
word. A table of its own, not a column on ``messages``: most messages are
never vectorised (too short to mean anything, activity rows), the biggest
table stays as it is, and switching model later is dropping rows here
rather than rewriting ``messages``.

``model`` records which model produced the vector; distances between
models are not comparable, so a vector is only ever compared with the
query embedded by the same one. HNSW with cosine distance, the measure the
thresholds were set in.

Revision ID: 1a2f8e3b4c5d
Revises: 0f8e5a1c2b3d
"""

from __future__ import annotations

from alembic import op

revision = "1a2f8e3b4c5d"
down_revision = "0f8e5a1c2b3d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE message_embeddings (
            message_id integer PRIMARY KEY
                REFERENCES messages (id) ON DELETE CASCADE,
            account_id integer NOT NULL,
            model varchar NOT NULL,
            embedding vector(768) NOT NULL,
            created_at timestamp NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_message_embeddings_account_id "
        "ON message_embeddings (account_id)"
    )
    op.execute(
        "CREATE INDEX ix_message_embeddings_embedding "
        "ON message_embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS message_embeddings")
