"""Integration tests for MCP message tools."""

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
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
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


async def _seed(session: AsyncSession, *, suffix: str, scope: str = "write"):
    import secrets

    suffix = f"{suffix}-{secrets.token_hex(4)}"
    owner = await AccountBuilder(
        session,
        AccountBuilderParams(
            email=f"admin{suffix}@mcpm.example.com",
            account_name=f"MCPM{suffix}",
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
                name="API",
                channel_type="api",
                channel_params={"webhook_url": "https://x.example.com"},
            ),
        ).perform()
    ).inbox
    contact = Contact(account_id=owner.account.id, name="Diana")
    session.add(contact)
    await session.flush()
    ci = await ContactInboxBuilder(
        session=session,
        contact=contact,
        inbox=inbox,
        source_id=f"mcm-{contact.id}",
    ).perform()
    conv = await create_conversation(
        session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    token = await create_token(
        session,
        account_id=owner.account.id,
        name=f"agent{suffix}",
        scope=scope,
        user_id=owner.user.id,
    )
    await session.commit()
    session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    return owner, token.token, conv


def _body(result):
    return result.structured_content or result.data


# ---------------------------------------------------------------------------
# list_messages / show_message
# ---------------------------------------------------------------------------
async def test_list_messages_chronological_newest_first(mcp_session):
    _owner, token, conv = await _seed(mcp_session, suffix="-li")
    for i in range(3):
        await create_message(
            mcp_session,
            conversation=conv,
            params=MessageBuilderParams(
                content=f"m{i}", message_type="incoming"
            ),
            user_id=None,
        )
    await mcp_session.commit()
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "list_messages", {"conversation_id": conv.id}
        )
        msgs = _body(result)["messages"]
        contents = [m["content"] for m in msgs]
        # Newest first.
        assert contents == ["m2", "m1", "m0"]


async def test_list_messages_before_id_paginates_backward(mcp_session):
    _owner, token, conv = await _seed(mcp_session, suffix="-pg")
    seeded_ids = []
    for i in range(5):
        m = await create_message(
            mcp_session,
            conversation=conv,
            params=MessageBuilderParams(
                content=f"m{i}", message_type="incoming"
            ),
            user_id=None,
        )
        seeded_ids.append(m.id)
    await mcp_session.commit()
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        # Page 1: most recent 2.
        first = await client.call_tool(
            "list_messages",
            {"conversation_id": conv.id, "limit": 2},
        )
        first_msgs = _body(first)["messages"]
        assert len(first_msgs) == 2
        oldest_in_page1 = first_msgs[-1]["id"]
        # Page 2: walk backward.
        second = await client.call_tool(
            "list_messages",
            {
                "conversation_id": conv.id,
                "limit": 2,
                "before_id": oldest_in_page1,
            },
        )
        second_msgs = _body(second)["messages"]
        assert len(second_msgs) == 2
        assert second_msgs[0]["id"] < oldest_in_page1


async def test_show_message(mcp_session):
    _owner, token, conv = await _seed(mcp_session, suffix="-sh")
    msg = await create_message(
        mcp_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="probe", message_type="incoming"
        ),
        user_id=None,
    )
    await mcp_session.commit()
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "show_message", {"message_id": msg.id}
        )
        body = _body(result)
        assert body["content"] == "probe"
        assert body["message_type"] == "incoming"


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------
async def test_send_message_creates_outgoing_with_sender(mcp_session):
    owner, token, conv = await _seed(mcp_session, suffix="-sm")
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "send_message",
            {"conversation_id": conv.id, "content": "Hi from AI"},
        )
        body = _body(result)
        assert body["content"] == "Hi from AI"
        assert body["message_type"] == "outgoing"
        assert body["private"] is False
        assert body["sender_type"] == "User"
        assert body["sender_id"] == owner.user.id


async def test_send_message_rejects_blank_content(mcp_session):
    _owner, token, conv = await _seed(mcp_session, suffix="-bl")
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="content can't be blank"):
            await client.call_tool(
                "send_message",
                {"conversation_id": conv.id, "content": "   "},
            )


async def test_send_private_message(mcp_session):
    _owner, token, conv = await _seed(mcp_session, suffix="-pv")
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "send_message",
            {
                "conversation_id": conv.id,
                "content": "internal note",
                "private": True,
            },
        )
        body = _body(result)
        assert body["private"] is True


async def test_add_private_note_is_sugar(mcp_session):
    _owner, token, conv = await _seed(mcp_session, suffix="-pn")
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "add_private_note",
            {"conversation_id": conv.id, "content": "handoff"},
        )
        body = _body(result)
        assert body["private"] is True
        assert body["content"] == "handoff"


# ---------------------------------------------------------------------------
# Permissions + isolation
# ---------------------------------------------------------------------------
async def test_send_message_blocked_for_read_token(mcp_session):
    _owner, token, conv = await _seed(
        mcp_session, suffix="-rd", scope="read"
    )
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="requires 'write'"):
            await client.call_tool(
                "send_message",
                {"conversation_id": conv.id, "content": "blocked"},
            )


async def test_send_message_cross_account_404(mcp_session):
    _owner_a, token_a, _ = await _seed(mcp_session, suffix="-ax")
    _owner_b, _, conv_b = await _seed(mcp_session, suffix="-bx")
    os.environ["MCP_BEARER_TOKEN"] = token_a

    mcp = build_server()
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="not found in this account"):
            await client.call_tool(
                "send_message",
                {"conversation_id": conv_b.id, "content": "x"},
            )
