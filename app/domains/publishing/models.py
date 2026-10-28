"""Publications and their per-channel targets (account-scoped).

A :class:`Publication` is written and scheduled once; each
:class:`PublicationTarget` is one channel (an inbox) it goes out to. The
network-specific work happens in ``app.domains.publishing.adapters`` — the
models only store which adapter owns a target (``network``) and the
adapter's own options (``settings``) and references (``extra``).

The publication's state is derived from its targets once publishing
starts: all published → ``published``, some → ``partially_published``,
none → ``failed``.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
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

PUBLICATION_STATE_DRAFT = "draft"
PUBLICATION_STATE_SCHEDULED = "scheduled"
PUBLICATION_STATE_PUBLISHING = "publishing"
PUBLICATION_STATE_PUBLISHED = "published"
PUBLICATION_STATE_PARTIALLY_PUBLISHED = "partially_published"
PUBLICATION_STATE_FAILED = "failed"

PUBLICATION_STATES: tuple[str, ...] = (
    PUBLICATION_STATE_DRAFT,
    PUBLICATION_STATE_SCHEDULED,
    PUBLICATION_STATE_PUBLISHING,
    PUBLICATION_STATE_PUBLISHED,
    PUBLICATION_STATE_PARTIALLY_PUBLISHED,
    PUBLICATION_STATE_FAILED,
)

# States in which the publication can still be edited or cancelled.
PUBLICATION_EDITABLE_STATES: tuple[str, ...] = (
    PUBLICATION_STATE_DRAFT,
    PUBLICATION_STATE_SCHEDULED,
)

TARGET_STATE_PENDING = "pending"
TARGET_STATE_PUBLISHING = "publishing"
TARGET_STATE_PUBLISHED = "published"
TARGET_STATE_FAILED = "failed"

MEDIA_TYPES: tuple[str, ...] = ("image", "video")


class Publication(TimestampMixin, table=True):
    """Content written once and scheduled to one or more channels."""

    __tablename__ = "publications"
    __table_args__ = (
        Index(
            "index_publications_on_account_id_and_scheduled_for",
            "account_id",
            "scheduled_for",
        ),
        Index(
            "index_publications_on_state_and_scheduled_for",
            "state",
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
    content: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    # Ordered ``[{"type": "image" | "video", "url": str}]``. The URLs must
    # be public: each network downloads the file itself.
    media: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
    scheduled_for: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    state: str = Field(
        default=PUBLICATION_STATE_DRAFT,
        sa_column=Column(
            String, nullable=False, server_default=PUBLICATION_STATE_DRAFT
        ),
    )
    created_by_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    published_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class PublicationTarget(TimestampMixin, table=True):
    """One channel a publication goes out to."""

    __tablename__ = "publication_targets"
    # Lookups by publication use the leading column of the unique index.
    __table_args__ = (
        Index(
            "index_publication_targets_on_account_id_and_inbox_id",
            "account_id",
            "inbox_id",
        ),
        UniqueConstraint(
            "publication_id",
            "inbox_id",
            name="uniq_publication_targets_publication_inbox",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    publication_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("publications.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
    # Key of the adapter that publishes this target.
    network: str = Field(sa_column=Column(String, nullable=False))
    # Adapter-specific options; validated by the adapter.
    settings: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    content_override: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    state: str = Field(
        default=TARGET_STATE_PENDING,
        sa_column=Column(
            String, nullable=False, server_default=TARGET_STATE_PENDING
        ),
    )
    external_id: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    permalink: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    error_code: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    error_message: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    attempts: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    published_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    # Adapter references (e.g. the id of a row the adapter created).
    extra: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    # Latest engagement figures for the published post, with the normalised
    # keys of ``METRIC_KEYS`` (only the ones the network reports). Cached:
    # networks rate-limit insights, so a scheduled job refreshes them.
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    metrics_updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    # Why the last refresh failed (missing permission, deleted post…);
    # cleared by the next successful one.
    metrics_error: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )


# Normalised metric names. Each adapter maps its network's figures onto
# these; a network that doesn't report one simply leaves it out.
METRIC_KEYS: tuple[str, ...] = (
    "views",
    "reach",
    "likes",
    "comments",
    "shares",
    "saves",
    "interactions",
)
CHANNEL_METRIC_KEYS: tuple[str, ...] = (
    "followers",
    "views",
    "reach",
    "interactions",
)


class ChannelMetricSnapshot(TimestampMixin, table=True):
    """One day of a publishing channel's account-level figures: followers
    as seen that day, plus that day's views/reach/interactions when the
    network reports them (filled in a day or two later). Charts growth."""

    __tablename__ = "channel_metric_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "inbox_id", "date", name="uniq_channel_metric_snapshots_inbox_date"
        ),
        Index(
            "index_channel_metric_snapshots_on_account_id_and_date",
            "account_id",
            "date",
        ),
        Index("index_channel_metric_snapshots_on_date", "date"),
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
    network: str = Field(sa_column=Column(String, nullable=False))
    date: date_type = Field(sa_column=Column(Date, nullable=False))
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )


__all__ = [
    "CHANNEL_METRIC_KEYS",
    "MEDIA_TYPES",
    "METRIC_KEYS",
    "PUBLICATION_EDITABLE_STATES",
    "PUBLICATION_STATES",
    "PUBLICATION_STATE_DRAFT",
    "PUBLICATION_STATE_FAILED",
    "PUBLICATION_STATE_PARTIALLY_PUBLISHED",
    "PUBLICATION_STATE_PUBLISHED",
    "PUBLICATION_STATE_PUBLISHING",
    "PUBLICATION_STATE_SCHEDULED",
    "TARGET_STATE_FAILED",
    "TARGET_STATE_PENDING",
    "TARGET_STATE_PUBLISHED",
    "TARGET_STATE_PUBLISHING",
    "ChannelMetricSnapshot",
    "Publication",
    "PublicationTarget",
]
