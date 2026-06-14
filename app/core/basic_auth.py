"""HTTP Basic Auth verification for inbound webhooks.

Bandwidth (unlike the Meta channels, which sign with HMAC-SHA256) secures
its callbacks with **HTTP Basic Authentication**: you set a username +
password on the messaging application and Bandwidth includes them in the
``Authorization`` header of every callback. This verifies that header in
constant time.
"""

from __future__ import annotations

import base64
import binascii
import hmac

__all__ = ["verify_basic_auth"]


def verify_basic_auth(
    header: str | None, username: str, password: str
) -> bool:
    """Validate an ``Authorization: Basic <base64(user:pass)>`` header.

    Constant-time compares both the username and the password. Returns
    ``False`` on a missing/malformed header or empty expected creds (so
    callers fail closed when verification is enabled).
    """
    if not username or not password:
        return False
    if not header:
        return False
    scheme, _, encoded = header.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return False
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return False
    got_user, sep, got_pass = decoded.partition(":")
    if not sep:
        return False
    # Compare both halves in constant time (avoid short-circuit timing).
    user_ok = hmac.compare_digest(got_user, username)
    pass_ok = hmac.compare_digest(got_pass, password)
    return user_ok and pass_ok
