"""Attachment upload presigning — shared by the dashboard + widget.

Builds the account-namespaced object key and the pre-signed PUT URL a
client uploads directly to, plus the stable ``file_url`` to persist as the
attachment's ``external_url``. Kept channel-agnostic so both the
authenticated dashboard (``account_context``) and the public widget
(``widget_context``) surfaces reuse the exact same shape.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from app.core.storage import object_url, presigned_put_url

UPLOAD_TTL_SECONDS = 900
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str | None) -> str:
    """Strip any path components + collapse unsafe chars so the key can't
    escape the account prefix."""
    base = (name or "file").strip().rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    cleaned = _UNSAFE.sub("-", base).strip("-.") or "file"
    return cleaned[:120]


def presign_upload(account_id: int, filename: str | None) -> dict[str, Any]:
    """Return ``{key, upload_url, file_url, expires_in}`` for a fresh
    attachment upload, namespaced under ``account_id``."""
    key = (
        f"accounts/{account_id}/uploads/"
        f"{uuid4().hex}/{safe_filename(filename)}"
    )
    return {
        "key": key,
        "upload_url": presigned_put_url(key, expires=UPLOAD_TTL_SECONDS),
        "file_url": object_url(key),
        "expires_in": UPLOAD_TTL_SECONDS,
    }


__all__ = ["UPLOAD_TTL_SECONDS", "presign_upload", "safe_filename"]
