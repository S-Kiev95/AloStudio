"""Publications and their per-channel targets (account-scoped).

A :class:`Publication` is written and scheduled once; each
:class:`PublicationTarget` is one :class:`PublishingChannel` it goes out to. The
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
    Boolean,
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
from sqlalchemy import text as sa_text
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

CHANNEL_STATUS_ACTIVE = "active"
# The network stopped accepting the stored credentials: someone has to
# connect the account again before it can publish.
CHANNEL_STATUS_RECONNECT = "reconnect"


class PublishingChannel(TimestampMixin, table=True):
    """An account on a social network that the account publishes to.

    Networks that also message through an inbox (Instagram, Facebook
    Pages) get one channel per inbox (``inbox_id``), created from the inbox
    and using its credentials. Networks that only publish hold their own
    in ``credentials``, keyed by the network's account id
    (``external_id``). Publications, targets and figures refer to the
    channel, never to the inbox, so both kinds work the same way.
    """

    __tablename__ = "publishing_channels"
    __table_args__ = (
        UniqueConstraint("inbox_id", name="uniq_publishing_channels_inbox"),
        Index(
            "uniq_publishing_channels_account_network_external",
            "account_id",
            "network",
            "external_id",
            unique=True,
            postgresql_where=sa_text("external_id IS NOT NULL"),
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
            index=True,
        ),
    )
    # Key of the adapter that publishes to this channel.
    network: str = Field(sa_column=Column(String, nullable=False))
    name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    username: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    avatar_url: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    external_id: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    inbox_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    # Tokens of a network that doesn't go through an inbox. Never presented.
    credentials: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    token_expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    status: str = Field(
        default=CHANNEL_STATUS_ACTIVE,
        sa_column=Column(
            String, nullable=False, server_default=CHANNEL_STATUS_ACTIVE
        ),
    )
    status_message: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )


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
            "index_publication_targets_on_account_id_and_channel_id",
            "account_id",
            "channel_id",
        ),
        UniqueConstraint(
            "publication_id",
            "channel_id",
            name="uniq_publication_targets_publication_channel",
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
    channel_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("publishing_channels.id", ondelete="CASCADE"),
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
            "channel_id", "date", name="uniq_channel_metric_snapshots_channel_date"
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
    channel_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("publishing_channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    network: str = Field(sa_column=Column(String, nullable=False))
    date: date_type = Field(sa_column=Column(Date, nullable=False))
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )



class PublishingSignature(TimestampMixin, table=True):
    """A saved text the composer adds to a publication (contact details,
    hashtags…). At most one per account is added on its own to every new
    publication (``auto_add``)."""

    __tablename__ = "publishing_signatures"

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    content: str = Field(sa_column=Column(Text, nullable=False))
    auto_add: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    created_by_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


class PublicationSet(TimestampMixin, table=True):
    """The composer saved under a name — text, media and the channels with
    their per-network settings — so a publication can start from it.
    ``payload`` has the shape of a publication request without the date:
    ``{"content", "media": [...], "targets": [{"channel_id", "settings",
    "content_override"}]}``."""

    __tablename__ = "publication_sets"

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    created_by_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


AUTOPOST_MODE_PUBLISH = "publish"
AUTOPOST_MODE_DRAFT = "draft"
AUTOPOST_MODES: tuple[str, ...] = (AUTOPOST_MODE_PUBLISH, AUTOPOST_MODE_DRAFT)


class PublishingAutopost(TimestampMixin, table=True):
    """An RSS/Atom feed whose new entries become publications: published
    right away, or saved as drafts for someone to review (``mode``)."""

    __tablename__ = "publishing_autoposts"

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    feed_url: str = Field(sa_column=Column(Text, nullable=False))
    mode: str = Field(
        default=AUTOPOST_MODE_PUBLISH,
        sa_column=Column(String, nullable=False, server_default=AUTOPOST_MODE_PUBLISH),
    )
    active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    # Channels it publishes to; empty means every active channel of the
    # account at the time of each entry.
    channel_ids: list[int] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
    # On the first read, also publish the newest entry already in the feed
    # (otherwise only entries that appear afterwards).
    start_with_latest: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    # The newest entry seen (its guid, id or link): entries above it are new.
    last_item_key: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    last_checked_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_by_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


class PublishingPlug(TimestampMixin, table=True):
    """An automatic action on a channel's own posts once they reach
    ``likes_threshold`` likes (reply with ``message``, repost…). Which
    ``kind`` a network offers is up to its adapter (``plug_kinds``)."""

    __tablename__ = "publishing_plugs"
    __table_args__ = (
        UniqueConstraint("channel_id", "kind", name="uniq_publishing_plugs_channel_kind"),
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
            index=True,
        ),
    )
    channel_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("publishing_channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    kind: str = Field(sa_column=Column(String, nullable=False))
    likes_threshold: int = Field(sa_column=Column(Integer, nullable=False))
    message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    created_by_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


class PublishingPlugRun(TimestampMixin, table=True):
    """A plug fired on one post. One per plug and post, so it never fires
    twice; a failure stays recorded and is not retried."""

    __tablename__ = "publishing_plug_runs"
    __table_args__ = (
        UniqueConstraint("plug_id", "target_id", name="uniq_publishing_plug_runs_plug_target"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    plug_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("publishing_plugs.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    target_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("publication_targets.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    ok: bool = Field(sa_column=Column(Boolean, nullable=False))
    external_id: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


__all__ = [
    "AUTOPOST_MODES",
    "AUTOPOST_MODE_DRAFT",
    "AUTOPOST_MODE_PUBLISH",
    "CHANNEL_METRIC_KEYS",
    "CHANNEL_STATUS_ACTIVE",
    "CHANNEL_STATUS_RECONNECT",
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
    "PublicationSet",
    "PublicationTarget",
    "PublishingAutopost",
    "PublishingChannel",
    "PublishingPlug",
    "PublishingPlugRun",
    "PublishingSignature",
]
