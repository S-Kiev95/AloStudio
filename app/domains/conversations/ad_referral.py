"""Ad attribution: which Meta ad started this conversation.

When someone taps a *click-to-WhatsApp* or *click-to-Messenger* ad, Meta
attaches a ``referral`` block to the inbound message. Capturing it answers
the question a business that advertises always asks — "which ad brought me
this customer?" — without any extra API call or permission.

Payload shapes differ per surface:

* **WhatsApp Cloud** — ``messages[].referral`` with ``source_type``,
  ``source_id``, ``headline`` and ``ctwa_clid``.
* **Messenger / Instagram** — ``messaging[].referral`` (a fresh thread) or
  ``messaging[].message.referral`` (an existing one), with ``source``,
  ``type``, ``ref``, ``ad_id`` and a nested ``ads_context_data``.

Meta's public docs for the WhatsApp variant were mid-reorganisation when
this was written, so the parser never *requires* a field: it reads what it
recognises, tolerates what it doesn't, and always keeps the untouched block
in ``Conversation.ad_referral``. Reconciling against a real payload is then
a read of stored data rather than a re-capture.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domains.conversations.models import Conversation

log = logging.getLogger(__name__)

# ``source_type`` (WhatsApp) and ``source`` (Messenger) use different
# vocabularies for the same idea; normalise so reports group cleanly.
_SOURCE_ALIASES = {
    "ad": "ad",
    "ads": "ad",
    "post": "post",
    "shortlink": "shortlink",
    "sms": "shortlink",
}


@dataclass(frozen=True)
class AdReferral:
    """A normalised ad referral, plus the payload it came from."""

    source: str | None = None
    ad_id: str | None = None
    headline: str | None = None
    click_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """True when nothing identifying survived parsing.

        A referral with no ad id *and* no source is not worth stamping —
        it would only add noise to the reports.
        """
        return not (self.ad_id or self.source)


def _clean(value: Any) -> str | None:
    """Coerce a payload value to a trimmed string, or None."""
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    text = str(value).strip()
    return text or None


def _normalise_source(value: Any) -> str | None:
    text = _clean(value)
    return _SOURCE_ALIASES.get(text.lower(), text.lower()) if text else None


def parse_whatsapp_referral(message: dict[str, Any]) -> AdReferral | None:
    """Read ``messages[].referral`` from a WhatsApp Cloud inbound message."""
    raw = message.get("referral")
    if not isinstance(raw, dict) or not raw:
        return None
    referral = AdReferral(
        source=_normalise_source(raw.get("source_type")),
        # ``source_id`` is the ad id on this surface.
        ad_id=_clean(raw.get("source_id")),
        headline=_clean(raw.get("headline")) or _clean(raw.get("body")),
        click_id=_clean(raw.get("ctwa_clid")),
        raw=raw,
    )
    return None if referral.is_empty else referral


def parse_messenger_referral(event: dict[str, Any]) -> AdReferral | None:
    """Read a Messenger/Instagram referral.

    It arrives at the top level of the messaging event when the thread is
    new, and nested under ``message`` when the person was already talking to
    the page — both shapes mean the same thing.
    """
    raw = event.get("referral")
    if not isinstance(raw, dict) or not raw:
        message = event.get("message")
        raw = message.get("referral") if isinstance(message, dict) else None
    if not isinstance(raw, dict) or not raw:
        return None

    context = raw.get("ads_context_data")
    context = context if isinstance(context, dict) else {}
    referral = AdReferral(
        source=_normalise_source(raw.get("source")),
        ad_id=_clean(raw.get("ad_id")),
        # ``ref`` is the advertiser's own passthrough value; it is the best
        # human label available when the ad carries no title.
        headline=_clean(context.get("ad_title")) or _clean(raw.get("ref")),
        click_id=None,  # Messenger has no ctwa_clid equivalent
        raw=raw,
    )
    return None if referral.is_empty else referral


def stamp_conversation(
    conversation: Conversation, referral: AdReferral | None
) -> bool:
    """Attribute ``conversation`` to ``referral``. Returns True if it wrote.

    First touch wins. A conversation is reused across inbound messages (and
    reopened after resolution), so without this guard a later ad click would
    silently rewrite the history of how the customer originally arrived.
    A different ad landing on an attributed thread is logged, not applied.
    """
    if referral is None or referral.is_empty:
        return False

    if conversation.ad_id or conversation.ad_source:
        if referral.ad_id and referral.ad_id != conversation.ad_id:
            log.info(
                "ads.referral.ignored_second_touch conversation_id=%s "
                "kept_ad_id=%s incoming_ad_id=%s",
                conversation.id,
                conversation.ad_id,
                referral.ad_id,
            )
        return False

    conversation.ad_source = referral.source
    conversation.ad_id = referral.ad_id
    conversation.ad_headline = referral.headline
    conversation.ad_click_id = referral.click_id
    conversation.ad_referral = referral.raw
    conversation.ad_captured_at = datetime.now(UTC)
    log.info(
        "ads.referral.captured conversation_id=%s source=%s ad_id=%s",
        conversation.id,
        referral.source,
        referral.ad_id,
    )
    return True


__all__ = [
    "AdReferral",
    "parse_messenger_referral",
    "parse_whatsapp_referral",
    "stamp_conversation",
]
