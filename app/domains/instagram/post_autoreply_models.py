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
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )


__all__ = [
    "DELIVERIES",
    "DELIVERY_DM",
    "DELIVERY_PUBLIC",
    "MATCH_ALL",
    "MATCH_KEYWORD",
    "MATCH_PRIORITY",
    "MATCH_SEMANTIC",
    "MATCH_TYPES",
    "InstagramPostAutoreply",
]
