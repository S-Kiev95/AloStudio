"""Widget JWT token encode / decode.

Ported from:
  reference/chatwoot/app/services/widget/token_service.rb
  reference/chatwoot/app/services/base_token_service.rb

Chatwoot signs short-payload JWTs (``{source_id, inbox_id}``) with
the global ``secret_key_base`` and a 180-day default expiry. The
widget JS stores the token in ``localStorage`` and submits it on
every API request via the ``X-Auth-Token`` header.

We mirror the algorithm + payload shape so a Chatwoot-signed token
would round-trip through our decoder unchanged (modulo the secret
key, which is account-tenant data).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import get_settings

# Rails ``Widget::TokenService::DEFAULT_EXPIRY_DAYS`` — overridable via
# ``InstallationConfig.WIDGET_TOKEN_EXPIRY``. We don't ship the
# installation_configs table yet, so we hard-code the default — the
# settings hook lands with the admin-config phase.
DEFAULT_EXPIRY_DAYS = 180


def encode_widget_token(
    *, source_id: str, inbox_id: int, ttl_days: int = DEFAULT_EXPIRY_DAYS
) -> str:
    """Mirror ``Widget::TokenService#generate_token``.

    Payload shape is fixed at ``{source_id, inbox_id, iat, exp}``.
    Signed with ``HS256`` against the project secret key — Chatwoot
    uses HS256 by default.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "source_id": source_id,
        "inbox_id": inbox_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=ttl_days)).timestamp()),
    }
    return jwt.encode(
        payload, settings.secret_key, algorithm=settings.jwt_algorithm
    )


def decode_widget_token(token: str | None) -> dict[str, Any]:
    """Mirror ``BaseTokenService#decode_token``.

    Returns the decoded payload (``{source_id, inbox_id, iat, exp}``)
    on success. On any failure — bad signature, expired, malformed,
    nil — returns an empty dict, matching Rails' behaviour
    (``decode_token`` rescues ``JWT::DecodeError`` and returns ``{}``).
    """
    if not token:
        return {}
    settings = get_settings()
    try:
        return jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        return {}


__all__ = [
    "DEFAULT_EXPIRY_DAYS",
    "decode_widget_token",
    "encode_widget_token",
]
