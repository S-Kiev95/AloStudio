"""devise-token-auth header contract.

Ports the minimum surface of the Ruby ``devise-token-auth`` gem we need for
byte-identical parity with Chatwoot on:

  * ``POST /api/v1/accounts`` (AuthHelper#send_auth_headers after signup)
  * ``POST /auth/sign_in`` (SessionsController render_create_success)
  * Any future request that needs to send or validate the rotating
    access-token / client / uid / expiry headers.

Design decisions matching reference/chatwoot/config/initializers/devise_token_auth.rb:

  change_headers_on_each_request = false
    The same ``access-token`` is reused across requests for a given
    ``client``. We only rotate on sign_in (new session) or password reset.

  token_lifespan = 2.months
    Session tokens expire 60 days after issuance.

  remove_tokens_after_password_reset = true
    Handled by ``invalidate_all_tokens()`` — callers call it from the
    password-reset flow.

  max_number_of_devices = 25
    After 25 concurrent clients per user, oldest tokens (by ``updated_at``)
    are evicted before a new one is stored.

Storage shape (``users.tokens`` JSONB column, one entry per client):

  {
    "<client_id>": {
      "token":      "<bcrypt hash of access-token>",
      "expiry":     <unix ts when token expires>,
      "updated_at": "<iso8601 of last rotation>"
    },
    ...
  }

Ruby source of truth:
  reference/chatwoot/app/controllers/concerns/auth_helper.rb
  (vendored) devise-token-auth-1.2.x app/models/concerns/tokens_serialization.rb
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt

# devise-token-auth tokens are bcrypt-hashed with Devise's default cost
# (DEFAULT_STRETCHES = 11 in Devise 4.9). The *password* cost is 12 set by
# Chatwoot separately; do not conflate them.
TOKEN_BCRYPT_COST = 10
TOKEN_LIFESPAN = timedelta(days=60)  # `token_lifespan = 2.months`
MAX_DEVICES_PER_USER = 25  # `max_number_of_devices = 25`

# DeviseTokenAuth.headers_names — the wire header names. Lowercase because
# HTTP header names are case-insensitive, but clients grep for these exactly.
HEADER_ACCESS_TOKEN = "access-token"
HEADER_TOKEN_TYPE = "token-type"
HEADER_CLIENT = "client"
HEADER_EXPIRY = "expiry"
HEADER_UID = "uid"


@dataclass(slots=True)
class AuthHeaders:
    """The tuple returned by ``User#create_new_auth_token``."""

    access_token: str
    client: str
    uid: str
    expiry: int  # seconds since epoch (not ms — matches Ruby)

    def as_response_headers(self) -> dict[str, str]:
        """Return headers ready to attach to a FastAPI Response."""
        return {
            HEADER_ACCESS_TOKEN: self.access_token,
            HEADER_TOKEN_TYPE: "Bearer",
            HEADER_CLIENT: self.client,
            HEADER_EXPIRY: str(self.expiry),
            HEADER_UID: self.uid,
        }


def _urlsafe_token(length: int = 22) -> str:
    """``SecureRandom.urlsafe_base64(nil, false)`` → 22-char URL-safe string.

    Ruby's default with no length arg and padding=false produces a 22-char
    alphabet-``[A-Za-z0-9_-]`` string (16 random bytes base64url-encoded,
    stripped of trailing '='). ``secrets.token_urlsafe(16)`` is equivalent.
    """
    # token_urlsafe(nbytes) = 4*ceil(nbytes/3) chars before padding; 16 bytes
    # → 24 chars, 22 after stripping '=='. Python's token_urlsafe already
    # omits padding, so just slice.
    raw = secrets.token_urlsafe(16)
    return raw[:length] if len(raw) > length else raw


def _hash_token(token: str) -> str:
    """BCrypt-hash a raw token for at-rest storage in ``users.tokens``."""
    salt = bcrypt.gensalt(rounds=TOKEN_BCRYPT_COST)
    return bcrypt.hashpw(token.encode("utf-8"), salt).decode("utf-8")


def _verify_token(token: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(token.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _prune_old_devices(tokens: dict[str, Any]) -> dict[str, Any]:
    """Drop the oldest entries until we're under :data:`MAX_DEVICES_PER_USER`.

    Ruby does this on every write via ``max_client_prune!``. Ordering is by
    ``updated_at`` ascending; ties are broken by client id (stable across
    runs).
    """
    if len(tokens) <= MAX_DEVICES_PER_USER - 1:
        return tokens

    def _sort_key(item: tuple[str, Any]) -> tuple[str, str]:
        _client, data = item
        return (data.get("updated_at", ""), _client)

    ordered = sorted(tokens.items(), key=_sort_key)
    keep = ordered[-(MAX_DEVICES_PER_USER - 1) :]
    return dict(keep)


def create_new_auth_token(
    user_tokens: dict[str, Any] | None,
    uid: str,
    *,
    client: str | None = None,
) -> tuple[AuthHeaders, dict[str, Any]]:
    """Mint a fresh access-token/client/expiry triple and return the new
    ``user.tokens`` dict to persist.

    If ``client`` is given we rotate an existing entry (keeping the same
    client id) — this matches the Ruby flow when ``change_headers_on_each_request``
    is false but we still want to refresh the token (e.g. on sign_in).

    The *raw* token is only returned here; the column stores the BCrypt
    hash. That's how devise-token-auth prevents token theft via a DB leak.
    """
    tokens = dict(user_tokens or {})
    tokens = _prune_old_devices(tokens)

    client_id = client or _urlsafe_token()
    raw_token = _urlsafe_token()
    expiry = int((_now_utc() + TOKEN_LIFESPAN).timestamp())

    tokens[client_id] = {
        "token": _hash_token(raw_token),
        "expiry": expiry,
        "updated_at": _now_utc().isoformat(),
    }

    return (
        AuthHeaders(
            access_token=raw_token,
            client=client_id,
            uid=uid,
            expiry=expiry,
        ),
        tokens,
    )


def verify_auth_token(
    user_tokens: dict[str, Any] | None,
    *,
    client: str,
    access_token: str,
) -> bool:
    """Validate an incoming ``(client, access-token)`` pair.

    Returns ``True`` if the client id exists, the BCrypt compare succeeds,
    and the entry has not expired.
    """
    tokens = user_tokens or {}
    entry = tokens.get(client)
    if not entry:
        return False

    expiry = int(entry.get("expiry") or 0)
    if expiry < int(_now_utc().timestamp()):
        return False

    hashed = entry.get("token")
    if not hashed or not isinstance(hashed, str):
        return False

    return _verify_token(access_token, hashed)


def invalidate_all_tokens(user_tokens: dict[str, Any] | None) -> dict[str, Any]:
    """Drop every session — used on password reset.

    Returns an empty dict so the caller writes it back to ``user.tokens``.
    """
    return {}
