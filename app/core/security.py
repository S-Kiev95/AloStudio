"""JWT + password hashing.

Chatwoot (Devise) uses BCrypt with cost 12 for `encrypted_password`. We use the
same algorithm and cost so that — if we ever migrate a real Chatwoot DB — user
password hashes carry over unchanged.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

BCRYPT_COST = 12


def hash_password(plaintext: str) -> str:
    salt = bcrypt.gensalt(rounds=BCRYPT_COST)
    return bcrypt.hashpw(plaintext.encode("utf-8"), salt).decode("utf-8")


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _encode(payload: dict[str, Any], ttl_seconds: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    body = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(body, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    return _encode(
        {"sub": str(subject), "typ": "access", **(extra or {})},
        settings.jwt_access_ttl_seconds,
    )


def create_refresh_token(subject: str | int) -> str:
    settings = get_settings()
    return _encode(
        {"sub": str(subject), "typ": "refresh"},
        settings.jwt_refresh_ttl_seconds,
    )


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
