"""``POST /auth/sso`` and the ``super_admin`` claim.

Postiz decides who operates the installation: its signed token says
``super_admin: true`` for its own super admins, and that marks the session
the exchange mints. A missing claim, ``false``, a truthy look-alike or a
token signed with another secret never does, and neither does a session
the same user opened with a password.

Postiz also opens the inbox with several requests at once, so a first visit
runs several exchanges in parallel: they must all succeed and leave one
user, one account and every session they minted.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool, delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.models import Account
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.installation import service
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_ADMINISTRATOR,
    AccessToken,
    AccountUser,
    User,
)
from app.main import app

pytestmark = pytest.mark.integration

SSO = "/auth/sso"
CONFIGS = "/api/v1/installation/configs"
SECRET = "test-sso-shared-secret-of-at-least-32-bytes"


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture(autouse=True)
def _sso_enabled(monkeypatch):
    monkeypatch.setenv("SSO_SHARED_SECRET", SECRET)
    service.reset_overlay()
    get_settings.cache_clear()
    yield
    service.reset_overlay()
    get_settings.cache_clear()


async def _native_user(db_session, email: str, *, super_admin: bool = False):
    """A user that signs in with a password, and one session of theirs."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=email,
            account_name=f"Native {email}",
            user_full_name="Native",
            user_password="Password123!",
            confirmed=True,
            super_admin=super_admin,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return {
        k: v
        for k, v in headers.as_response_headers().items()
        if k in ("access-token", "client", "uid")
    }


@pytest.fixture
async def _not_the_first_account(db_session):
    """Some other account comes first, so the bootstrap operator (the first
    account's admin) can't be what lets an SSO user in."""
    await _native_user(db_session, "owner@sso-first.example.com")


def _token(email: str, *, secret: str = SECRET, **extra: Any) -> str:
    claims = {
        "email": email,
        "name": "Postiz User",
        "org_id": f"org-{email}",
        "org_name": "Postiz Org",
        "exp": datetime.now(UTC) + timedelta(seconds=60),
        **extra,
    }
    return jwt.encode(claims, secret, algorithm="HS256")


async def _sign_in(client: AsyncClient, token: str) -> dict[str, str]:
    resp = await client.post(SSO, json={"token": token})
    assert resp.status_code == 200, resp.text
    return {k: resp.headers[k] for k in ("access-token", "client", "uid")}


async def _user(db_session, email: str) -> User | None:
    return (await db_session.exec(select(User).where(User.email == email))).first()


# ---------------------------------------------------------------------------
# No claim, no access
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("_not_the_first_account")
async def test_without_the_claim_an_sso_user_is_not_the_operator(
    client, db_session
):
    headers = await _sign_in(client, _token("plain@sso.example.com"))

    assert (await _user(db_session, "plain@sso.example.com")).type is None
    resp = await client.get(CONFIGS, headers=headers)
    assert resp.status_code == 401
    assert resp.json()["code"] == "not_authorized"


@pytest.mark.usefixtures("_not_the_first_account")
@pytest.mark.parametrize("claim", [False, "true", "yes", 1, None])
async def test_only_a_literal_true_counts(client, claim):
    email = f"lookalike-{claim!s}@sso.example.com".lower()
    headers = await _sign_in(client, _token(email, super_admin=claim))

    assert (await client.get(CONFIGS, headers=headers)).status_code == 401


async def test_an_account_postiz_created_first_gets_no_bootstrap(
    client, db_session
):
    """On a fresh sidecar the first Postiz org to sign in creates account
    #1 and becomes its admin; that must not make it the operator."""
    from sqlalchemy import func

    from app.domains.accounts.models import Account
    from app.domains.installation.deps import has_any_super_admin

    headers = await _sign_in(client, _token("tenant@sso.example.com"))

    first = (await db_session.exec(select(func.min(Account.id)))).one()
    account = (
        await db_session.exec(
            select(Account).where(
                Account.settings["postiz_org_id"].astext
                == "org-tenant@sso.example.com"
            )
        )
    ).first()
    assert account.id == first
    assert await has_any_super_admin(db_session) is False
    assert (await client.get(CONFIGS, headers=headers)).status_code == 401


async def test_a_claim_signed_with_another_secret_is_refused(client, db_session):
    forged = _token(
        "forged@sso.example.com",
        secret="not-the-shared-secret-but-also-32-bytes",
        super_admin=True,
    )
    resp = await client.post(SSO, json={"token": forged})
    assert resp.status_code == 401
    assert await _user(db_session, "forged@sso.example.com") is None


# ---------------------------------------------------------------------------
# The claim marks one session, not the user
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("_not_the_first_account")
async def test_a_postiz_super_admin_operates_the_installation(client, db_session):
    headers = await _sign_in(
        client, _token("operator@sso.example.com", super_admin=True)
    )

    resp = await client.get(CONFIGS, headers=headers)
    assert resp.status_code == 200, resp.text
    # The user row is untouched: the mark lives on the session.
    assert (await _user(db_session, "operator@sso.example.com")).type is None


@pytest.mark.usefixtures("_not_the_first_account")
async def test_a_password_session_of_the_same_user_does_not_inherit_it(
    client, db_session
):
    """SSO links by email to a user that may already exist with its own
    password (open signup): whoever holds that password stays out."""
    email = "preexisting@sso.example.com"
    password_session = await _native_user(db_session, email)

    sso_session = await _sign_in(client, _token(email, super_admin=True))

    assert (await client.get(CONFIGS, headers=sso_session)).status_code == 200
    assert (await client.get(CONFIGS, headers=password_session)).status_code == 401


@pytest.mark.usefixtures("_not_the_first_account")
async def test_losing_the_claim_takes_the_role_away(client):
    """Removed as super admin in Postiz → out on the next SSO sign-in, and
    the session minted while it was still one stops working too."""
    email = "demoted@sso.example.com"
    earlier = await _sign_in(client, _token(email, super_admin=True))
    assert (await client.get(CONFIGS, headers=earlier)).status_code == 200

    later = await _sign_in(client, _token(email))

    assert (await client.get(CONFIGS, headers=later)).status_code == 401
    assert (await client.get(CONFIGS, headers=earlier)).status_code == 401


async def test_a_native_super_admin_keeps_the_role_without_the_claim(
    client, db_session
):
    """Postiz only grants and takes back what it granted."""
    email = "native-sa@sso.example.com"
    native_session = await _native_user(db_session, email, super_admin=True)

    sso_session = await _sign_in(client, _token(email))

    assert (await _user(db_session, email)).type == "SuperAdmin"
    assert (await client.get(CONFIGS, headers=native_session)).status_code == 200
    assert (await client.get(CONFIGS, headers=sso_session)).status_code == 200


# ---------------------------------------------------------------------------
# First access in parallel
# ---------------------------------------------------------------------------
PARALLEL = 5
RACE_DOMAIN = "sso-race.example.com"


# ---------------------------------------------------------------------------
# One user, several Postiz orgs
# ---------------------------------------------------------------------------
async def test_the_session_lands_in_the_account_of_the_org_it_came_from(client):
    email = "multi@sso.example.com"

    async def account_for(org_id: str) -> int:
        token = _token(email, org_id=org_id, org_name=f"Org {org_id}")
        resp = await client.post(SSO, json={"token": token})
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]["account_id"]

    account_a = await account_for("org-a")
    account_b = await account_for("org-b")
    assert account_a != account_b
    # Not the first membership: each org keeps landing in its own account.
    assert await account_for("org-b") == account_b
    assert await account_for("org-a") == account_a


@pytest.fixture
async def committed_sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Sessions that commit, each on its own connection, as in production.

    The races below only happen between separate transactions, which the
    shared, rolled-back ``db_session`` can't have. Every row they leave
    belongs to a ``RACE_DOMAIN`` user or a ``race-`` org and is deleted at
    teardown.
    """
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    sessions = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    try:
        yield sessions
    finally:
        async with sessions() as cleanup:
            race_users = select(User.id).where(User.email.like(f"%@{RACE_DOMAIN}"))  # type: ignore[union-attr]
            await cleanup.exec(  # type: ignore[call-overload]
                delete(AccessToken).where(
                    AccessToken.owner_type == "User",
                    AccessToken.owner_id.in_(race_users),  # type: ignore[union-attr]
                )
            )
            await cleanup.exec(  # type: ignore[call-overload]
                delete(Account).where(
                    Account.settings["postiz_org_id"].astext.like("race-%")
                )
            )
            await cleanup.exec(  # type: ignore[call-overload]
                delete(User).where(User.email.like(f"%@{RACE_DOMAIN}"))  # type: ignore[union-attr]
            )
            await cleanup.commit()
        await engine.dispose()


@pytest.fixture
def _committing_requests(committed_sessions) -> Iterator[None]:
    async def _override() -> AsyncIterator[AsyncSession]:
        # Same contract as ``app.core.db.get_session``.
        async with committed_sessions() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = _override
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
async def parallel_client(_committing_requests) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _race_ids() -> tuple[str, str]:
    """A fresh org id and email suffix, so no run sees another's rows."""
    run = secrets.token_hex(4)
    return f"race-{run}", f"{run}@{RACE_DOMAIN}"


async def _sign_in_in_parallel(
    client: AsyncClient, tokens: list[str]
) -> list[dict[str, Any]]:
    responses = await asyncio.gather(
        *(client.post(SSO, json={"token": token}) for token in tokens)
    )
    assert [r.status_code for r in responses] == [200] * len(tokens), [
        r.text for r in responses if r.status_code != 200
    ]
    return [{"client": r.headers["client"], **r.json()["data"]} for r in responses]


async def _org_accounts(sessions, org_id: str) -> list[Account]:
    async with sessions() as s:
        return list(
            (
                await s.exec(
                    select(Account).where(
                        Account.settings["postiz_org_id"].astext == org_id
                    )
                )
            ).all()
        )


async def test_a_first_visit_in_parallel_creates_one_user_and_one_account(
    parallel_client, committed_sessions
):
    """Production, 2026-10-19: every exchange but the first answered 500
    on ``index_users_on_uid_and_provider``."""
    org_id, suffix = _race_ids()
    email = f"director-{suffix}"

    signed_in = await _sign_in_in_parallel(
        parallel_client, [_token(email, org_id=org_id) for _ in range(PARALLEL)]
    )

    accounts = await _org_accounts(committed_sessions, org_id)
    async with committed_sessions() as s:
        users = (await s.exec(select(User).where(User.email == email))).all()
        assert len(users) == 1
        assert len(accounts) == 1
        memberships = (
            await s.exec(
                select(AccountUser).where(AccountUser.account_id == accounts[0].id)
            )
        ).all()
    assert [(m.user_id, m.role) for m in memberships] == [
        (users[0].id, ACCOUNT_USER_ROLE_ADMINISTRATOR)
    ]
    assert {d["account_id"] for d in signed_in} == {accounts[0].id}
    # Each exchange's session outlived the others' writes to ``tokens``.
    assert {d["client"] for d in signed_in} <= set(users[0].tokens)


async def test_members_of_a_new_org_in_parallel_share_one_account(
    parallel_client, committed_sessions
):
    """Several people of the same new org open the inbox at once: one
    account, everyone in it, one administrator."""
    org_id, suffix = _race_ids()
    emails = [f"member{i}-{suffix}" for i in range(PARALLEL)]

    signed_in = await _sign_in_in_parallel(
        parallel_client, [_token(email, org_id=org_id) for email in emails]
    )

    accounts = await _org_accounts(committed_sessions, org_id)
    assert len(accounts) == 1
    async with committed_sessions() as s:
        memberships = (
            await s.exec(
                select(AccountUser).where(AccountUser.account_id == accounts[0].id)
            )
        ).all()
    assert {m.user_id for m in memberships} == {d["id"] for d in signed_in}
    assert len(memberships) == PARALLEL
    assert [m.role for m in memberships].count(ACCOUNT_USER_ROLE_ADMINISTRATOR) == 1
    assert {d["account_id"] for d in signed_in} == {accounts[0].id}


async def test_parallel_exchanges_of_a_known_user_keep_every_session(
    parallel_client, committed_sessions
):
    """Each exchange appends its session to the user's ``tokens``; none may
    write back a stale copy that drops another's."""
    org_id, suffix = _race_ids()
    email = f"returning-{suffix}"
    await _sign_in_in_parallel(parallel_client, [_token(email, org_id=org_id)])

    signed_in = await _sign_in_in_parallel(
        parallel_client, [_token(email, org_id=org_id) for _ in range(PARALLEL)]
    )

    async with committed_sessions() as s:
        user = (await s.exec(select(User).where(User.email == email))).one()
    assert {d["client"] for d in signed_in} <= set(user.tokens)


@pytest.mark.usefixtures("_committing_requests")
async def test_the_session_is_committed_before_the_response_leaves(
    committed_sessions,
):
    """Postiz sends every request it held during the exchange as soon as
    the response arrives; the session must already be in the database.
    ``ASGITransport`` returns only once the app finishes, so the check runs
    where the response starts."""
    org_id, suffix = _race_ids()
    email = f"eager-{suffix}"
    committed_at_response: list[bool] = []

    async def watching_app(scope, receive, send) -> None:
        async def _send(message) -> None:
            if message["type"] == "http.response.start":
                async with committed_sessions() as s:
                    user = (
                        await s.exec(select(User).where(User.email == email))
                    ).first()
                committed_at_response.append(user is not None)
            await send(message)

        await app(scope, receive, _send)

    transport = ASGITransport(app=watching_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await _sign_in_in_parallel(ac, [_token(email, org_id=org_id)])

    assert committed_at_response == [True]
