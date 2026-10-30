"""OAuth 2.0 authorization server: registered apps, the user's consent and
the tokens.

Authorization code grant with PKCE (S256, required for public apps;
RFC 6749, RFC 7636) and rotating refresh tokens, token revocation
(RFC 7009) and the discovery documents (RFC 8414, RFC 9728). An access
token works on the MCP server (``app.mcp.service.resolve_token``) with the
scope the user granted, capped by their role in the account at the time of
use: a demoted administrator's tokens stop writing right away.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException
from app.domains.accounts.models import Account
from app.domains.oauth.models import (
    OAUTH_SCOPE_READ,
    OAUTH_SCOPE_WRITE,
    OAuthApplication,
    OAuthAuthorizationCode,
    OAuthToken,
)
from app.domains.users.models import ACCOUNT_USER_ROLE_ADMINISTRATOR, AccountUser, User

CLIENT_ID_PREFIX = "alo_app_"
CLIENT_SECRET_PREFIX = "alo_secret_"
CODE_PREFIX = "alo_code_"
ACCESS_TOKEN_PREFIX = "alo_at_"
REFRESH_TOKEN_PREFIX = "alo_rt_"

CODE_TTL = timedelta(minutes=10)
ACCESS_TOKEN_TTL = timedelta(hours=1)
REFRESH_TOKEN_TTL = timedelta(days=30)
NAME_MAX_LENGTH = 80
MAX_REDIRECT_URIS = 10
_LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")


class OAuthError(Exception):
    """An error of the OAuth protocol endpoints, answered as
    ``{"error", "error_description"}`` (RFC 6749 §5.2)."""

    def __init__(self, error: str, description: str, *, status_code: int = 400) -> None:
        super().__init__(description)
        self.error = error
        self.description = description
        self.status_code = status_code


class RedirectWithError(Exception):
    """An authorization request that is wrong but whose redirect URI is
    valid: the error goes back to the app, not to the user."""

    def __init__(self, redirect_to: str) -> None:
        super().__init__(redirect_to)
        self.redirect_to = redirect_to


@dataclass(slots=True)
class AuthorizeRequest:
    """A validated authorization request."""

    app: OAuthApplication
    redirect_uri: str
    scope: str
    state: str | None
    code_challenge: str | None


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _new_secret(prefix: str) -> str:
    return f"{prefix}{secrets.token_urlsafe(32)}"


def _now() -> datetime:
    return datetime.now(UTC)


def _unprocessable(message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=422, detail={"message": message})


def issuer() -> str:
    """The public base URL: the consent page and every OAuth endpoint hang
    from it (the reverse proxy sends ``/oauth/authorize`` to the panel and
    the rest to the API)."""
    return get_settings().app_base_url.rstrip("/")


def endpoints() -> dict[str, str]:
    base = issuer()
    return {
        "authorization": f"{base}/oauth/authorize",
        "token": f"{base}/oauth/token",
        "revocation": f"{base}/oauth/revoke",
        "metadata": f"{base}/.well-known/oauth-authorization-server",
        "mcp": f"{base}/mcp",
    }


def authorization_server_metadata() -> dict[str, Any]:
    """RFC 8414."""
    urls = endpoints()
    client_auth = ["client_secret_basic", "client_secret_post", "none"]
    return {
        "issuer": issuer(),
        "authorization_endpoint": urls["authorization"],
        "token_endpoint": urls["token"],
        "revocation_endpoint": urls["revocation"],
        "scopes_supported": [OAUTH_SCOPE_READ, OAUTH_SCOPE_WRITE],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": client_auth,
        "revocation_endpoint_auth_methods_supported": client_auth,
    }


def protected_resource_metadata() -> dict[str, Any]:
    """RFC 9728: tells an MCP client which server issues tokens for /mcp."""
    return {
        "resource": endpoints()["mcp"],
        "authorization_servers": [issuer()],
        "scopes_supported": [OAUTH_SCOPE_READ, OAUTH_SCOPE_WRITE],
        "bearer_methods_supported": ["header"],
    }


def protected_resource_metadata_url() -> str:
    return f"{issuer()}/.well-known/oauth-protected-resource/mcp"


def parse_scope(raw: str | None) -> str | None:
    """``read`` by default; ``write`` if asked (it includes read). ``None``
    for a scope we do not offer."""
    words = set((raw or "").split())
    if not words <= {OAUTH_SCOPE_READ, OAUTH_SCOPE_WRITE}:
        return None
    return OAUTH_SCOPE_WRITE if OAUTH_SCOPE_WRITE in words else OAUTH_SCOPE_READ


def scope_allowed(scope: str, role: int) -> bool:
    """Only administrators can let an app write."""
    return scope == OAUTH_SCOPE_READ or role == ACCOUNT_USER_ROLE_ADMINISTRATOR


def with_params(uri: str, **params: str | None) -> str:
    """``uri`` with ``params`` added to its query string (``None`` skipped)."""
    parts = urlsplit(uri)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query += [(k, v) for k, v in params.items() if v is not None]
    return urlunsplit(parts._replace(query=urlencode(query)))


# ---------------------------------------------------------------------------
# Apps (an account's registered clients)
# ---------------------------------------------------------------------------
def _clean_name(raw: str) -> str:
    name = " ".join(raw.split())
    if not 1 <= len(name) <= NAME_MAX_LENGTH:
        raise _unprocessable(f"El nombre tiene que tener entre 1 y {NAME_MAX_LENGTH} caracteres.")
    return name


def _clean_redirect_uris(raw: list[str]) -> list[str]:
    uris = list(dict.fromkeys(u.strip() for u in raw if u.strip()))
    if not 1 <= len(uris) <= MAX_REDIRECT_URIS:
        raise _unprocessable(f"Cargá entre 1 y {MAX_REDIRECT_URIS} URL de retorno.")
    for uri in uris:
        parts = urlsplit(uri)
        if "#" in uri:
            raise _unprocessable(f"{uri}: una URL de retorno no puede tener #.")
        secure = parts.scheme == "https" and bool(parts.hostname)
        loopback = parts.scheme == "http" and parts.hostname in _LOOPBACK_HOSTS
        if not (secure or loopback):
            raise _unprocessable(
                f"{uri}: tiene que empezar con https:// (o http://localhost para desarrollo)."
            )
    return uris


async def list_apps(session: AsyncSession, *, account_id: int) -> list[OAuthApplication]:
    return list(
        (
            await session.exec(
                select(OAuthApplication)
                .where(OAuthApplication.account_id == account_id)
                .order_by(OAuthApplication.id)  # type: ignore[arg-type]
            )
        ).all()
    )


async def get_app(
    session: AsyncSession, *, account_id: int, app_id: int
) -> OAuthApplication:
    app = (
        await session.exec(
            select(OAuthApplication).where(
                OAuthApplication.id == app_id,
                OAuthApplication.account_id == account_id,
            )
        )
    ).first()
    if app is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"message": "No se encontró la app."}
        )
    return app


async def authorization_counts(session: AsyncSession, app_ids: list[int]) -> dict[int, int]:
    """How many (user, account) pairs hold a live grant of each app."""
    if not app_ids:
        return {}
    rows = (
        await session.exec(
            select(OAuthToken.application_id, OAuthToken.account_id, OAuthToken.user_id)
            .where(
                OAuthToken.application_id.in_(app_ids),  # type: ignore[attr-defined]
                OAuthToken.revoked_at.is_(None),  # type: ignore[union-attr]
                OAuthToken.refresh_expires_at > _now(),  # type: ignore[operator]
            )
            .distinct()
        )
    ).all()
    counts: dict[int, int] = {}
    for application_id, _account_id, _user_id in rows:
        counts[application_id] = counts.get(application_id, 0) + 1
    return counts


async def create_app(
    session: AsyncSession,
    *,
    account_id: int,
    created_by_id: int | None,
    name: str,
    redirect_uris: list[str],
    confidential: bool,
) -> tuple[OAuthApplication, str | None]:
    """The new app and its secret (``None`` for a public app). The secret
    is not stored: this is the only time anyone sees it."""
    secret = _new_secret(CLIENT_SECRET_PREFIX) if confidential else None
    app = OAuthApplication(
        account_id=account_id,
        created_by_id=created_by_id,
        name=_clean_name(name),
        client_id=f"{CLIENT_ID_PREFIX}{secrets.token_hex(12)}",
        client_secret_hash=_hash(secret) if secret else None,
        redirect_uris=_clean_redirect_uris(redirect_uris),
    )
    session.add(app)
    await session.flush()
    await session.refresh(app)
    return app, secret


async def update_app(
    session: AsyncSession,
    app: OAuthApplication,
    *,
    name: str | None,
    redirect_uris: list[str] | None,
) -> OAuthApplication:
    if name is not None:
        app.name = _clean_name(name)
    if redirect_uris is not None:
        app.redirect_uris = _clean_redirect_uris(redirect_uris)
    session.add(app)
    await session.flush()
    await session.refresh(app)
    return app


async def rotate_secret(session: AsyncSession, app: OAuthApplication) -> str:
    if app.client_secret_hash is None:
        raise _unprocessable("Una app pública no tiene secreto: usa PKCE.")
    secret = _new_secret(CLIENT_SECRET_PREFIX)
    app.client_secret_hash = _hash(secret)
    session.add(app)
    await session.flush()
    await session.refresh(app)
    return secret


async def delete_app(session: AsyncSession, app: OAuthApplication) -> None:
    """Its codes and tokens go with it (ON DELETE CASCADE)."""
    await session.delete(app)
    await session.flush()


# ---------------------------------------------------------------------------
# Approved apps (a user's live grants in an account)
# ---------------------------------------------------------------------------
async def live_grants(
    session: AsyncSession, *, account_id: int, user_id: int
) -> list[tuple[OAuthApplication, list[OAuthToken]]]:
    tokens = (
        await session.exec(
            select(OAuthToken)
            .where(
                OAuthToken.account_id == account_id,
                OAuthToken.user_id == user_id,
                OAuthToken.revoked_at.is_(None),  # type: ignore[union-attr]
                OAuthToken.refresh_expires_at > _now(),  # type: ignore[operator]
            )
            .order_by(OAuthToken.id)  # type: ignore[arg-type]
        )
    ).all()
    by_app: dict[int, list[OAuthToken]] = {}
    for token in tokens:
        by_app.setdefault(token.application_id, []).append(token)
    if not by_app:
        return []
    apps = (
        await session.exec(
            select(OAuthApplication).where(OAuthApplication.id.in_(list(by_app)))  # type: ignore[union-attr]
        )
    ).all()
    return [(app, by_app[app.id]) for app in sorted(apps, key=lambda a: a.id)]  # type: ignore[index, arg-type, return-value]


async def revoke_grant(
    session: AsyncSession, *, application_id: int, account_id: int, user_id: int
) -> int:
    """Revoke every live token of the app for this user in this account.
    Returns how many were revoked."""
    result = await session.exec(  # type: ignore[call-overload]
        update(OAuthToken)
        .where(
            OAuthToken.application_id == application_id,  # type: ignore[arg-type]
            OAuthToken.account_id == account_id,  # type: ignore[arg-type]
            OAuthToken.user_id == user_id,  # type: ignore[arg-type]
            OAuthToken.revoked_at.is_(None),  # type: ignore[union-attr]
        )
        .values(revoked_at=_now())
    )
    return result.rowcount


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------
async def app_by_client_id(session: AsyncSession, client_id: str | None) -> OAuthApplication | None:
    if not client_id:
        return None
    return (
        await session.exec(select(OAuthApplication).where(OAuthApplication.client_id == client_id))
    ).first()


async def validate_authorize(
    session: AsyncSession, params: dict[str, Any]
) -> AuthorizeRequest:
    """Check an authorization request. A bad app or redirect URI is told to
    the user (never redirect to an unregistered URI); anything else goes back
    to the app as :class:`RedirectWithError`."""
    app = await app_by_client_id(session, params.get("client_id"))
    if app is None:
        raise ChatwootHTTPException(
            status_code=400, detail={"message": "La app que pide acceso no existe."}
        )
    redirect_uri = params.get("redirect_uri")
    if not redirect_uri:
        if len(app.redirect_uris) != 1:
            raise ChatwootHTTPException(
                status_code=400, detail={"message": "Falta la URL de retorno de la app."}
            )
        redirect_uri = app.redirect_uris[0]
    elif redirect_uri not in app.redirect_uris:
        raise ChatwootHTTPException(
            status_code=400,
            detail={"message": "La URL de retorno no está registrada para esta app."},
        )
    state = params.get("state")

    def back(error: str, description: str) -> RedirectWithError:
        return RedirectWithError(
            with_params(redirect_uri, error=error, error_description=description, state=state)
        )

    if params.get("response_type") != "code":
        raise back("unsupported_response_type", "Solo se acepta response_type=code.")
    scope = parse_scope(params.get("scope"))
    if scope is None:
        raise back("invalid_scope", "Los permisos posibles son read y write.")
    challenge = params.get("code_challenge")
    if challenge:
        if params.get("code_challenge_method") != "S256":
            raise back("invalid_request", "Solo se acepta code_challenge_method=S256.")
        if not 43 <= len(challenge) <= 128:
            raise back("invalid_request", "code_challenge no es válido.")
    elif app.client_secret_hash is None:
        raise back("invalid_request", "Una app pública tiene que usar PKCE (code_challenge).")
    return AuthorizeRequest(
        app=app,
        redirect_uri=redirect_uri,
        scope=scope,
        state=state,
        code_challenge=challenge or None,
    )


async def memberships(
    session: AsyncSession, *, user_id: int
) -> list[tuple[Account, AccountUser]]:
    rows = (
        await session.exec(
            select(Account, AccountUser)
            .join(AccountUser, AccountUser.account_id == Account.id)  # type: ignore[arg-type]
            .where(AccountUser.user_id == user_id)
            .order_by(Account.id)  # type: ignore[arg-type]
        )
    ).all()
    return list(rows)  # type: ignore[arg-type]


async def _membership(session: AsyncSession, *, account_id: int, user_id: int) -> AccountUser | None:
    return (
        await session.exec(
            select(AccountUser).where(
                AccountUser.account_id == account_id,
                AccountUser.user_id == user_id,
            )
        )
    ).first()


def denied_redirect(request: AuthorizeRequest) -> str:
    return with_params(request.redirect_uri, error="access_denied", state=request.state)


async def approve(
    session: AsyncSession, user: User, request: AuthorizeRequest, *, account_id: int | None
) -> str:
    """The user said yes on ``account_id``: the redirect carrying the code."""
    membership = (
        await _membership(session, account_id=account_id, user_id=user.id)  # type: ignore[arg-type]
        if account_id is not None
        else None
    )
    if membership is None:
        raise ChatwootHTTPException(
            status_code=403, detail={"message": "Elegí una de tus cuentas."}
        )
    if not scope_allowed(request.scope, membership.role):
        raise ChatwootHTTPException(
            status_code=403,
            detail={"message": "Tu rol en esa cuenta no permite dar acceso de escritura."},
        )
    code = _new_secret(CODE_PREFIX)
    session.add(
        OAuthAuthorizationCode(
            application_id=request.app.id,  # type: ignore[arg-type]
            account_id=account_id,
            user_id=user.id,  # type: ignore[arg-type]
            code_hash=_hash(code),
            redirect_uri=request.redirect_uri,
            scope=request.scope,
            code_challenge=request.code_challenge,
            expires_at=_now() + CODE_TTL,
        )
    )
    await session.flush()
    return with_params(request.redirect_uri, code=code, state=request.state)


# ---------------------------------------------------------------------------
# Token endpoint
# ---------------------------------------------------------------------------
async def authenticate_client(
    session: AsyncSession, *, client_id: str | None, client_secret: str | None
) -> OAuthApplication:
    """A confidential app proves itself with its secret; a public one only
    names itself (PKCE protects its codes)."""
    app = await app_by_client_id(session, client_id)
    if app is None:
        raise OAuthError("invalid_client", "Cliente desconocido.", status_code=401)
    if app.client_secret_hash is None:
        if client_secret:
            raise OAuthError("invalid_client", "Esta app es pública: no tiene secreto.", status_code=401)
        return app
    if not client_secret or not hmac.compare_digest(_hash(client_secret), app.client_secret_hash):
        raise OAuthError("invalid_client", "El secreto de la app no es válido.", status_code=401)
    return app


def _pkce_matches(verifier: str, challenge: str) -> bool:
    digest = hashlib.sha256(verifier.encode("ascii", errors="ignore")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return hmac.compare_digest(expected, challenge)


async def _issue(
    session: AsyncSession, *, application_id: int, account_id: int, user_id: int, scope: str
) -> dict[str, Any]:
    access = _new_secret(ACCESS_TOKEN_PREFIX)
    refresh = _new_secret(REFRESH_TOKEN_PREFIX)
    now = _now()
    session.add(
        OAuthToken(
            application_id=application_id,
            account_id=account_id,
            user_id=user_id,
            scope=scope,
            access_token_hash=_hash(access),
            access_expires_at=now + ACCESS_TOKEN_TTL,
            refresh_token_hash=_hash(refresh),
            refresh_expires_at=now + REFRESH_TOKEN_TTL,
        )
    )
    await session.flush()
    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": int(ACCESS_TOKEN_TTL.total_seconds()),
        "refresh_token": refresh,
        "scope": scope,
    }


async def exchange_code(
    session: AsyncSession,
    app: OAuthApplication,
    *,
    code: str | None,
    redirect_uri: str | None,
    code_verifier: str | None,
) -> dict[str, Any]:
    row = (
        await session.exec(
            select(OAuthAuthorizationCode).where(
                OAuthAuthorizationCode.code_hash == _hash(code or ""),
                OAuthAuthorizationCode.application_id == app.id,
            )
        )
    ).first()
    if row is None:
        raise OAuthError("invalid_grant", "El código no es válido.")
    if row.used_at is not None:
        # A code used twice means it leaked: what it bought is cut off too.
        await revoke_grant(
            session, application_id=app.id, account_id=row.account_id, user_id=row.user_id  # type: ignore[arg-type]
        )
        raise OAuthError("invalid_grant", "El código ya se usó.")
    if row.expires_at <= _now():
        raise OAuthError("invalid_grant", "El código venció.")
    if (redirect_uri or row.redirect_uri) != row.redirect_uri:
        raise OAuthError("invalid_grant", "La URL de retorno no coincide con la de la autorización.")
    if row.code_challenge is not None:
        if not code_verifier or not _pkce_matches(code_verifier, row.code_challenge):
            raise OAuthError("invalid_grant", "code_verifier no coincide con el code_challenge.")
    # Single use even against two simultaneous requests.
    claimed = await session.exec(  # type: ignore[call-overload]
        update(OAuthAuthorizationCode)
        .where(
            OAuthAuthorizationCode.id == row.id,  # type: ignore[arg-type]
            OAuthAuthorizationCode.used_at.is_(None),  # type: ignore[union-attr]
        )
        .values(used_at=_now())
    )
    if claimed.rowcount != 1:
        raise OAuthError("invalid_grant", "El código ya se usó.")
    if await _membership(session, account_id=row.account_id, user_id=row.user_id) is None:
        raise OAuthError("invalid_grant", "El usuario ya no es parte de la cuenta.")
    return await _issue(
        session,
        application_id=app.id,  # type: ignore[arg-type]
        account_id=row.account_id,
        user_id=row.user_id,
        scope=row.scope,
    )


async def refresh(
    session: AsyncSession, app: OAuthApplication, *, refresh_token: str | None, scope: str | None
) -> dict[str, Any]:
    row = (
        await session.exec(
            select(OAuthToken).where(
                OAuthToken.refresh_token_hash == _hash(refresh_token or ""),
                OAuthToken.application_id == app.id,
            )
        )
    ).first()
    if row is None:
        raise OAuthError("invalid_grant", "El refresh token no es válido.")
    if row.revoked_at is not None:
        # A rotated refresh token came back: someone kept a copy.
        await revoke_grant(
            session, application_id=app.id, account_id=row.account_id, user_id=row.user_id  # type: ignore[arg-type]
        )
        raise OAuthError("invalid_grant", "El refresh token ya se usó o fue revocado.")
    if row.refresh_expires_at <= _now():
        raise OAuthError("invalid_grant", "El refresh token venció.")
    granted = row.scope
    if scope is not None:
        asked = parse_scope(scope)
        if asked is None or (asked == OAUTH_SCOPE_WRITE and granted == OAUTH_SCOPE_READ):
            raise OAuthError("invalid_scope", "No se pueden pedir más permisos que los autorizados.")
        granted = asked
    if await _membership(session, account_id=row.account_id, user_id=row.user_id) is None:
        raise OAuthError("invalid_grant", "El usuario ya no es parte de la cuenta.")
    rotated = await session.exec(  # type: ignore[call-overload]
        update(OAuthToken)
        .where(OAuthToken.id == row.id, OAuthToken.revoked_at.is_(None))  # type: ignore[arg-type, union-attr]
        .values(revoked_at=_now())
    )
    if rotated.rowcount != 1:
        raise OAuthError("invalid_grant", "El refresh token ya se usó o fue revocado.")
    return await _issue(
        session,
        application_id=app.id,  # type: ignore[arg-type]
        account_id=row.account_id,
        user_id=row.user_id,
        scope=granted,
    )


async def revoke_token(session: AsyncSession, app: OAuthApplication, *, token: str | None) -> None:
    """RFC 7009: revoke an access or refresh token of this app. An unknown
    token is not an error."""
    digest = _hash(token or "")
    await session.exec(  # type: ignore[call-overload]
        update(OAuthToken)
        .where(
            OAuthToken.application_id == app.id,  # type: ignore[arg-type]
            (OAuthToken.access_token_hash == digest) | (OAuthToken.refresh_token_hash == digest),  # type: ignore[arg-type, operator]
            OAuthToken.revoked_at.is_(None),  # type: ignore[union-attr]
        )
        .values(revoked_at=_now())
    )


# ---------------------------------------------------------------------------
# Using a token (MCP)
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class AccessGrant:
    account: Account
    user: User
    scope: str


async def resolve_access_token(session: AsyncSession, token: str) -> AccessGrant | None:
    """The account, user and effective scope behind a live access token, or
    ``None``. The scope is capped by the user's current role."""
    row = (
        await session.exec(
            select(OAuthToken).where(OAuthToken.access_token_hash == _hash(token))
        )
    ).first()
    now = _now()
    if row is None or row.revoked_at is not None or row.access_expires_at <= now:
        return None
    membership = await _membership(session, account_id=row.account_id, user_id=row.user_id)
    account = await session.get(Account, row.account_id)
    user = await session.get(User, row.user_id)
    if membership is None or account is None or user is None:
        return None
    row.last_used_at = now
    session.add(row)
    scope = row.scope if scope_allowed(row.scope, membership.role) else OAUTH_SCOPE_READ
    return AccessGrant(account=account, user=user, scope=scope)


__all__ = [
    "ACCESS_TOKEN_PREFIX",
    "AccessGrant",
    "AuthorizeRequest",
    "OAuthError",
    "RedirectWithError",
    "app_by_client_id",
    "approve",
    "authenticate_client",
    "authorization_counts",
    "authorization_server_metadata",
    "create_app",
    "delete_app",
    "denied_redirect",
    "endpoints",
    "exchange_code",
    "get_app",
    "issuer",
    "list_apps",
    "live_grants",
    "memberships",
    "parse_scope",
    "protected_resource_metadata",
    "protected_resource_metadata_url",
    "refresh",
    "resolve_access_token",
    "revoke_grant",
    "revoke_token",
    "rotate_secret",
    "scope_allowed",
    "update_app",
    "validate_authorize",
    "with_params",
]
