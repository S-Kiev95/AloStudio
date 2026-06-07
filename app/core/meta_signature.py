"""Shared HMAC verification for Meta webhook payloads.

Meta (Instagram / WhatsApp Cloud / Facebook Messenger) signs every
webhook POST with ``X-Hub-Signature-256: sha256=<hmac>`` where the HMAC
is SHA-256 of the **raw request body** keyed by the Meta app secret.

This is the single place that primitive lives so the per-channel
receivers (instagram / whatsapp / facebook) verify identically. The
GET ``hub.verify_token`` handshake is a *separate*, weaker check that
only gates subscription setup — it does NOT authenticate each POST,
which is why per-POST signature verification matters for any
internet-exposed deployment.
"""

from __future__ import annotations

import hashlib
import hmac

__all__ = ["verify_sha256_signature"]


def verify_sha256_signature(
    raw_body: bytes, header: str | None, secret: str
) -> bool:
    """Validate ``X-Hub-Signature-256: sha256=<hex>``.

    HMAC-SHA256 of the raw request body keyed by ``secret``, compared in
    constant time. Returns ``False`` on a missing/malformed header or an
    empty secret (callers should fail closed when verification is
    enabled but the secret isn't configured).
    """
    if not secret:
        return False
    if not header or not header.startswith("sha256="):
        return False
    provided = header.split("=", 1)[1]
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)
