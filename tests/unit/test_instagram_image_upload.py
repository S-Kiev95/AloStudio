"""Unit tests for Instagram post-media normalisation + signed public links.

Meta's Content Publishing API only accepts JPEG and fetches the file itself,
so an upload has to be converted and served from a signed public URL.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.signed_links import expiry_from_now, is_valid, sign
from app.domains.uploads.images import (
    MAX_BYTES,
    MAX_EDGE,
    ImageConversionError,
    to_instagram_jpeg,
)
from app.domains.uploads.public_router import _payload, public_media_url


def _png(size=(64, 48), color=(255, 0, 0, 128)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg(size=(64, 48)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# to_instagram_jpeg
# ---------------------------------------------------------------------------
def test_png_becomes_jpeg():
    out = to_instagram_jpeg(_png())
    with Image.open(io.BytesIO(out)) as im:
        assert im.format == "JPEG"
        assert im.mode == "RGB"


def test_transparency_is_flattened_onto_white_not_black():
    """A straight RGB convert turns transparent pixels black, which reads as
    a rendering bug."""
    transparent = io.BytesIO()
    Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(transparent, format="PNG")
    out = to_instagram_jpeg(transparent.getvalue())
    with Image.open(io.BytesIO(out)) as im:
        assert im.convert("RGB").getpixel((4, 4)) == (255, 255, 255)


def test_jpeg_passes_through_as_jpeg():
    out = to_instagram_jpeg(_jpeg())
    with Image.open(io.BytesIO(out)) as im:
        assert im.format == "JPEG"


def test_oversized_image_is_downscaled():
    big = io.BytesIO()
    Image.new("RGB", (MAX_EDGE * 2, MAX_EDGE), (1, 2, 3)).save(
        big, format="JPEG"
    )
    out = to_instagram_jpeg(big.getvalue())
    with Image.open(io.BytesIO(out)) as im:
        assert max(im.size) <= MAX_EDGE
    assert len(out) <= MAX_BYTES


def test_non_image_is_rejected():
    with pytest.raises(ImageConversionError):
        to_instagram_jpeg(b"this is not an image at all")


def test_truncated_image_is_rejected():
    with pytest.raises(ImageConversionError):
        to_instagram_jpeg(_png()[:20])


# ---------------------------------------------------------------------------
# Signed public media link
# ---------------------------------------------------------------------------
def test_public_media_url_is_signed_and_key_escaped():
    key = "accounts/1/uploads/ab cd/instagram.jpg"
    url = public_media_url(key, ttl_seconds=600)
    assert "/public/media?" in url
    assert "%20" in url or "+" in url  # the space is escaped, not raw
    assert "sig=" in url and "exp=" in url


def test_signature_is_bound_to_the_key():
    """Signing is namespaced + key-bound, so a link can't be walked into an
    arbitrary-object read."""
    exp = expiry_from_now(600)
    assert sign(_payload("a/b.jpg"), exp) != sign(_payload("a/c.jpg"), exp)
    assert is_valid(_payload("a/b.jpg"), exp, sign(_payload("a/b.jpg"), exp))
    assert not is_valid(
        _payload("a/c.jpg"), exp, sign(_payload("a/b.jpg"), exp)
    )


def test_expired_signature_is_rejected():
    past = expiry_from_now(-10)
    assert not is_valid(_payload("a/b.jpg"), past, sign(_payload("a/b.jpg"), past))


def test_attachment_and_media_namespaces_do_not_collide():
    """An attachment signature must not unlock the key-addressed route."""
    from app.domains.conversations.attachments_router import (
        _payload as att_payload,
    )

    exp = expiry_from_now(600)
    assert sign(att_payload(7), exp) != sign(_payload("7"), exp)
