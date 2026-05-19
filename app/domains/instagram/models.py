"""Instagram publishing + moderation models.

Three tables that extend the Phase 5e ``channel_instagram`` row with:

  * :class:`InstagramPost`            — one row per dashboard-initiated
    publish request. State machine flips from ``pending`` → ``publishing``
    → ``published`` / ``failed`` via the ARQ worker.
  * :class:`InstagramPostContainer`   — one row per Meta-side container
    (``POST /{ig-user}/media`` returns one). A single image gets one
    container; a carousel gets N children + 1 parent. We poll each.
  * :class:`InstagramComment`         — local mirror of comments on
    owned media. Populated by the webhook receiver (``field=comments``
    on the ``object=instagram`` envelope) and by manual list operations.
    Optionally linked to a :class:`Conversation` when the account
    wants comments to surface in the agent inbox.

References:
  * ``PLAN.instagram-graph.md`` for the verified Meta API spec.
  * Phase 5e's ``InstagramChannel`` in ``app.domains.inboxes.models`` —
    these rows FK into ``channel_instagram.id``.

State machines:
  * ``InstagramPost.state`` — pending / publishing / published / failed /
    deleted.
  * ``InstagramPostContainer.status_code`` — Meta's literal values:
    IN_PROGRESS / FINISHED / PUBLISHED / ERROR / EXPIRED.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.base_model import TimestampMixin

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
# InstagramPost.state — our side. Distinct from Meta's container
# status_code so it stays meaningful even before any Meta call lands
# (``pending`` predates container creation).
INSTAGRAM_POST_STATES: tuple[str, ...] = (
    "pending",
    "publishing",
    "published",
    "failed",
    "deleted",
)

# Meta's container status_code values — verbatim from
# https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-container/
INSTAGRAM_CONTAINER_STATUS_CODES: tuple[str, ...] = (
    "IN_PROGRESS",
    "FINISHED",
    "PUBLISHED",
    "ERROR",
    "EXPIRED",
)

# Media type literals — match Meta's API param values (uppercase) so
# we don't need a translation table. ``IMAGE`` is our synthetic value
# for the single-image case (Meta's API distinguishes by absence of
# ``media_type`` rather than passing ``IMAGE``).
INSTAGRAM_MEDIA_TYPES: tuple[str, ...] = (
    "IMAGE",
    "VIDEO",
    "REELS",
    "CAROUSEL",
    "STORIES",
)

InstagramPostState = Literal[
    "pending", "publishing", "published", "failed", "deleted"
]
InstagramContainerStatus = Literal[
    "IN_PROGRESS", "FINISHED", "PUBLISHED", "ERROR", "EXPIRED"
]
InstagramMediaType = Literal[
    "IMAGE", "VIDEO", "REELS", "CAROUSEL", "STORIES"
]


# ---------------------------------------------------------------------------
# InstagramPost — the publish request, one row per dashboard action.
# ---------------------------------------------------------------------------
class InstagramPost(TimestampMixin, table=True):
    """A single publish request the dashboard initiates.

    ``source`` is the JSONB payload the publisher needs:
      * IMAGE / VIDEO / REELS:
            ``{"image_url": "..."}`` or ``{"video_url": "...",
            "cover_url": "...", "share_to_feed": true}``
      * CAROUSEL:
            ``{"children": [{"image_url": "..."}, {"video_url": "..."}, ...]}``
      * STORIES:
            ``{"image_url": "..."}`` or ``{"video_url": "..."}``

    Carousel children are persisted as ``InstagramPostContainer`` rows
    (with ``position > 0``); the parent gets ``position = 0``. Single
    media types still get exactly one container row (``position = 0``).
    """

    __tablename__ = "instagram_posts"
    __table_args__ = (
        Index(
            "index_instagram_posts_on_channel_instagram_id",
            "channel_instagram_id",
        ),
        Index("index_instagram_posts_on_account_id", "account_id"),
        Index("index_instagram_posts_on_state", "state"),
        Index(
            "index_instagram_posts_on_scheduled_for",
            "scheduled_for",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    inbox_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    channel_instagram_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("channel_instagram.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    state: str = Field(
        default="pending",
        sa_column=Column(
            String, nullable=False, server_default="pending"
        ),
    )
    media_type: str = Field(sa_column=Column(String, nullable=False))
    caption: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    source: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    ig_media_id: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    ig_permalink: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    error_code: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    error_message: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    scheduled_for: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    published_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


# ---------------------------------------------------------------------------
# InstagramPostContainer — Meta-side creation IDs, polled to FINISHED.
# ---------------------------------------------------------------------------
class InstagramPostContainer(TimestampMixin, table=True):
    """One Meta container per ``POST /{ig-user}/media`` call.

    For a single image/video/story/reel: one row with ``position = 0``.
    For a carousel: N child rows with ``position = 1..N`` plus one
    parent row with ``position = 0`` (created only after all children
    are ``FINISHED``).

    ``poll_count`` is incremented by the ARQ poller each cycle (Meta
    recommends polling at most 5 times — we honour that as the
    retry cap before giving up and marking the post ``failed``).
    """

    __tablename__ = "instagram_post_containers"
    __table_args__ = (
        Index(
            "index_instagram_post_containers_on_post_id", "post_id"
        ),
        Index(
            "index_instagram_post_containers_on_status_code",
            "status_code",
        ),
        UniqueConstraint(
            "post_id",
            "position",
            name="index_instagram_post_containers_post_position",
        ),
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
        ),
    )
    ig_container_id: str = Field(sa_column=Column(String, nullable=False))
    position: int = Field(sa_column=Column(Integer, nullable=False))
    status_code: str = Field(
        default="IN_PROGRESS",
        sa_column=Column(
            String, nullable=False, server_default="IN_PROGRESS"
        ),
    )
    poll_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )


# ---------------------------------------------------------------------------
# InstagramComment — local mirror of moderated comments.
# ---------------------------------------------------------------------------
class InstagramComment(TimestampMixin, table=True):
    """Local representation of a comment on owned IG media.

    Populated two ways:
      * **Webhook**: ``object=instagram&field=comments`` fires on new
        comments + new replies. Phase I.8 receiver inserts/updates here.
      * **Manual list**: when the agent wants a fresh pull, the service
        layer calls ``GET /{ig-media-id}/comments`` and upserts.

    ``parent_comment_id`` is the IG-side id of the parent comment (NULL
    for top-level). Self-FK isn't enforced because parents may arrive
    out of order from the webhook stream — orphan replies just dangle
    until a backfill list-fetch pulls the missing parent.

    ``conversation_id`` is optional — when the account opts to route
    comments into the agent inbox, the webhook receiver creates a
    Conversation and back-links it here. Otherwise the comment lives
    only in this table for moderation.
    """

    __tablename__ = "instagram_comments"
    __table_args__ = (
        UniqueConstraint(
            "ig_comment_id",
            name="index_instagram_comments_on_ig_comment_id",
        ),
        Index(
            "index_instagram_comments_on_channel_instagram_id",
            "channel_instagram_id",
        ),
        Index(
            "index_instagram_comments_on_ig_media_id", "ig_media_id"
        ),
        Index(
            "index_instagram_comments_on_parent_comment_id",
            "parent_comment_id",
        ),
        Index(
            "index_instagram_comments_on_conversation_id",
            "conversation_id",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    channel_instagram_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("channel_instagram.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    ig_comment_id: str = Field(sa_column=Column(String, nullable=False))
    ig_media_id: str = Field(sa_column=Column(String, nullable=False))
    parent_comment_id: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    from_username: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    from_id: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    text: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    hidden: bool = Field(
        default=False,
        sa_column=Column(
            Boolean, nullable=False, server_default="false"
        ),
    )
    conversation_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    ig_created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


__all__ = [
    "INSTAGRAM_CONTAINER_STATUS_CODES",
    "INSTAGRAM_MEDIA_TYPES",
    "INSTAGRAM_POST_STATES",
    "InstagramComment",
    "InstagramContainerStatus",
    "InstagramMediaType",
    "InstagramPost",
    "InstagramPostContainer",
    "InstagramPostState",
]
