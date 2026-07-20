"""Normalise uploaded images into something Instagram will publish.

Meta's Content Publishing API only accepts **JPEG** — a PNG (the format most
screenshots and design exports use) is rejected at container creation with an
unhelpful generic error. It also caps the file at 8 MB and expects no
transparency.

So rather than making the user convert by hand, we do it on the way in:
transparency is flattened onto white, EXIF orientation is baked in (otherwise
a phone photo publishes sideways), oversized images are downscaled, and
quality steps down until the file fits.
"""

from __future__ import annotations

import io
import logging

from PIL import Image, ImageOps, UnidentifiedImageError

log = logging.getLogger(__name__)

# Meta's documented ceiling for a published image.
MAX_BYTES = 8 * 1024 * 1024
# Instagram downscales anything wider than 1440 anyway; sending more just
# burns the byte budget.
MAX_EDGE = 1440
_QUALITY_STEPS = (90, 80, 70, 60, 50)


class ImageConversionError(ValueError):
    """The upload isn't an image we can decode."""


def _flatten(im: Image.Image) -> Image.Image:
    """RGB copy, compositing any alpha channel onto white.

    JPEG has no alpha; converting straight to RGB turns transparent pixels
    black, which looks like a bug to the user.
    """
    if im.mode in ("RGBA", "LA") or (
        im.mode == "P" and "transparency" in im.info
    ):
        rgba = im.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, (255, 255, 255))
        canvas.paste(rgba, mask=rgba.split()[-1])
        return canvas
    return im.convert("RGB")


def to_instagram_jpeg(data: bytes) -> bytes:
    """Return ``data`` as a JPEG within Instagram's limits.

    Raises :class:`ImageConversionError` if the bytes aren't a decodable
    image (a video, a PDF, a corrupt upload).
    """
    try:
        with Image.open(io.BytesIO(data)) as opened:
            # Bake in the EXIF rotation phones set instead of rotating pixels.
            im = ImageOps.exif_transpose(opened) or opened
            im = _flatten(im)
            if max(im.size) > MAX_EDGE:
                im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)

            for quality in _QUALITY_STEPS:
                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=quality, optimize=True)
                out = buf.getvalue()
                if len(out) <= MAX_BYTES:
                    return out
            # Every quality step still too big — hand back the smallest we
            # made; Meta's own error is clearer than a synthetic one here.
            log.warning(
                "instagram.image.oversized bytes=%s after quality=%s",
                len(out),
                _QUALITY_STEPS[-1],
            )
            return out
    except UnidentifiedImageError as exc:
        raise ImageConversionError("not a decodable image") from exc
    except OSError as exc:  # truncated / malformed payloads
        raise ImageConversionError(str(exc)) from exc


__all__ = ["MAX_BYTES", "MAX_EDGE", "ImageConversionError", "to_instagram_jpeg"]
