"""The library of prepared answers a ``semantic`` rule matches against.

Which publications use these is decided by the rules on each post
(:mod:`app.domains.instagram.post_autoreply_models`). This module only
holds the answers themselves.

Answers are written once and **picked per publication**: a post can select
the handful of the library that apply to it, and the same answer can be
picked by as many posts as you like without being duplicated. A post that
picks nothing uses the whole library, so the feature costs no
configuration until you want the control.

The comment is embedded and matched against the library; the closest
answer is used **only** if it clears a similarity threshold, otherwise the
comment is left for a person. That threshold is the whole point. A matcher
that always answers will answer confidently and wrongly, in public, under
the brand — so "no good match" has to be a real outcome, not a fallback to
the nearest thing.

Embeddings reuse the pgvector column and ``text-embedding-3-small`` model
the Help-Center search already runs on. A second vector store would add a
service to operate and back up without adding a capability.
"""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin

# Same dimensionality as the Help-Center index — one model, one column type.
COMMENT_REPLY_EMBEDDING_DIM = 1536

# Cosine *distance* below which a prepared answer is considered a match.
# 0 is identical, 2 is opposite. 0.35 is deliberately conservative: the
# cost of staying quiet is a human answering a minute later, while the cost
# of a wrong answer is public.
DEFAULT_MATCH_MAX_DISTANCE = 0.35

AUTOREPLY_OFF = "off"
AUTOREPLY_FIXED = "fixed"
AUTOREPLY_SEMANTIC = "semantic"
AUTOREPLY_MODES = (AUTOREPLY_OFF, AUTOREPLY_FIXED, AUTOREPLY_SEMANTIC)


class InstagramCommentReply(TimestampMixin, table=True):
    """One prepared answer, matched against incoming comments by meaning.

    ``trigger`` is an example of what a person might write ("hacen envíos?"),
    not a keyword list — it is what gets embedded. Several rows can point at
    the same answer, which is how you cover different phrasings of one
    question without writing the answer twice.
    """

    __tablename__ = "instagram_comment_replies"
    __table_args__ = (
        Index(
            "index_ig_comment_replies_on_account",
            "account_id",
            "enabled",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    trigger: str = Field(sa_column=Column(Text, nullable=False))
    reply: str = Field(sa_column=Column(Text, nullable=False))
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    # Null until embedded. A row without an embedding is simply never
    # matched, so a failed embedding call degrades to "this answer is not
    # offered yet" rather than breaking the matcher.
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(COMMENT_REPLY_EMBEDDING_DIM), nullable=True),
    )


class InstagramPostReplyPick(TimestampMixin, table=True):
    """One prepared answer picked for one publication.

    A join table rather than a column on the answer, because the same
    answer is worth offering under several posts and duplicating its text
    to do that would mean editing it in several places later.

    Absence is meaningful: a post with no rows here offers the whole
    library. That way turning on similarity matching needs no picking, and
    picking is what narrows it.
    """

    __tablename__ = "instagram_post_comment_replies"
    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "comment_reply_id",
            name="index_ig_post_replies_on_post_and_reply",
        ),
        Index("index_ig_post_replies_on_reply", "comment_reply_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    post_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("instagram_posts.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    comment_reply_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("instagram_comment_replies.id", ondelete="CASCADE"),
            nullable=False,
        )
    )


__all__ = [
    "AUTOREPLY_FIXED",
    "AUTOREPLY_MODES",
    "AUTOREPLY_OFF",
    "AUTOREPLY_SEMANTIC",
    "COMMENT_REPLY_EMBEDDING_DIM",
    "DEFAULT_MATCH_MAX_DISTANCE",
    "InstagramCommentReply",
    "InstagramPostReplyPick",
]
