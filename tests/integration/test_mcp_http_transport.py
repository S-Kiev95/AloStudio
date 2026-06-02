"""End-to-end test for the MCP HTTP transport.

Boots ``app.mcp`` over HTTP on a free port, then connects with a real
fastmcp ``Client(url, auth=<bearer>)`` to confirm the auth middleware
+ tool surface work identically over the wire as in-memory.

Anchors:
  app/mcp/__main__.py
  app/mcp/server.py
"""

from __future__ import annotations

import asyncio
import os
import socket
import threading
from collections.abc import AsyncIterator
from contextlib import closing

import pytest
from fastmcp import Client
from fastmcp.client.auth import BearerAuth
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


def _free_port() -> int:
    """Bind ephemeral, close, return the port — small race window but
    fine for one-shot test boots."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
async def mcp_committed_session() -> AsyncIterator[AsyncSession]:
    """Per-test session that COMMITS — mirrors the pattern in
    ``test_mcp_server.py`` so the MCP middleware's own connection sees
    the seeded token."""
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


async def _seed_token(session: AsyncSession, *, suffix: str) -> str:
    import secrets

    suffix = f"{suffix}-{secrets.token_hex(4)}"
    owner = await AccountBuilder(
        session,
        AccountBuilderParams(
            email=f"http{suffix}@mcp.example.com",
            account_name=f"MCPHttp{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    row = await create_token(
        session,
        account_id=owner.account.id,
        name=f"agent{suffix}",
        scope="write",
        user_id=owner.user.id,
    )
    await session.commit()
    session._mcp_test_accounts.append(owner.account.id)  # type: ignore[attr-defined]
    return row.token


def _serve_in_thread(mcp, *, host: str, port: int, path: str) -> threading.Thread:
    """Run ``mcp.run`` in a background daemon thread. fastmcp creates
    its own event loop inside ``run`` so we MUST NOT share the test's
    loop — a daemon thread is the cheapest isolation."""
    thread = threading.Thread(
        target=lambda: mcp.run(
            transport="http", host=host, port=port, path=path, show_banner=False
        ),
        name="mcp-http-test",
        daemon=True,
    )
    thread.start()
    return thread


async def _wait_for_port(host: str, port: int, *, timeout: float = 10.0) -> None:
    """Poll the bound port until accepting connections — beats sleeping."""
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        try:
            r, w = await asyncio.open_connection(host, port)
            w.close()
            await w.wait_closed()
            return
        except OSError:
            if asyncio.get_event_loop().time() > deadline:
                raise TimeoutError(f"port {host}:{port} never came up")
            await asyncio.sleep(0.1)


async def test_http_transport_authenticates_and_calls_whoami(
    mcp_committed_session,
):
    """Real HTTP boot + bearer-auth handshake + tool call round-trip."""
    # Env var fallback removed — the HTTP path must read the
    # Authorization header. Stale env from another test would mask a
    # broken header path, so make sure it's empty.
    prev_env = os.environ.pop("MCP_BEARER_TOKEN", None)
    try:
        token = await _seed_token(mcp_committed_session, suffix="-http")
        port = _free_port()
        host = "127.0.0.1"
        path = "/mcp"

        mcp = build_server()
        _serve_in_thread(mcp, host=host, port=port, path=path)
        await _wait_for_port(host, port)

        url = f"http://{host}:{port}{path}"
        async with Client(url, auth=BearerAuth(token)) as client:
            result = await client.call_tool("whoami", {})
            body = result.structured_content or result.data
            assert body["scope"] == "write"
            assert body["account_name"].startswith("MCPHttp")
            assert body["user"]["id"] is not None
    finally:
        if prev_env is not None:
            os.environ["MCP_BEARER_TOKEN"] = prev_env


async def test_http_transport_rejects_missing_bearer(mcp_committed_session):
    """No ``Authorization`` header → the auth middleware raises and the
    HTTP transport surfaces the error to the client."""
    prev_env = os.environ.pop("MCP_BEARER_TOKEN", None)
    try:
        port = _free_port()
        host = "127.0.0.1"
        path = "/mcp"

        mcp = build_server()
        _serve_in_thread(mcp, host=host, port=port, path=path)
        await _wait_for_port(host, port)

        url = f"http://{host}:{port}{path}"
        with pytest.raises(Exception, match="missing bearer token"):
            async with Client(url) as client:
                await client.call_tool("whoami", {})
    finally:
        if prev_env is not None:
            os.environ["MCP_BEARER_TOKEN"] = prev_env
