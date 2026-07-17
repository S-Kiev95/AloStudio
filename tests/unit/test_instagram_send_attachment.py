"""Unit tests for the Instagram outbound attachment path (no DB).

Covers the two pure pieces: Rails' ``attachment_type`` degradation, and the
signed public link Meta downloads outbound media from.

Anchors:
  reference/chatwoot/app/services/instagram/base_send_service.rb
"""

from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

from app.core.config import get_settings
from app.domains.conversations.attachments_router import (
    _public_signature,
    public_attachment_url,
)
from app.domains.instagram.sender import _send_attachment_type


# ---------------------------------------------------------------------------
# attachment_type (Rails' allow-list)
# ---------------------------------------------------------------------------
def test_send_attachment_type_passes_meta_known_types():
    for known in ("image", "audio", "video", "file"):
        assert _send_attachment_type(known) == known


def test_send_attachment_type_degrades_unknown_to_file():
    """Meta's Send API has no ig_post/share/story_mention — Rails sends
    those as a plain ``file``."""
    for ours in ("ig_post", "ig_story", "ig_reel", "share", "story_mention"):
        assert _send_attachment_type(ours) == "file"


# ---------------------------------------------------------------------------
# Signed public link
# ---------------------------------------------------------------------------
def test_public_attachment_url_is_signed_and_expiring():
    url = public_attachment_url(42, ttl_seconds=600)
    assert url.startswith(get_settings().app_base_url.rstrip("/"))
    assert "/public/attachments/42?" in url

    q = parse_qs(urlparse(url).query)
    exp = int(q["exp"][0])
    sig = q["sig"][0]
    assert exp > int(time.time())
    assert exp <= int(time.time()) + 600
    assert sig == _public_signature(42, exp)


def test_public_signature_is_bound_to_id_and_expiry():
    """A signature must not be replayable for another attachment or a later
    expiry."""
    exp = 1_800_000_000
    assert _public_signature(1, exp) != _public_signature(2, exp)
    assert _public_signature(1, exp) != _public_signature(1, exp + 1)


def test_public_attachment_url_uses_public_base_not_the_store():
    """The link has to be fetchable from the internet — the object store is
    internal-only."""
    url = public_attachment_url(7)
    assert "9100" not in url  # never the MinIO endpoint
