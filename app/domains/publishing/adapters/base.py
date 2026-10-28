"""The contract every network adapter implements.

The publishing domain never names a network: it asks the registry for the
adapter that owns an inbox (``supports``) or a channel or target
(``network``), and calls the methods below. Everything a network needs —
limits, API calls, error wording — lives in its adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, ClassVar

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.inboxes.models import Inbox
from app.domains.publishing.models import (
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


class PublishingAdapter(ABC):
    """One social network."""

    #: Stable key stored on ``PublicationTarget.network``.
    network: ClassVar[str]

    def supports(self, inbox: Inbox) -> bool:
        """Whether this adapter publishes through the inbox (networks that
        also message, like Instagram). Such inboxes get a channel of their
        own automatically; other networks connect their channels apart."""
        return False

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


def target_text(publication: Publication, target: PublicationTarget) -> str:
    """The text a target goes out with: its override, or the shared one."""
    if target.content_override is not None:
        return target.content_override
    return publication.content or ""


__all__ = [
    "MetricsResult",
    "PublishResult",
    "PublishingAdapter",
    "channel_inbox",
    "target_text",
]
