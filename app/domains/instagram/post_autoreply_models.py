"""Per-publication auto-reply rules.

Configuration lives on the post, not the account: a promotional reel and an
ordinary photo want different answers, and the common Instagram mechanic —
"comentá LINK y te lo paso" — is inherently about one specific post.

Three ways a rule can match, evaluated most-specific first:

``keyword``   the comment contains one of the rule's words. This is the
              mechanic above, and the reason a rule can answer privately:
              the point is to move the person into a DM, not to publish a
              link under the post.
``semantic``  falls through to the account's prepared-answer library
              (:mod:`app.domains.instagram.autoreply_models`), matched by
              meaning. The library is account-level on purpose — the same
              answers about shipping or prices apply across every post.
``all``       answers anything left. A catch-all, so it sorts last.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin

MATCH_KEYWORD = "keyword"
MATCH_SEMANTIC = "semantic"
MATCH_ALL = "all"
MATCH_TYPES = (MATCH_KEYWORD, MATCH_SEMANTIC, MATCH_ALL)

# Most specific first. A keyword rule must beat the catch-all on the same
# post, otherwise the catch-all would swallow every comment and the
# keyword mechanic would never fire.
MATCH_PRIORITY = {MATCH_KEYWORD: 0, MATCH_SEMANTIC: 1, MATCH_ALL: 2}

DELIVERY_PUBLIC = "public"
DELIVERY_DM = "dm"
DELIVERIES = (DELIVERY_PUBLIC, DELIVERY_DM)

# How close a prepared answer has to be, per rule. Named levels rather than
# a free number: the underlying value is a cosine distance, which is not
# something anyone running a shop can reason about, while "only if it is
# nearly the same question" is. The numbers come from the measurements in
# :mod:`app.domains.instagram.autoreply_models`.
STRICTNESS_LEVELS: dict[str, float] = {
    # Near-verbatim only. A paraphrase already sits past this.
    "strict": 0.45,
    # Paraphrases of the same question, not a different one. The default.
    "balanced": 0.55,
    # Reaches into where genuinely different questions start, so it will
    # sometimes answer the wrong one. Offered because on some posts a
    # near-miss answer beats no answer.
    "loose": 0.65,
}
DEFAULT_STRICTNESS = "balanced"

# Hand-set values are still accepted, bounded so a stray number cannot turn
# the matcher into "always answer the nearest thing".
MIN_MATCH_DISTANCE = 0.05
MAX_MATCH_DISTANCE = 1.0


class InstagramPostAutoreply(TimestampMixin, table=True):
    """One auto-reply rule on one publication."""

    __tablename__ = "instagram_post_autoreplies"
    __table_args__ = (
        Index(
            "index_ig_post_autoreplies_on_post",
            "post_id",
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
    post_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("instagram_posts.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    match_type: str = Field(
        default=MATCH_KEYWORD,
        sa_column=Column(String, nullable=False, server_default=MATCH_KEYWORD),
    )
    # Comma-separated for ``keyword``. Matching is case- and
    # accent-insensitive on the reading side: someone typing "INFO" or
    # "linké" should still trigger a rule written as "info".
    keywords: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    # Unused by ``semantic`` rules, which take their text from the matched
    # library entry.
    reply_text: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    delivery: str = Field(
        default=DELIVERY_PUBLIC,
        sa_column=Column(String, nullable=False, server_default=DELIVERY_PUBLIC),
    )
    # How close a prepared answer has to be for a ``semantic`` rule to use
    # it. Null follows the installation default, so a rule written before
    # this existed — or by someone who does not want to think about it —
    # keeps tracking the tuned value instead of freezing today's number.
    max_distance: float | None = Field(
        default=None, sa_column=Column(Float, nullable=True)
    )
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )


__all__ = [
    "DEFAULT_STRICTNESS",
    "DELIVERIES",
    "DELIVERY_DM",
    "DELIVERY_PUBLIC",
    "MATCH_ALL",
    "MATCH_KEYWORD",
    "MATCH_PRIORITY",
    "MATCH_SEMANTIC",
    "MATCH_TYPES",
    "MAX_MATCH_DISTANCE",
    "MIN_MATCH_DISTANCE",
    "STRICTNESS_LEVELS",
    "InstagramPostAutoreply",
]
