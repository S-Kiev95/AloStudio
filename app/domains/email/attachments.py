"""Fetch a message's attachments so an outgoing reply can carry them.

Email is the one channel that needs the *bytes*. Instagram, Messenger and
WhatsApp are handed a signed URL and download it themselves; a mail server
gets a MIME part, so the file has to be pulled back out of the object
store first.

Every failure here is non-fatal by design. The reply is what the agent
wrote and the customer is waiting for it — losing an attachment is worse
than sending late, but far better than not sending at all, so a file that
cannot be fetched is logged and skipped and the mail goes.
"""

from __future__ import annotations

import logging
import mimetypes
from dataclasses import dataclass

import httpx

from app.core.storage import signed_read_url
from app.domains.conversations.models import Attachment

log = logging.getLogger(__name__)

_TIMEOUT = 20.0

# Most providers reject a message over ~25 MB once base64 expands it by a
# third. Skipping the file beats having the whole reply bounce.
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class FetchedFile:
    filename: str
    content: bytes
    maintype: str
    subtype: str


def _filename(attachment: Attachment) -> str:
    """A name the recipient can read, never a bare id.

    Falls back through the title the sender gave it, then the file type,
    so a downloaded file is at least identifiable as an image or a PDF.
    """
    title = (attachment.fallback_title or "").strip()
    if title:
        return title
    ext = (attachment.extension or "").lstrip(".")
    stem = attachment.file_type_str or "archivo"
    return f"{stem}-{attachment.id}.{ext}" if ext else f"{stem}-{attachment.id}"


def _content_type(filename: str, header: str | None) -> tuple[str, str]:
    """Prefer what the store served; fall back to the name, then bytes.

    ``application/octet-stream`` is the honest last resort: a mail client
    shows it as a download rather than guessing wrong and rendering
    something as the wrong kind of file.
    """
    candidate = (header or "").split(";")[0].strip()
    if not candidate or "/" not in candidate:
        candidate = mimetypes.guess_type(filename)[0] or ""
    if "/" not in candidate:
        return "application", "octet-stream"
    maintype, _, subtype = candidate.partition("/")
    return maintype or "application", subtype or "octet-stream"


async def fetch_attachments(
    attachments: list[Attachment],
) -> list[FetchedFile]:
    """Download what can be downloaded, in order, within the size budget."""
    out: list[FetchedFile] = []
    if not attachments:
        return out

    total = 0
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        for attachment in attachments:
            stored = (attachment.external_url or "").strip()
            if not stored:
                # A location attachment has coordinates, not a file.
                continue
            try:
                resp = await client.get(signed_read_url(stored))
                resp.raise_for_status()
            except (httpx.HTTPError, OSError) as exc:
                log.warning(
                    "email.attachment.fetch_failed attachment_id=%s error=%s",
                    attachment.id,
                    exc,
                )
                continue

            content = resp.content
            if len(content) > MAX_ATTACHMENT_BYTES:
                log.warning(
                    "email.attachment.too_large attachment_id=%s bytes=%s",
                    attachment.id,
                    len(content),
                )
                continue
            if total + len(content) > MAX_TOTAL_BYTES:
                log.warning(
                    "email.attachment.budget_exhausted attachment_id=%s",
                    attachment.id,
                )
                break

            total += len(content)
            name = _filename(attachment)
            maintype, subtype = _content_type(
                name, resp.headers.get("content-type")
            )
            out.append(
                FetchedFile(
                    filename=name,
                    content=content,
                    maintype=maintype,
                    subtype=subtype,
                )
            )
    return out


__all__ = [
    "MAX_ATTACHMENT_BYTES",
    "MAX_TOTAL_BYTES",
    "FetchedFile",
    "fetch_attachments",
]
