"""``POST /auth/sso`` — Postiz → AloStudio SSO bridge.

Postiz redirects the user's browser to the *frontend* at
``/auth/sso?token=<jwt>``; the frontend BFF forwards the token here. The JWT
is HS256-signed with ``SSO_SHARED_SECRET`` — a secret shared with Postiz and
deliberately distinct from ``secret_key`` (which signs AloStudio's own
access/refresh tokens), so a leak of one can't forge the other. That is why
this module decodes with ``jwt`` directly instead of reusing
:func:`app.core.security.decode_token`, which is pinned to ``secret_key``.

Claims (required): ``email``, ``org_id``, ``org_name``, ``exp`` (~60 s —
Postiz mints one per redirect). ``name`` is optional. A Postiz organization
maps to an AloStudio ``Account`` via ``accounts.settings->>'postiz_org_id'``;
the first visit for an org creates the account with the user as
administrator, later visits attach unknown users as agents.

``super_admin`` (optional) carries Postiz's own super-admin flag, which
opens the installation settings (:mod:`app.domains.installation.deps`).
Only a literal ``true`` counts, and it marks the session minted here, not
the user. Anything else — the claim missing, ``false``, a string — strips
the mark from every session of the user, so a super admin removed in
Postiz loses it on their next SSO sign-in.

Fail-closed: an empty ``SSO_SHARED_SECRET`` answers 404 (feature off) and any
signature/expiry/claim problem answers 401. No sign-in throttle here — this
is a machine-issued, short-lived, signed token, not a credential-guessing
surface.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

import jwt
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.core.security import hash_password
from app.core.tokens import base58_token
from app.domains.accounts.models import Account
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.installation.deps import SSO_SUPER_ADMIN_TOKEN_KEY
from app.domains.users.models import (
    AccessToken,
    AccountUser,
    User,
    role_name_to_int,
)
from app.domains.users.presenters import present_auth_response

router = APIRouter(prefix="/auth", tags=["auth"])


class SsoRequest(BaseModel):
    """Body of ``POST /auth/sso`` — the Postiz-minted JWT, nothing else."""

    token: str


_INVALID_SSO_TOKEN_BODY = {"errors": ["Invalid or expired SSO token."]}


def _decode_sso_claims(token: str) -> dict[str, Any] | None:
    """Verify the HS256 signature + ``exp`` against the shared secret.

    Returns ``None`` for any failure (bad signature, expired, malformed) —
    the endpoint maps every variant to the same 401 so an attacker can't
    probe which check failed. ``ExpiredSignatureError`` is a subclass of
    ``InvalidTokenError``, so one except covers both.
    """
    try:
        claims: dict[str, Any] = jwt.decode(
            token, get_settings().sso_shared_secret, algorithms=["HS256"]
        )
    except jwt.InvalidTokenError:
        return None
    return claims


async def _find_or_create_user(
    session: AsyncSession, *, email: str, name: str
) -> User:
    # FOR NO KEY UPDATE: the caller appends this exchange's session to
    # ``user.tokens``, and two exchanges for the same user would otherwise
    # each write back the tokens they read, the later one dropping the
    # other's session. Only non-key columns change, so rows that reference
    # the user can still be inserted meanwhile.
    by_email = select(User).where(User.email == email).with_for_update(key_share=True)
    user = (await session.exec(by_email)).first()
    if user is not None:
        return user
    # Random, unguessable password — SSO users never sign in with it; the
    # password-reset flow stays available if they later want direct access.
    # Mirrors ``AccountBuilder._create_user`` (uid = email, confirmed).
    user = User(
        provider="email",
        uid=email,
        email=email,
        encrypted_password=hash_password(secrets.token_urlsafe(32)),
        name=name,
        pubsub_token=base58_token(24),
        confirmed_at=datetime.now(UTC).replace(tzinfo=None),
    )
    try:
        # A savepoint: Postiz opens the inbox with several requests at once,
        # so a first visit can run several exchanges in parallel, and the
        # check above passes for all of them. The insert of whichever comes
        # second waits for the first to commit, then collides on
        # ``index_users_on_uid_and_provider``.
        async with session.begin_nested():
            session.add(user)
            await session.flush()
    except IntegrityError:
        # The other exchange created the user: sign in as that one.
        user = (await session.exec(by_email)).first()
        if user is None:
            raise
    return user


def _with_super_admin_mark(
    tokens: dict[str, Any], *, client: str, claims: dict[str, Any]
) -> dict[str, Any]:
    """Postiz's super-admin flag onto the new session (see module docstring).

    ``is True`` on purpose: a truthy ``"false"`` or ``1`` must not count.
    Builds new entries instead of editing them, as ``tokens`` shares them
    with the user's loaded column value.
    """
    if claims.get("super_admin") is True:
        return {**tokens, client: {**tokens[client], SSO_SUPER_ADMIN_TOKEN_KEY: True}}
    return {
        key: {k: v for k, v in entry.items() if k != SSO_SUPER_ADMIN_TOKEN_KEY}
        for key, entry in tokens.items()
    }


async def _ensure_membership(
    session: AsyncSession, *, user: User, org_id: str, org_name: str
) -> None:
    """Link ``user`` to the account mapped to ``org_id``, creating it if needed.

    Serialized per org with a transaction-scoped advisory lock. Two members
    of a new org signing in at once would otherwise both find no account and
    create one each, as nothing in the schema keeps ``postiz_org_id``
    unique, and two first members of a mapped account would both become its
    administrator. The lock is held until the request commits, so the
    second exchange sees what the first one wrote.
    """
    await session.exec(
        select(func.pg_advisory_xact_lock(func.hashtext(f"postiz_org:{org_id}")))
    )
    account = (
        await session.exec(
            select(Account).where(Account.settings["postiz_org_id"].astext == org_id)
        )
    ).first()

    if account is None:
        # First visit for this org: the builder creates the account and
        # links the user as administrator (the builder's fixed role).
        result = await AccountBuilder(
            session,
            AccountBuilderParams(
                email=user.uid,
                account_name=org_name,
                user_full_name=user.name,
                confirmed=True,
                existing_user=user,
            ),
        ).perform()
        result.account.settings = {
            **(result.account.settings or {}),
            "postiz_org_id": org_id,
        }
        session.add(result.account)
        await session.flush()
        return

    membership = (
        await session.exec(
            select(AccountUser).where(
                AccountUser.account_id == account.id,
                AccountUser.user_id == user.id,
            )
        )
    ).first()
    if membership is not None:
        return

    # First user of an already-mapped account becomes its administrator
    # (covers accounts mapped out-of-band); everyone else lands as agent.
    has_members = (
        await session.exec(
            select(AccountUser.id).where(AccountUser.account_id == account.id).limit(1)
        )
    ).first() is not None
    session.add(
        AccountUser(
            account_id=account.id,
            user_id=user.id,
            role=role_name_to_int("agent" if has_members else "administrator"),
        )
    )
    await session.flush()


@router.post("/sso", status_code=status.HTTP_200_OK)
async def sso_sign_in(
    payload: SsoRequest,
    response: Response,
    # scope="function" commits before the response is sent, not after (the
    # default): Postiz uses the minted session right away, for every
    # request it held during the exchange.
    session: AsyncSession = Depends(get_session, scope="function"),
) -> dict:
    """Exchange a Postiz-signed SSO token for an AloStudio session.

    Success mirrors ``POST /auth/sign_in`` byte-for-byte: the devise
    ``access-token`` / ``client`` / ``uid`` / ``expiry`` / ``token-type``
    headers plus the ``{ "data": { ...user } }`` body, so the frontend
    reuses its login flow unchanged.
    """
    if not get_settings().sso_shared_secret:
        raise ChatwootHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"errors": ["SSO is not enabled."]},
        )

    claims = _decode_sso_claims(payload.token)
    if claims is None:
        raise ChatwootHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_SSO_TOKEN_BODY,
        )

    email = str(claims.get("email") or "").strip().lower()
    org_id = str(claims.get("org_id") or "").strip()
    org_name = str(claims.get("org_name") or "").strip()
    name = str(claims.get("name") or "").strip()
    if not email or not org_id or not org_name:
        raise ChatwootHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_SSO_TOKEN_BODY,
        )

    user = await _find_or_create_user(session, email=email, name=name)
    await _ensure_membership(session, user=user, org_id=org_id, org_name=org_name)

    # Devise `trackable` hook, mirroring sign_in.
    now = datetime.now(UTC).replace(tzinfo=None)
    user.sign_in_count = (user.sign_in_count or 0) + 1
    user.last_sign_in_at = user.current_sign_in_at
    user.current_sign_in_at = now

    headers, new_tokens = create_new_auth_token(user_tokens=user.tokens, uid=user.uid)
    user.tokens = _with_super_admin_mark(
        new_tokens, client=headers.client, claims=claims
    )
    session.add(user)
    await session.flush()

    for k, v in headers.as_response_headers().items():
        response.headers[k] = v

    memberships = (
        await session.exec(
            select(AccountUser)
            .where(AccountUser.user_id == user.id)
            .order_by(AccountUser.id)  # type: ignore[arg-type]
        )
    ).all()

    access_token = (
        await session.exec(
            select(AccessToken).where(
                AccessToken.owner_type == "User",
                AccessToken.owner_id == user.id,
            )
        )
    ).first()
    if access_token is None:
        # AccessTokenable backfill — mirrors AccountBuilder._get_access_token.
        access_token = AccessToken(
            owner_type="User",
            owner_id=user.id,
            token=base58_token(24),
        )
        session.add(access_token)
        await session.flush()

    return present_auth_response(
        user=user,
        access_token=access_token,
        account_users=list(memberships),
    )
