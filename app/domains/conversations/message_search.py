"""Search inside old conversations — by message, not by conversation (F8).

``GET /conversations/search`` answers "which conversations mention this",
with ``ILIKE`` over every message. That finds the conversation and leaves
you scrolling a year of it for the line. This answers per *message*: the
fragment with the words highlighted, its date and contact, and enough to
open the conversation right there (``around`` on the messages endpoint).

Matching, over the normalised text the migration ``0f8e5a1c2b3d`` indexes
(lower-cased, accents removed — so "envio" finds "Envío"):

* **words** — Spanish full text: "cuota" finds "cuotas", and the query
  accepts quotes and ``-palabra`` like a web search box;
* **fragments** — "cuot" anywhere in the text;
* **typos** — trigram word similarity, for queries of four letters or
  more ("cuotsa"). Shorter ones match too much to be useful.

Ranked by full-text relevance, then by similarity, then newest first.

Always scoped to the account and, for agents, to the inboxes they belong
to — the same rule as the conversation list, through
:func:`apply_permission_scope`. Activity rows are excluded, as in the
existing search; private notes are included, because they are exactly the
kind of thing an agent wants to find again.
"""

from __future__ import annotations

import logging
import unicodedata
from datetime import datetime
from typing import Any

from sqlalchemy import Float, cast, func, literal, literal_column, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.embeddings import (
    MODEL_GEMMA,
    TASK_QUERY,
    EmbeddingServiceError,
    embed_gemma_one,
    gemma_enabled,
)
from app.domains.contacts.models import Contact
from app.domains.conversations.message_embeddings import MessageEmbedding
from app.domains.conversations.models import (
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
    message_type_to_str,
)
from app.domains.conversations.permission import apply_permission_scope
from app.domains.inboxes.models import Inbox

log = logging.getLogger(__name__)

PER_PAGE = 20
MAX_QUERY = 200
TYPO_MIN_LENGTH = 4
# pg_trgm's default word-similarity threshold is 0.6, which misses the most
# common typo there is — two letters swapped: "cuotsa" scores 0.57 against
# "cuotas", "presupeusto" 0.50 against "presupuesto" (measured). Lowered for
# this query only, inside its transaction.
TYPO_THRESHOLD = "0.5"
SNIPPET_BEFORE = 60
# Candidates taken from each side before fusing. Pages are cut from the
# fused list, so deep pages end where the candidates do — enough to find a
# conversation, which is what this is for.
CANDIDATES = 100
# Meaning (F8, step 2). Cosine distance with EmbeddingGemma, measured on
# Spanish customer messages: what answers the query sits at 0.15-0.28.
MEANING_MAX_DISTANCE = 0.25
MEANING_MIN_LENGTH = 4
MEANING_WEIGHT = 0.8
RRF_K = 60
SNIPPET_LENGTH = 220

_SPANISH = literal_column("'spanish'::regconfig")


def _norm_sql(expr: Any) -> Any:
    """The indexed normalisation. Must stay byte-identical to the index
    expression, or Postgres will not use the index."""
    return func.alo_search_text(expr)


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search_messages(
    session: AsyncSession,
    *,
    account_id: int,
    current_user_id: int | None,
    q: str,
    conversation_display_id: int | None = None,
    page: int = 1,
    per_page: int = PER_PAGE,
) -> dict[str, Any]:
    q = q.strip()[:MAX_QUERY]
    page = max(page, 1)
    if not q:
        return {"payload": [], "meta": {"page": page, "has_more": False}}

    async def scoped(*columns: Any) -> Any:
        stmt = (
            select(*columns)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Message.account_id == account_id,
                Conversation.account_id == account_id,
                Message.message_type.in_(  # type: ignore[attr-defined]
                    [MESSAGE_TYPE_INCOMING, MESSAGE_TYPE_OUTGOING]
                ),
                Message.content.is_not(None),  # type: ignore[union-attr]
            )
        )
        if conversation_display_id is not None:
            stmt = stmt.where(Conversation.display_id == conversation_display_id)
        if current_user_id is not None:
            # ``None`` is the MCP case: a token acts for the account, the
            # same way ``list_messages`` reads any conversation in it.
            stmt = await apply_permission_scope(
                stmt,
                session=session,
                account_id=account_id,
                current_user_id=current_user_id,
            )
        return stmt

    text_ids = await _text_candidates(session, await scoped(Message.id), q)
    meaning_ids = await _meaning_candidates(
        session, await scoped(Message.id), q, account_id
    )
    fused = fuse(text_ids, meaning_ids)

    offset = (page - 1) * per_page
    window = fused[offset : offset + per_page]
    has_more = len(fused) > offset + per_page
    rows = await _details(session, [message_id for message_id, _ in window])
    terms = _terms(q)

    payload = []
    for message_id, match in window:
        row = rows.get(message_id)
        if row is None:
            continue
        text, created_at, message_type, private, display_id, contact, inbox = row
        snippet, highlights = make_snippet(text or "", terms)
        payload.append(
            {
                "message_id": message_id,
                "conversation_id": display_id,
                "created_at": _unix(created_at),
                "message_type": message_type_to_str(message_type),
                "private": bool(private),
                "snippet": snippet,
                "highlights": highlights,
                # "text": the words are there. "meaning": found by what it is
                # about, with no word in common — the UI calls it related.
                # "both": the two agree, which puts it first.
                "match": match,
                "contact": contact,
                "inbox": inbox,
            }
        )
    return {"payload": payload, "meta": {"page": page, "has_more": has_more}}


async def _text_candidates(session: AsyncSession, stmt: Any, q: str) -> list[int]:
    content = _norm_sql(Message.content)
    q_norm = _norm_sql(literal(q))
    tsvector = func.to_tsvector(_SPANISH, content)
    tsquery = func.websearch_to_tsquery(_SPANISH, q_norm)
    matches = [
        tsvector.op("@@")(tsquery),
        content.like(func.concat("%", _norm_sql(literal(_escape_like(q))), "%")),
    ]
    if len(q) >= TYPO_MIN_LENGTH:
        matches.append(content.op("%>")(q_norm))
        await session.exec(
            select(
                func.set_config(
                    "pg_trgm.word_similarity_threshold", TYPO_THRESHOLD, True
                )
            )
        )
    stmt = (
        stmt.where(or_(*matches))
        .order_by(
            func.ts_rank(tsvector, tsquery).desc(),
            cast(func.word_similarity(q_norm, content), Float).desc(),
            Message.created_at.desc(),  # type: ignore[attr-defined]
        )
        .limit(CANDIDATES)
    )
    return list((await session.exec(stmt)).all())


async def _meaning_candidates(
    session: AsyncSession, stmt: Any, q: str, account_id: int
) -> list[int]:
    """Messages about the same thing, nearest first — or nothing.

    Nothing when the local model is not configured, when the query is too
    short to carry a topic, or when the service does not answer: the text
    results stand on their own, and a search must never fail because the
    embedding service is restarting.
    """
    if len(q) < MEANING_MIN_LENGTH or not gemma_enabled():
        return []
    try:
        vector = await embed_gemma_one(q, task=TASK_QUERY)
    except EmbeddingServiceError as exc:
        log.warning("search.meaning.unavailable err=%s", exc)
        return []
    distance = MessageEmbedding.embedding.cosine_distance(vector)  # type: ignore[attr-defined]
    # HNSW looks at ``ef_search`` neighbours and *then* applies the WHERE.
    # With the account, inbox and permission filters on top, the default 40
    # would routinely come back with a handful; the iterative scan keeps
    # walking the graph until the filtered LIMIT is met (pgvector 0.8).
    for name, value in (
        ("hnsw.ef_search", "200"),
        ("hnsw.iterative_scan", "relaxed_order"),
    ):
        await session.exec(select(func.set_config(name, value, True)))
    stmt = (
        stmt.join(MessageEmbedding, MessageEmbedding.message_id == Message.id)
        .where(
            MessageEmbedding.account_id == account_id,
            MessageEmbedding.model == MODEL_GEMMA,
            distance <= MEANING_MAX_DISTANCE,
        )
        .order_by(distance)
        .limit(CANDIDATES)
    )
    return list((await session.exec(stmt)).all())


def fuse(text_ids: list[int], meaning_ids: list[int]) -> list[tuple[int, str]]:
    """Reciprocal rank fusion of the two lists, text weighted above meaning.

    Distance alone could not separate a related message from a neighbouring
    topic (measured: relevant 0.15-0.28, noise from 0.22), so meaning never
    ranks on its own score: it adds to the text rank, and a message both
    lists agree on rises to the top. Text weighs more because a message
    that has the words is the surer answer.
    """
    scores: dict[int, float] = {}
    found: dict[int, set[str]] = {}
    lists = ((1.0, "text", text_ids), (MEANING_WEIGHT, "meaning", meaning_ids))
    for weight, kind, ids in lists:
        for rank, message_id in enumerate(ids):
            scores[message_id] = scores.get(message_id, 0.0) + weight / (
                RRF_K + rank + 1
            )
            found.setdefault(message_id, set()).add(kind)
    ordered = sorted(scores, key=lambda m: scores[m], reverse=True)
    return [
        (m, "both" if len(found[m]) == 2 else next(iter(found[m]))) for m in ordered
    ]


async def _details(session: AsyncSession, ids: list[int]) -> dict[int, tuple]:
    if not ids:
        return {}
    stmt = (
        select(
            Message.id,
            Message.content,
            Message.created_at,
            Message.message_type,
            Message.private,
            Conversation.display_id,
            Contact.id,
            Contact.name,
            Inbox.id,
            Inbox.name,
        )
        .join(Conversation, Conversation.id == Message.conversation_id)
        .join(Inbox, Inbox.id == Conversation.inbox_id)
        .outerjoin(Contact, Contact.id == Conversation.contact_id)
        .where(Message.id.in_(ids))  # type: ignore[union-attr]
    )
    out: dict[int, tuple] = {}
    for row in (await session.exec(stmt)).all():
        mid, text, created, mtype, private, display_id, cid, cname, iid, iname = row
        out[mid] = (
            text,
            created,
            mtype,
            private,
            display_id,
            {"id": cid, "name": cname},
            {"id": iid, "name": iname},
        )
    return out


# ---------------------------------------------------------------------------
# Snippets
# ---------------------------------------------------------------------------
def _fold(char: str) -> str:
    """One character, lower-cased with its accents removed — the same
    normalisation as ``alo_search_text``, done in Python so the offsets
    can be mapped back onto the original text."""
    decomposed = unicodedata.normalize("NFD", char.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _terms(q: str) -> list[str]:
    """What to highlight: the query's words, folded, without the operators
    a web-style query allows (quotes, a leading ``-``, ``or``)."""
    out: list[str] = []
    for raw in q.replace('"', " ").split():
        if raw.startswith("-") or raw.lower() == "or":
            continue
        word = "".join(_fold(c) for c in raw)
        if len(word) >= 2 and word not in out:
            out.append(word)
    return out


def make_snippet(text: str, terms: list[str]) -> tuple[str, list[list[int]]]:
    """A window of ``text`` around the first match, with the matched spans.

    Highlights are ``[start, end)`` offsets into the returned snippet, in
    the *original* characters — accents and capitals intact — so the
    client can wrap them without re-running any matching of its own.
    Stemmed and typo matches are not highlighted; the snippet then opens
    at the start of the message.
    """
    folded_chars: list[str] = []
    origin: list[int] = []
    for i, char in enumerate(text):
        for piece in _fold(char):
            folded_chars.append(piece)
            origin.append(i)
    folded = "".join(folded_chars)

    spans: list[tuple[int, int]] = []
    for term in terms:
        start = folded.find(term)
        while start != -1:
            end = start + len(term)
            spans.append((origin[start], origin[end - 1] + 1))
            start = folded.find(term, end)
    spans.sort()

    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    first = merged[0][0] if merged else 0
    window_start = max(0, first - SNIPPET_BEFORE)
    if window_start > 0:
        space = text.find(" ", window_start)
        if 0 <= space < first:
            window_start = space + 1
    window_end = min(len(text), window_start + SNIPPET_LENGTH)

    prefix = "…" if window_start > 0 else ""
    suffix = "…" if window_end < len(text) else ""
    snippet = prefix + text[window_start:window_end] + suffix
    shift = len(prefix) - window_start
    highlights = [
        [start + shift, min(end, window_end) + shift]
        for start, end in merged
        if start < window_end and end > window_start
    ]
    return snippet, highlights


def _unix(dt: datetime | None) -> int | None:
    return int(dt.timestamp()) if dt is not None else None


__all__ = ["PER_PAGE", "make_snippet", "search_messages"]
