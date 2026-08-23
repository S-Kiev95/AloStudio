"""HMAC-signed, expiring links for bytes Meta has to fetch itself.

Instagram pulls both DM attachments and post media from a URL on its own
side, so those links can't be session-gated the way the dashboard's media
proxy is. They're signed against ``secret_key`` and expire instead — the
same trade a pre-signed S3 URL makes.

The payload is opaque to this module (an attachment id, an object key…);
callers namespace it so a signature minted for one resource can never be
replayed against another.
"""

from __future__ import annotations

import hashlib
import hmac
import time

from app.core.config import get_settings

# 32 hex chars of SHA-256 — 128 bits, far past brute-force for a link that
# also expires, and short enough to keep URLs readable.
_SIG_LENGTH = 32


def sign(payload: str, expires_at: int) -> str:
    """Signature binding ``payload`` to its expiry."""
    secret = get_settings().secret_key.encode()
    message = f"{payload}:{expires_at}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()[:_SIG_LENGTH]


def is_valid(payload: str, expires_at: int, signature: str) -> bool:
    """True when ``signature`` matches and hasn't expired.

    Constant-time compare — a timing oracle here would leak the secret one
    byte at a time.
    """
    if int(time.time()) > expires_at:
        return False
    return hmac.compare_digest(sign(payload, expires_at), signature)


def expiry_from_now(ttl_seconds: int) -> int:
    return int(time.time()) + ttl_seconds


# ---------------------------------------------------------------------------
# Links that must outlive any expiry
# ---------------------------------------------------------------------------
def sign_permanent(payload: str) -> str:
    """Signature over ``payload`` alone, with no expiry.

    For bytes embedded in something that keeps its own copy for years: an
    email sits in an inbox long after any TTL we would have picked, and a
    letterhead whose logo 404s next month is worse than one that was
    never uploaded. The signature still makes the URL unguessable, which
    is what stops enumeration; expiry was never what protected it.

    Namespaced separately from :func:`sign` so a permanent signature can
    never be replayed as an expiring one, or the reverse.
    """
    secret = get_settings().secret_key.encode()
    message = f"permanent:{payload}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()[:_SIG_LENGTH]


def is_valid_permanent(payload: str, signature: str) -> bool:
    return hmac.compare_digest(sign_permanent(payload), signature)


__all__ = [
    "expiry_from_now",
    "is_valid",
    "is_valid_permanent",
    "sign",
    "sign_permanent",
]
