"""Vectors for meaning-based message search (F8, step 2).

One EmbeddingGemma vector per message worth searching, written in batches
by a worker task rather than when the message arrives: a message must never
wait on the embedding service, and the same loop that keeps new messages
current is the backfill for the old ones. Full-text search covers a new
message instantly; meaning catches up within a few minutes.

Only the local model, never OpenAI: vectorising every message is a cost per
message that F6 has not measured yet, and the local one is free and won its
comparison in F9.

Not every message is worth a vector. "ok", "gracias", "👍" carry no topic
and would only crowd the neighbours of every query, so messages shorter
than :data:`MIN_LENGTH` are skipped — and filtered in the query, so they
are never picked up again.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, func
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.embeddings import GEMMA_DIM, MODEL_GEMMA, TASK_DOCUMENT, embed_gemma
from app.domains.conversations.models import (
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Message,
)

log = logging.getLogger(__name__)

MIN_LENGTH = 12
MAX_CHARS = 2000  # a long email still has its topic near the top
BATCH = 64


class MessageEmbedding(SQLModel, table=True):
    __tablename__ = "message_embeddings"

    message_id: int = Field(primary_key=True)
    account_id: int = Field(index=True)
    model: str
    embedding: list[float] = Field(
        sa_column=Column(Vector(GEMMA_DIM), nullable=False)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None)
    )


def eligible(stmt):  # type: ignore[no-untyped-def]
    """The messages worth a vector — shared by the writer and the tests."""
    return stmt.where(
        Message.message_type.in_(  # type: ignore[attr-defined]
            [MESSAGE_TYPE_INCOMING, MESSAGE_TYPE_OUTGOING]
        ),
        func.length(func.trim(Message.content)) >= MIN_LENGTH,
    )


async def embed_pending(
    session: AsyncSession, *, batch: int = BATCH, account_id: int | None = None
) -> int:
    """Vectorise one batch of messages that have none. Returns how many.

    Newest first: recent conversations are the ones people search, so a
    fresh install becomes useful long before the backfill reaches 2023.
    """
    stmt = eligible(
        select(Message.id, Message.account_id, Message.content)
        .outerjoin(MessageEmbedding, MessageEmbedding.message_id == Message.id)
        .where(MessageEmbedding.message_id.is_(None))  # type: ignore[union-attr]
    )
    if account_id is not None:
        stmt = stmt.where(Message.account_id == account_id)
    rows = list(
        (await session.exec(stmt.order_by(Message.id.desc()).limit(batch))).all()  # type: ignore[union-attr]
    )
    if not rows:
        return 0

    vectors = await embed_gemma(
        [(content or "")[:MAX_CHARS] for _, _, content in rows],
        task=TASK_DOCUMENT,
    )
    await session.exec(
        insert(MessageEmbedding)
        .values(
            [
                {
                    "message_id": message_id,
                    "account_id": acct,
                    "model": MODEL_GEMMA,
                    "embedding": vector,
                }
                for (message_id, acct, _), vector in zip(rows, vectors, strict=True)
            ]
        )
        # A message deleted or embedded meanwhile by another run is fine.
        .on_conflict_do_nothing(index_elements=["message_id"])
    )
    await session.commit()
    return len(rows)


async def embed_until(
    session: AsyncSession, *, seconds: float, account_id: int | None = None
) -> int:
    """Batches until nothing is left or ``seconds`` have gone by — so one
    run of the cron never outlives its slot, and the backfill simply
    continues on the next one."""
    deadline = time.monotonic() + seconds
    total = 0
    while time.monotonic() < deadline:
        done = await embed_pending(session, account_id=account_id)
        total += done
        if done == 0:
            break
    return total


__all__ = [
    "MIN_LENGTH",
    "MessageEmbedding",
    "eligible",
    "embed_pending",
    "embed_until",
]
