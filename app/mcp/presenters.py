"""Wire-shape presenters for MCPToken.

Two surfaces:

  * :func:`present_token` — list/update/show. **No secret** in the body
    (admins see the secret only once at create/rotate time).
  * :func:`present_token_with_secret` — POST create / POST rotate. The
    secret appears in the response body **once** and is then unreachable
    via any other route.

This mirrors how every other "tokens" UI in the wild works (GitHub
personal access tokens, Stripe API keys, etc.) — show on create, never
again.
"""

from __future__ import annotations

from typing import Any

from app.mcp.models import MCPToken


def _iso(dt: Any) -> str | None:
    return None if dt is None else dt.isoformat()


def present_token(token: MCPToken) -> dict[str, Any]:
    return {
        "id": token.id,
        "account_id": token.account_id,
        "user_id": token.user_id,
        "name": token.name,
        "scope": token.scope,
        "last_used_at": _iso(token.last_used_at),
        "created_at": _iso(token.created_at),
    }


def present_token_with_secret(token: MCPToken) -> dict[str, Any]:
    body = present_token(token)
    body["token"] = token.token
    return body


__all__ = ["present_token", "present_token_with_secret"]
