"""Unit tests for ad attribution parsing + stamping (no DB).

The payloads here mirror the shapes Meta documents for click-to-WhatsApp and
click-to-Messenger ads. The parser is deliberately tolerant — Meta's public
reference for the WhatsApp variant was mid-reorganisation when this landed —
so these tests pin both what we read and what we refuse to guess at.
"""

from __future__ import annotations

import pytest

from app.core.models_registry import import_all_models
from app.domains.conversations.ad_referral import (
    parse_messenger_referral,
    parse_whatsapp_referral,
    stamp_conversation,
)
from app.domains.conversations.models import Conversation

# Instantiating a Conversation configures its mappers, which resolve
# relationship targets by class name — so every model module has to be
# imported first. Cheaper than pulling in the whole app.
import_all_models()

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# WhatsApp
# ---------------------------------------------------------------------------
def test_whatsapp_reads_the_documented_fields():
    msg = {
        "from": "5491100000000",
        "text": {"body": "Hola"},
        "referral": {
            "source_type": "ad",
            "source_id": "1200456789",
            "headline": "20% OFF en toda la tienda",
            "body": "Solo por hoy",
            "ctwa_clid": "ARaBcD123",
        },
    }
    ref = parse_whatsapp_referral(msg)
    assert ref is not None
    assert ref.source == "ad"
    assert ref.ad_id == "1200456789"
    assert ref.headline == "20% OFF en toda la tienda"
    assert ref.click_id == "ARaBcD123"
    # The untouched block is kept so an unanticipated shape is recoverable.
    assert ref.raw["ctwa_clid"] == "ARaBcD123"


def test_whatsapp_falls_back_to_body_when_no_headline():
    ref = parse_whatsapp_referral(
        {"referral": {"source_type": "ad", "source_id": "9", "body": "Texto"}}
    )
    assert ref is not None
    assert ref.headline == "Texto"


def test_whatsapp_without_referral_is_none():
    assert parse_whatsapp_referral({"text": {"body": "Hola"}}) is None
    assert parse_whatsapp_referral({"referral": {}}) is None


def test_whatsapp_unidentifiable_referral_is_dropped():
    """A block with neither ad id nor source would only add noise."""
    assert parse_whatsapp_referral({"referral": {"headline": "algo"}}) is None


# ---------------------------------------------------------------------------
# Messenger / Instagram
# ---------------------------------------------------------------------------
def test_messenger_reads_a_top_level_referral():
    event = {
        "sender": {"id": "PSID"},
        "referral": {
            "source": "ADS",
            "type": "OPEN_THREAD",
            "ad_id": "6045246247433",
            "ads_context_data": {"ad_title": "Envío gratis"},
        },
    }
    ref = parse_messenger_referral(event)
    assert ref is not None
    assert ref.source == "ad"  # 'ADS' normalised
    assert ref.ad_id == "6045246247433"
    assert ref.headline == "Envío gratis"


def test_messenger_reads_a_referral_nested_under_message():
    """An already-open thread carries the referral inside ``message``."""
    event = {
        "message": {
            "mid": "m_1",
            "text": "Hola",
            "referral": {"source": "ADS", "ad_id": "77"},
        }
    }
    ref = parse_messenger_referral(event)
    assert ref is not None
    assert ref.ad_id == "77"


def test_messenger_shortlink_keeps_ref_as_the_label():
    ref = parse_messenger_referral(
        {"referral": {"source": "SHORTLINK", "ref": "promo-verano"}}
    )
    assert ref is not None
    assert ref.source == "shortlink"
    assert ref.headline == "promo-verano"


def test_shortlink_singular_and_plural_fold_together():
    """m.me sends SHORTLINK, ig.me sends SHORTLINKS — one concept.

    Left unfolded they'd group as two different sources in reports.
    """
    singular = parse_messenger_referral({"referral": {"source": "SHORTLINK", "ref": "a"}})
    plural = parse_messenger_referral({"referral": {"source": "SHORTLINKS", "ref": "a"}})
    assert singular is not None and plural is not None
    assert singular.source == plural.source == "shortlink"


def test_messenger_without_referral_is_none():
    assert parse_messenger_referral({"message": {"text": "Hola"}}) is None


# ---------------------------------------------------------------------------
# Stamping
# ---------------------------------------------------------------------------
def _conv() -> Conversation:
    return Conversation(account_id=1, inbox_id=1, contact_id=1, display_id=1)


def test_stamp_writes_every_field():
    conv = _conv()
    ref = parse_whatsapp_referral(
        {"referral": {"source_type": "ad", "source_id": "42",
                      "headline": "Hola", "ctwa_clid": "CLID"}}
    )
    assert stamp_conversation(conv, ref) is True
    assert conv.ad_source == "ad"
    assert conv.ad_id == "42"
    assert conv.ad_headline == "Hola"
    assert conv.ad_click_id == "CLID"
    assert conv.ad_referral["source_id"] == "42"
    assert conv.ad_captured_at is not None


def test_first_touch_wins():
    """A later ad must not rewrite how the customer originally arrived.

    Conversations are reused across inbound messages and reopened after
    resolution, so without this guard the attribution would drift to
    whichever ad the person clicked most recently.
    """
    conv = _conv()
    first = parse_whatsapp_referral(
        {"referral": {"source_type": "ad", "source_id": "111", "headline": "A"}}
    )
    second = parse_whatsapp_referral(
        {"referral": {"source_type": "ad", "source_id": "222", "headline": "B"}}
    )
    assert stamp_conversation(conv, first) is True
    assert stamp_conversation(conv, second) is False
    assert conv.ad_id == "111"
    assert conv.ad_headline == "A"


def test_stamp_ignores_nothing_to_stamp():
    conv = _conv()
    assert stamp_conversation(conv, None) is False
    assert conv.ad_id is None
