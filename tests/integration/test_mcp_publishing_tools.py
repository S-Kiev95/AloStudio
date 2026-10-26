"""Integration tests for the MCP publishing tools."""

from __future__ import annotations

import os
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from fastmcp import Client
from sqlalchemy import NullPool, delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.models_registry import import_all_models
from app.domains.accounts.models import Account
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.media_library.models import MediaAsset
from app.mcp.server import build_server
from app.mcp.service import create_token

import_all_models()

pytestmark = pytest.mark.integration


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


async def _seed(session: AsyncSession, *, suffix: str, scope: str = "write"):
    suffix = f"{suffix}-{secrets.token_hex(4)}"
    owner = await AccountBuilder(
        session,
        AccountBuilderParams(
            email=f"admin{suffix}@mcppub.example.com",
            account_name=f"MCPPUB{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    inbox = (
        await InboxBuilder(
            session,
            InboxBuilderParams(
                account=owner.account,
                name="Pagina MCP",
                channel_type="facebook",
                channel_params={
                    "page_id": f"P{suffix}",
                    "page_access_token": "t",
                },
            ),
        ).perform()
    ).inbox
    token = await create_token(
        session,
        account_id=owner.account.id,
        name=f"agent{suffix}",
        scope=scope,
        user_id=owner.user.id,
    )
    await session.commit()
    session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token.token
    return owner, inbox


def _body(result):
    return result.structured_content or result.data


async def test_mcp_schedule_list_and_cancel(mcp_session):
    _owner, inbox = await _seed(mcp_session, suffix="-flow")
    when = datetime.now(UTC) + timedelta(days=2)

    async with Client(build_server()) as client:
        channels = _body(await client.call_tool("list_publication_channels", {}))
        assert channels["channels"] == [
            {"inbox_id": inbox.id, "network": "facebook_page", "name": "Pagina MCP"}
        ]

        created = _body(
            await client.call_tool(
                "create_publication",
                {
                    "inbox_ids": [inbox.id],
                    "content": "Promo del agente",
                    "scheduled_for": when.isoformat(),
                },
            )
        )
        assert created["state"] == "scheduled"
        assert created["targets"][0]["channel"]["inbox_id"] == inbox.id

        listed = _body(
            await client.call_tool(
                "list_publications",
                {
                    "from": (when - timedelta(hours=1)).isoformat(),
                    "to": (when + timedelta(hours=1)).isoformat(),
                },
            )
        )
        assert [p["id"] for p in listed["publications"]] == [created["id"]]

        deleted = _body(
            await client.call_tool(
                "cancel_publication", {"publication_id": created["id"]}
            )
        )
        assert deleted == {"deleted": created["id"]}


async def test_mcp_lists_the_media_library(mcp_session):
    owner, _inbox = await _seed(mcp_session, suffix="-media")
    asset = MediaAsset(
        account_id=owner.account.id,
        kind="image",
        key=f"accounts/{owner.account.id}/uploads/x/foto.jpg",
        filename="foto.jpg",
        content_type="image/jpeg",
        size_bytes=10,
    )
    mcp_session.add(asset)
    await mcp_session.commit()

    async with Client(build_server()) as client:
        listed = _body(await client.call_tool("list_media", {}))

    (item,) = listed["media"]
    assert item["id"] == asset.id
    assert item["kind"] == "image"


async def test_mcp_validation_errors_reach_the_agent(mcp_session):
    _owner, inbox = await _seed(mcp_session, suffix="-err")

    async with Client(build_server()) as client:
        with pytest.raises(Exception, match="texto o al menos"):
            await client.call_tool(
                "create_publication", {"inbox_ids": [inbox.id], "content": ""}
            )


async def test_mcp_create_requires_write_scope(mcp_session):
    _owner, inbox = await _seed(mcp_session, suffix="-ro", scope="read")

    async with Client(build_server()) as client:
        with pytest.raises(Exception, match="requires 'write'"):
            await client.call_tool(
                "create_publication",
                {"inbox_ids": [inbox.id], "content": "no"},
            )
