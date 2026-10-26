"""Registry of network adapters.

Adding a network means writing an adapter module and listing it in
``_ADAPTERS``; nothing else in the publishing domain changes.
"""

from __future__ import annotations

from app.domains.inboxes.models import Inbox
from app.domains.publishing.adapters.base import (
    PublishingAdapter,
    PublishResult,
    target_text,
)
from app.domains.publishing.adapters.facebook_page import FacebookPageAdapter
from app.domains.publishing.adapters.instagram import InstagramAdapter

_ADAPTERS: tuple[PublishingAdapter, ...] = (
    InstagramAdapter(),
    FacebookPageAdapter(),
)


def adapter_for_network(network: str) -> PublishingAdapter | None:
    for adapter in _ADAPTERS:
        if adapter.network == network:
            return adapter
    return None


def adapter_for_inbox(inbox: Inbox) -> PublishingAdapter | None:
    for adapter in _ADAPTERS:
        if adapter.supports(inbox):
            return adapter
    return None


__all__ = [
    "PublishResult",
    "PublishingAdapter",
    "adapter_for_inbox",
    "adapter_for_network",
    "target_text",
]
