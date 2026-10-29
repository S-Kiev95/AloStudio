"""Registry of network adapters.

Adding a network means writing an adapter module and listing it in
``_ADAPTERS``; nothing else in the publishing domain changes.
"""

from __future__ import annotations

from app.domains.inboxes.models import Inbox
from app.domains.publishing.adapters.base import (
    ChannelConnectionError,
    ConnectedAccount,
    ConnectionField,
    Credentials,
    MetricsResult,
    PlugKind,
    PublishingAdapter,
    PublishResult,
    channel_inbox,
    mark_reconnect,
    target_text,
)
from app.domains.publishing.adapters.discord import DiscordAdapter
from app.domains.publishing.adapters.facebook_page import FacebookPageAdapter
from app.domains.publishing.adapters.instagram import InstagramAdapter
from app.domains.publishing.adapters.telegram import TelegramAdapter
from app.domains.publishing.adapters.threads import ThreadsAdapter

_ADAPTERS: tuple[PublishingAdapter, ...] = (
    InstagramAdapter(),
    FacebookPageAdapter(),
    ThreadsAdapter(),
    TelegramAdapter(),
    DiscordAdapter(),
)


def adapter_for_network(network: str) -> PublishingAdapter | None:
    for adapter in _ADAPTERS:
        if adapter.network == network:
            return adapter
    return None


def all_adapters() -> tuple[PublishingAdapter, ...]:
    return _ADAPTERS


def connectable_adapters() -> list[PublishingAdapter]:
    """Networks whose channels are connected apart from inboxes."""
    return [adapter for adapter in _ADAPTERS if adapter.label is not None]


def adapter_for_inbox(inbox: Inbox) -> PublishingAdapter | None:
    for adapter in _ADAPTERS:
        if adapter.supports(inbox):
            return adapter
    return None


__all__ = [
    "ChannelConnectionError",
    "ConnectedAccount",
    "ConnectionField",
    "Credentials",
    "MetricsResult",
    "PlugKind",
    "PublishResult",
    "PublishingAdapter",
    "adapter_for_inbox",
    "adapter_for_network",
    "all_adapters",
    "channel_inbox",
    "connectable_adapters",
    "mark_reconnect",
    "target_text",
]
