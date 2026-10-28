"""The contract every network adapter implements.

The publishing domain never names a network: it asks the registry for the
adapter that owns an inbox (``supports``) or a channel or target
(``network``), and calls the methods below. Everything a network needs —
limits, API calls, error wording — lives in its adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, ClassVar

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.inboxes.models import Inbox
from app.domains.publishing.models import (
    CHANNEL_STATUS_RECONNECT,
    Publication,
    PublicationTarget,
    PublishingChannel,
)


@dataclass
class PublishResult:
    """Outcome of publishing one target. Adapters return failures here
    instead of raising, so one network failing never stops the others."""

    ok: bool
    external_id: str | None = None
    permalink: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    # True when trying again later can succeed (rate limits, 5xx,
    # network errors); False for permissions, bad data or expired tokens.
    retryable: bool = False


@dataclass
class MetricsResult:
    """Figures read from a network, keyed by the normalised names of
    ``METRIC_KEYS`` / ``CHANNEL_METRIC_KEYS``. Like publishing, failures
    come back here (``error_message`` in Spanish) instead of raising.

    ``metrics`` is the current state (a post's lifetime figures, or a
    channel's followers today); ``daily`` holds per-day channel figures,
    each under the day they belong to."""

    ok: bool
    metrics: dict[str, int] = field(default_factory=dict)
    daily: dict[date, dict[str, int]] = field(default_factory=dict)
    error_message: str | None = None


@dataclass
class Credentials:
    """What a network gives back for an authorized account: stored on the
    channel and never presented."""

    credentials: dict[str, Any]
    token_expires_at: datetime | None = None


@dataclass
class ConnectedAccount(Credentials):
    """The account a network just authorized, ready to become a channel
    (or to refresh the one it already is)."""

    external_id: str = ""
    name: str | None = None
    username: str | None = None
    avatar_url: str | None = None


class ChannelConnectionError(Exception):
    """A connection or token renewal the network refused; the message is
    in Spanish, for the owner."""


class PublishingAdapter(ABC):
    """One social network."""

    #: Stable key stored on ``PublicationTarget.network``.
    network: ClassVar[str]
    #: Name shown to connect a channel of a network that doesn't publish
    #: through an inbox; ``None`` for those that do.
    label: ClassVar[str | None] = None

    def supports(self, inbox: Inbox) -> bool:
        """Whether this adapter publishes through the inbox (networks that
        also message, like Instagram). Such inboxes get a channel of their
        own automatically; other networks connect their channels apart."""
        return False

    # -- Connecting a channel (networks with a ``label``) -------------------
    def missing_connection_settings(self) -> list[str]:
        """Installation settings that are still empty, so connecting can't
        work yet (shown to the owner by name)."""
        return []

    def authorize_url(self, *, state: str, redirect_uri: str) -> str:
        """Where the owner's browser goes to authorize an account."""
        raise NotImplementedError

    async def complete_authorization(
        self, *, code: str, redirect_uri: str
    ) -> ConnectedAccount:
        """Trade the authorization code for the account and its
        credentials. Raises :class:`ChannelConnectionError`."""
        raise NotImplementedError

    async def refresh_credentials(
        self, channel: PublishingChannel
    ) -> Credentials | None:
        """Fresh credentials before the stored ones expire, or ``None`` when
        the network's don't. Raises :class:`ChannelConnectionError` when
        they can't be renewed and the owner has to connect again."""
        return None

    @abstractmethod
    def validate(
        self, publication: Publication, target: PublicationTarget
    ) -> list[str]:
        """Human-readable problems (Spanish) that would make the network
        reject the target. Empty list when it can be published."""

    @abstractmethod
    async def publish(
        self,
        session: AsyncSession,
        publication: Publication,
        target: PublicationTarget,
    ) -> PublishResult:
        """Publish one target. Must not raise on network-side errors."""

    async def fetch_post_metrics(
        self, session: AsyncSession, target: PublicationTarget
    ) -> MetricsResult | None:
        """Engagement figures of a published target. ``None`` when the
        network offers none."""
        return None

    async def fetch_channel_metrics(
        self, session: AsyncSession, channel: PublishingChannel, *, days: list[date]
    ) -> MetricsResult | None:
        """Account-level figures of the channel: followers now, and per-day
        views/reach/interactions for ``days`` when the network reports them
        (re-read a few days back: networks finish a day late). ``None``
        when the network offers none."""
        return None


async def channel_inbox(session: AsyncSession, channel_id: int) -> Inbox | None:
    """The inbox a channel publishes through, for adapters that ``support``
    inboxes. ``None`` when the channel or its inbox is gone."""
    channel = await session.get(PublishingChannel, channel_id)
    if channel is None or channel.inbox_id is None:
        return None
    return await session.get(Inbox, channel.inbox_id)


async def mark_reconnect(
    session: AsyncSession, channel_id: int, message: str
) -> None:
    """Flag a channel whose credentials the network stopped accepting: it
    can't be chosen to publish until the owner connects it again."""
    channel = await session.get(PublishingChannel, channel_id)
    if channel is None:
        return
    channel.status = CHANNEL_STATUS_RECONNECT
    channel.status_message = message
    session.add(channel)
    await session.flush()


def target_text(publication: Publication, target: PublicationTarget) -> str:
    """The text a target goes out with: its override, or the shared one."""
    if target.content_override is not None:
        return target.content_override
    return publication.content or ""


__all__ = [
    "ChannelConnectionError",
    "ConnectedAccount",
    "Credentials",
    "MetricsResult",
    "PublishResult",
    "PublishingAdapter",
    "channel_inbox",
    "mark_reconnect",
    "target_text",
]
