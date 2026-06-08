"""X-Twilio-Signature verification.

Twilio signs every webhook with ``X-Twilio-Signature``: the base64 of
HMAC-SHA1 (keyed on the account ``auth_token``) over a signing string
built from the **exact request URL** Twilio POSTed to, immediately
followed by each POST param as ``key + value``, the params sorted by
key. See https://www.twilio.com/docs/usage/security#validating-requests.

Two correctness traps this handles:
  * **URL must match what Twilio signed** — behind a reverse proxy the
    app sees an internal scheme/host, so the caller passes the
    externally-visible URL (reconstructed from ``X-Forwarded-Proto`` /
    ``X-Forwarded-Host``).
  * **Param order** — sorted by key, value appended with no separator.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Mapping

__all__ = ["compute_twilio_signature", "verify_twilio_signature"]


def compute_twilio_signature(
    auth_token: str, url: str, params: Mapping[str, object]
) -> str:
    """Return the expected ``X-Twilio-Signature`` value (base64 string)."""
    signing = url + "".join(
        f"{key}{params[key]}" for key in sorted(params)
    )
    digest = hmac.new(
        auth_token.encode("utf-8"),
        signing.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def verify_twilio_signature(
    auth_token: str | None,
    url: str,
    params: Mapping[str, object],
    header: str | None,
) -> bool:
    """Constant-time check of the inbound ``X-Twilio-Signature`` header.

    Returns ``False`` on a missing header or empty ``auth_token`` so the
    caller fails closed when verification is enabled.
    """
    if not auth_token or not header:
        return False
    expected = compute_twilio_signature(auth_token, url, params)
    return hmac.compare_digest(expected, header)
