"""Integration tests for the Instagram MCP tools (I.13).

Follows the MCP test pattern: a commit-friendly session (the MCP
middleware opens its own session, so seeded state must be committed),
a real token, and the in-memory ``Client(mcp)`` transport. Meta calls
are respx-mocked in-process.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from fastmcp import Client
from sqlalchemy import NullPool, delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.accounts.models import Account
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram import publishing_service as svc
from app.domains.products import service as psvc
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.mcp.server import build_server
from app.mcp.service import create_token

pytestmark = pytest.mark.integration

GRAPH = "https://graph.facebook.com/v23.0"


@pytest.fixture(autouse=True)
def _clear_token_env():
    prev = os.environ.pop("MCP_BEARER_TOKEN", None)
    yield
    if prev is None:
        os.environ.pop("MCP_BEARER_TOKEN", None)
    else:
        os.environ["MCP_BEARER_TOKEN"] = prev


@pytest.fixture
async def mcp_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        get_settings().database_url, poolclass=NullPool
    )
    created: list[int] = []
    try:
        sm = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        async with sm() as session:
            session._mcp_accts = created  # type: ignore[attr-defined]
            yield session
        async with sm() as cleanup:
            if created:
                await cleanup.exec(  # type: ignore[call-overload]
                    delete(Account).where(Account.id.in_(created))  # type: ignore[union-attr]
                )
                await cleanup.commit()
    finally:
        await engine.dispose()


async def _seed(mcp_session, *, scope: str = "write"):
    suffix = f"-{secrets.token_hex(4)}"
    owner = await AccountBuilder(
        mcp_session,
        AccountBuilderParams(
            email=f"admin{suffix}@mcpig.example.com",
            account_name=f"MCPIG{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    inbox_res = await InboxBuilder(
        mcp_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"IG{suffix}",
            channel_type="instagram",
            channel_params={
                "instagram_id": f"ig-mcp-{suffix}",
                "access_token": "PAGE-TOKEN",
            },
        ),
    ).perform()
    token = await create_token(
        mcp_session,
        account_id=owner.account.id,
        name=f"agent{suffix}",
        scope=scope,
        user_id=owner.user.id,
    )
    await mcp_session.commit()
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    return owner, inbox_res, token.token


async def _published_post(mcp_session, owner, inbox_res, ig_media_id):
    post = await svc.create_post(
        mcp_session,
        account_id=owner.account.id,
        inbox_id=inbox_res.inbox.id,
        channel_instagram_id=inbox_res.channel.id,
        media_type="IMAGE",
        source={"image_url": "https://x.example.com/p.jpg"},
    )
    post.state = "published"
    post.ig_media_id = ig_media_id
    mcp_session.add(post)
    await mcp_session.commit()
    return post


def _body(result):
    return result.structured_content or result.data


# ---------------------------------------------------------------------------
# read tools
# ---------------------------------------------------------------------------
async def test_list_instagram_posts(mcp_session):
    owner, inbox_res, token = await _seed(mcp_session)
    post = await _published_post(mcp_session, owner, inbox_res, "M1")
    os.environ["MCP_BEARER_TOKEN"] = token
    async with Client(build_server()) as client:
        body = _body(await client.call_tool("list_instagram_posts", {}))
        assert any(p["id"] == post.id for p in body["posts"])


async def test_products_for_media_ai_context(mcp_session):
    owner, inbox_res, token = await _seed(mcp_session)
    post = await _published_post(mcp_session, owner, inbox_res, "M2")
    product = await psvc.create_product(
        mcp_session,
        account_id=owner.account.id,
        payload={"name": "Remera"},
    )
    await svc.set_post_products(
        mcp_session,
        account_id=owner.account.id,
        post=post,
        product_ids=[product.id],
    )
    await mcp_session.commit()
    os.environ["MCP_BEARER_TOKEN"] = token
    async with Client(build_server()) as client:
        body = _body(
            await client.call_tool(
                "instagram_products_for_media", {"ig_media_id": "M2"}
            )
        )
        assert [p["id"] for p in body["products"]] == [product.id]


# ---------------------------------------------------------------------------
# write tools
# ---------------------------------------------------------------------------
async def test_create_instagram_post_scheduled(mcp_session):
    owner, inbox_res, token = await _seed(mcp_session)
    product = await psvc.create_product(
        mcp_session, account_id=owner.account.id, payload={"name": "Gorra"}
    )
    await mcp_session.commit()
    os.environ["MCP_BEARER_TOKEN"] = token
    from datetime import UTC, datetime, timedelta

    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    async with Client(build_server()) as client:
        body = _body(
            await client.call_tool(
                "create_instagram_post",
                {
                    "inbox_id": inbox_res.inbox.id,
                    "media_type": "IMAGE",
                    "source": {"image_url": "https://x.example.com/p.jpg"},
                    "caption": "via agent",
                    "scheduled_for": future,
                    "product_ids": [product.id],
                },
            )
        )
        assert body["state"] == "pending"
        assert [p["id"] for p in body["products"]] == [product.id]


@respx.mock
async def test_reply_to_instagram_comment(mcp_session):
    owner, inbox_res, token = await _seed(mcp_session)
    parent = await svc.upsert_comment(
        mcp_session,
        account_id=owner.account.id,
        channel_instagram_id=inbox_res.channel.id,
        ig_comment_id="PC1",
        ig_media_id="MED",
        text="pregunta",
    )
    await mcp_session.commit()
    respx.post(f"{GRAPH}/PC1/replies").mock(
        return_value=httpx.Response(200, json={"id": "RPLY1"})
    )
    os.environ["MCP_BEARER_TOKEN"] = token
    async with Client(build_server()) as client:
        body = _body(
            await client.call_tool(
                "reply_to_instagram_comment",
                {"comment_id": parent.id, "message": "gracias!"},
            )
        )
        assert body["ig_comment_id"] == "RPLY1"
        assert body["parent_comment_id"] == "PC1"


# ---------------------------------------------------------------------------
# permission scope
# ---------------------------------------------------------------------------
async def test_read_scope_cannot_create(mcp_session):
    _owner, inbox_res, token = await _seed(mcp_session, scope="read")
    os.environ["MCP_BEARER_TOKEN"] = token
    async with Client(build_server()) as client:
        with pytest.raises(Exception):  # noqa: B017  (FastMCP tool error)
            await client.call_tool(
                "create_instagram_post",
                {
                    "inbox_id": inbox_res.inbox.id,
                    "media_type": "IMAGE",
                    "source": {"image_url": "https://x.example.com/p.jpg"},
                },
            )
