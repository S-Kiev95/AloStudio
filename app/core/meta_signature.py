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

__all__ = ["verify_against_any_secret", "verify_sha256_signature"]


def verify_against_any_secret(
    raw_body: bytes, header: str | None, secrets: tuple[str, ...]
) -> bool:
    """True when the signature validates against **any** of ``secrets``.

    One endpoint can receive events from more than one Meta app. The
    Instagram webhook is the case in point: an account connected through
    Instagram Login is subscribed by the *Instagram* app and signed with
    its secret, while one connected through Facebook Login is signed with
    the Facebook app's. Verifying against a single secret rejects half
    the traffic — with a 401, which Meta eventually reads as a broken
    endpoint and disables.

    Empty secrets are skipped, so an unconfigured one can never make a
    forged payload pass; if every candidate is empty this returns False
    and the caller fails closed.
    """
    return any(
        verify_sha256_signature(raw_body, header, secret)
        for secret in secrets
        if secret
    )


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
