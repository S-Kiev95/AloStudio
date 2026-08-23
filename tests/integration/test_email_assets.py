"""Images embedded in email get links that do not expire.

Every other public link here expires and should. Email is the opposite
medium: the message is a copy the recipient keeps and may open a year
later, so a logo behind a 30-day link leaves a broken image in every
letter the organisation ever sent.
"""

from __future__ import annotations

import pytest

from app.core.signed_links import (
    expiry_from_now,
    is_valid,
    is_valid_permanent,
    sign,
    sign_permanent,
)
from app.domains.uploads.email_assets_router import _payload, email_asset_url

pytestmark = pytest.mark.unit

KEY = "accounts/1/uploads/abc123/email.jpg"


def test_a_permanent_signature_validates_without_an_expiry():
    sig = sign_permanent(_payload(KEY))
    assert is_valid_permanent(_payload(KEY), sig) is True


def test_a_tampered_key_is_refused():
    sig = sign_permanent(_payload(KEY))
    assert is_valid_permanent(_payload("accounts/2/otro.jpg"), sig) is False


def test_a_permanent_signature_cannot_be_replayed_as_an_expiring_one():
    """The two namespaces are separate on purpose: a link that never
    expires must not be usable where an expiring one was required."""
    permanent = sign_permanent(_payload(KEY))
    later = expiry_from_now(3600)
    assert is_valid(_payload(KEY), later, permanent) is False


def test_an_expiring_signature_cannot_be_replayed_as_permanent():
    expiring = sign(_payload(KEY), expiry_from_now(3600))
    assert is_valid_permanent(_payload(KEY), expiring) is False


def test_the_url_is_absolute_and_carries_the_signature():
    """A mail client has no origin to resolve a relative path against —
    the message is read inside Gmail, not on our domain."""
    url = email_asset_url(KEY)
    assert url.startswith("http")
    assert "/public/email_asset?" in url
    assert "key=" in url
    assert "sig=" in url
    # No expiry parameter at all, which is the whole point.
    assert "exp=" not in url
