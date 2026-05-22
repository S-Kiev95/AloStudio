"""Integration tests for MCP meta tools (labels + reports)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from fastmcp import Client
from sqlalchemy import NullPool, delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.accounts.models import Account
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
    toggle_status,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.labels.models import Label
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.mcp.server import build_server
from app.mcp.service import create_token

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


async def _seed_account_token(
    session: AsyncSession, *, suffix: str, scope: str = "read"
):
    import secrets

    suffix = f"{suffix}-{secrets.token_hex(4)}"
    owner = await AccountBuilder(
        session,
        AccountBuilderParams(
            email=f"admin{suffix}@mcpmt.example.com",
            account_name=f"MCPMT{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    token = await create_token(
        session,
        account_id=owner.account.id,
        name=f"agent{suffix}",
        scope=scope,
        user_id=owner.user.id,
    )
    return owner, token.token


def _body(result):
    return result.structured_content or result.data


# ---------------------------------------------------------------------------
# list_labels
# ---------------------------------------------------------------------------
async def test_list_labels_returns_account_labels_alphabetically(mcp_session):
    owner, token = await _seed_account_token(mcp_session, suffix="-ll")
    for title in ["urgent", "billing", "feature-request"]:
        mcp_session.add(Label(account_id=owner.account.id, title=title))
    await mcp_session.commit()
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool("list_labels", {})
        body = _body(result)
        titles = [lab["title"] for lab in body["labels"]]
        # Alphabetical.
        assert titles == ["billing", "feature-request", "urgent"]


async def test_list_labels_isolates_per_account(mcp_session):
    owner_a, token_a = await _seed_account_token(
        mcp_session, suffix="-ai"
    )
    owner_b, _ = await _seed_account_token(mcp_session, suffix="-bi")
    mcp_session.add(Label(account_id=owner_a.account.id, title="a-only"))
    mcp_session.add(Label(account_id=owner_b.account.id, title="b-only"))
    await mcp_session.commit()
    mcp_session._mcp_accts.append(owner_a.account.id)  # type: ignore[attr-defined]
    mcp_session._mcp_accts.append(owner_b.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token_a

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool("list_labels", {})
        titles = {lab["title"] for lab in _body(result)["labels"]}
        assert titles == {"a-only"}


# ---------------------------------------------------------------------------
# get_account_summary
# ---------------------------------------------------------------------------
async def test_get_account_summary_reflects_seed_state(mcp_session):
    owner, token = await _seed_account_token(mcp_session, suffix="-as")
    inbox = (
        await InboxBuilder(
            mcp_session,
            InboxBuilderParams(
                account=owner.account,
                name="API",
                channel_type="api",
                channel_params={"webhook_url": "https://x.example.com"},
            ),
        ).perform()
    ).inbox
    contact = Contact(account_id=owner.account.id, name="X")
    mcp_session.add(contact)
    await mcp_session.flush()
    ci = await ContactInboxBuilder(
        session=mcp_session,
        contact=contact,
        inbox=inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    conv = await create_conversation(
        mcp_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    await create_message(
        mcp_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="hi", message_type="incoming"
        ),
        user_id=None,
    )
    await toggle_status(
        mcp_session, conversation=conv, status="resolved"
    )
    await mcp_session.commit()
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_account_summary", {"since_hours": 24}
        )
        body = _body(result)
        assert body["conversations_count"] == 1
        assert body["incoming_messages_count"] == 1
        assert body["resolutions_count"] == 1


async def test_get_account_summary_rejects_silly_window(mcp_session):
    owner, token = await _seed_account_token(mcp_session, suffix="-bw")
    await mcp_session.commit()
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="out of range"):
            await client.call_tool(
                "get_account_summary", {"since_hours": 100_000}
            )


# ---------------------------------------------------------------------------
# get_live_metrics
# ---------------------------------------------------------------------------
async def test_get_live_metrics_shape(mcp_session):
    owner, token = await _seed_account_token(mcp_session, suffix="-lm")
    inbox = (
        await InboxBuilder(
            mcp_session,
            InboxBuilderParams(
                account=owner.account,
                name="API",
                channel_type="api",
                channel_params={"webhook_url": "https://x.example.com"},
            ),
        ).perform()
    ).inbox
    contact = Contact(account_id=owner.account.id, name="X")
    mcp_session.add(contact)
    await mcp_session.flush()
    ci = await ContactInboxBuilder(
        session=mcp_session,
        contact=contact,
        inbox=inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    await create_conversation(
        mcp_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    await mcp_session.commit()
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool("get_live_metrics", {})
        body = _body(result)
        # Account-scoped — all four keys present.
        for key in ("open", "unattended", "unassigned", "pending"):
            assert key in body
        assert body["open"] == 1
