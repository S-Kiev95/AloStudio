"""Token helpers that match Chatwoot's formats 1:1.

Rails' ``has_secure_token`` uses ``SecureRandom.base58(24)`` which produces a
24-char Base58 string. We mirror that so tokens issued by AloStudio are
indistinguishable from ones issued by a Rails Chatwoot install — important
when/if we ever migrate a real Chatwoot database.
"""

from __future__ import annotations

import secrets

# Base58 alphabet (same order as Ruby's SecureRandom.base58).
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58_token(length: int = 24) -> str:
    """Cryptographically strong Base58 token — Chatwoot-compatible."""
    return "".join(secrets.choice(_BASE58_ALPHABET) for _ in range(length))


def hex_token(nbytes: int = 32) -> str:
    """Hex token for devise-token-auth client/access headers."""
    return secrets.token_hex(nbytes)
