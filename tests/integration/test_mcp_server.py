"""Integration tests for the MCP server scaffold + auth.

Uses fastmcp's in-memory ``Client(mcp_instance)`` transport so we can
exercise the full middleware + tool dispatch without spinning up an
HTTP server. Auth tokens are seeded into the real ``mcp_tokens`` table
and resolved via the production middleware.

These tests DON'T use the standard ``db_session`` fixture (which
wraps everything in a non-committing transaction) because the MCP
middleware opens its own engine. Any seeded state must be committed
to disk to be visible across sessions. The ``mcp_committed_session``
fixture commits writes and tracks rows for teardown.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from fastmcp import Client
from sqlalchemy import NullPool, delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.accounts.models import Account
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.mcp.server import build_server
from app.mcp.service import create_token

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _clear_token_env():
    """Make sure leaked env vars from a prior test don't contaminate."""
    prev = os.environ.pop("MCP_BEARER_TOKEN", None)
    yield
    if prev is None:
        os.environ.pop("MCP_BEARER_TOKEN", None)
    else:
        os.environ["MCP_BEARER_TOKEN"] = prev


@pytest.fixture
async def mcp_committed_session() -> AsyncIterator[AsyncSession]:
    """Per-test session that COMMITS writes (the MCP middleware needs
    to see the seeded data across its own connection). Tracks the
    ``account_ids`` created so teardown can CASCADE-delete them."""
    engine = create_async_engine(
        get_settings().database_url, poolclass=NullPool
    )
    created_accounts: list[int] = []
    try:
        sessionmaker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        async with sessionmaker() as session:
            # Attach a tracker callback so the helper can register
            # accounts for cleanup.
            session._mcp_test_accounts = created_accounts  # type: ignore[attr-defined]
            yield session
        async with sessionmaker() as cleanup:
            if created_accounts:
                await cleanup.exec(  # type: ignore[call-overload]
                    delete(Account).where(
                        Account.id.in_(created_accounts)  # type: ignore[union-attr]
                    )
                )
                await cleanup.commit()
    finally:
        await engine.dispose()


async def _seed_account_and_token(
    session: AsyncSession, *, suffix: str, scope: str = "read"
):
    """Seed an account + a fresh MCP token; commit. Returns
    (account_id, user_id, token_value)."""
    owner = await AccountBuilder(
        session,
        AccountBuilderParams(
            email=f"admin{suffix}@mcp.example.com",
            account_name=f"MCP{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    row = await create_token(
        session,
        account_id=owner.account.id,
        name=f"agent{suffix}",
        scope=scope,
        user_id=owner.user.id,
    )
    await session.commit()
    session._mcp_test_accounts.append(owner.account.id)  # type: ignore[attr-defined]
    return owner.account.id, owner.user.id, row.token


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
async def test_whoami_with_valid_token(mcp_committed_session):
    account_id, user_id, token = await _seed_account_and_token(
        mcp_committed_session, suffix="-ok"
    )
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool("whoami", {})
        body = result.structured_content or result.data
        assert body["account_id"] == account_id
        assert body["scope"] == "read"
        assert body["user"]["id"] == user_id


async def test_whoami_rejects_unknown_token(mcp_committed_session):
    os.environ["MCP_BEARER_TOKEN"] = "definitely-not-a-real-token-string"
    mcp = build_server()
    with pytest.raises(Exception, match="unknown token"):
        async with Client(mcp) as client:
            await client.call_tool("whoami", {})


async def test_list_tools_requires_auth(mcp_committed_session):
    """Even the discovery surface is gated — agents without a valid
    token can't enumerate tools."""
    mcp = build_server()
    with pytest.raises(Exception, match="missing bearer token"):
        async with Client(mcp) as client:
            await client.list_tools()


async def test_list_tools_with_valid_token_returns_whoami(
    mcp_committed_session,
):
    _account_id, _user_id, token = await _seed_account_and_token(
        mcp_committed_session, suffix="-lt"
    )
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = [t.name for t in tools]
        assert "whoami" in names


async def test_scope_recorded_on_token(mcp_committed_session):
    """Token created with admin scope surfaces on whoami."""
    _account_id, _user_id, token = await _seed_account_and_token(
        mcp_committed_session, suffix="-sc", scope="admin"
    )
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool("whoami", {})
        body = result.structured_content or result.data
        assert body["scope"] == "admin"
