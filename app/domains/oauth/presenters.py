"""Wire shapes of the OAuth apps, approved apps and consent (contract in
``PLAN.oauth-apps.md``). Never includes a secret or token hash."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.accounts.models import Account
from app.domains.oauth.models import OAUTH_SCOPE_WRITE, OAuthApplication, OAuthToken
from app.domains.oauth.service import AuthorizeRequest, scope_allowed
from app.domains.users.models import ACCOUNT_USER_ROLE_ADMINISTRATOR, AccountUser


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def present_app(app: OAuthApplication, *, authorizations_count: int) -> dict[str, Any]:
    return {
        "id": app.id,
        "name": app.name,
        "client_id": app.client_id,
        "confidential": app.client_secret_hash is not None,
        "redirect_uris": app.redirect_uris or [],
        "authorizations_count": authorizations_count,
        "created_at": _iso(app.created_at),
    }


def present_app_with_secret(
    app: OAuthApplication, secret: str | None, *, authorizations_count: int
) -> dict[str, Any]:
    """Create and rotate: the secret appears here once and nowhere else."""
    body = present_app(app, authorizations_count=authorizations_count)
    if secret is not None:
        body["client_secret"] = secret
    return body


def present_authorization(app: OAuthApplication, tokens: list[OAuthToken]) -> dict[str, Any]:
    used = [t.last_used_at for t in tokens if t.last_used_at is not None]
    return {
        "app": {"id": app.id, "name": app.name, "client_id": app.client_id},
        "scope": (
            OAUTH_SCOPE_WRITE if any(t.scope == OAUTH_SCOPE_WRITE for t in tokens) else tokens[0].scope
        ),
        "authorized_at": _iso(min(t.created_at for t in tokens)),
        "last_used_at": _iso(max(used)) if used else None,
    }


def present_consent(
    request: AuthorizeRequest,
    *,
    owner: Account | None,
    memberships: list[tuple[Account, AccountUser]],
) -> dict[str, Any]:
    return {
        "app": {
            "name": request.app.name,
            "client_id": request.app.client_id,
            "owner_account_name": owner.name if owner is not None else None,
        },
        "scope": request.scope,
        "redirect_uri": request.redirect_uri,
        "accounts": [
            {
                "id": account.id,
                "name": account.name,
                "role": (
                    "administrator"
                    if membership.role == ACCOUNT_USER_ROLE_ADMINISTRATOR
                    else "agent"
                ),
                "can_grant": scope_allowed(request.scope, membership.role),
            }
            for account, membership in memberships
        ],
    }


__all__ = [
    "present_app",
    "present_app_with_secret",
    "present_authorization",
    "present_consent",
]
