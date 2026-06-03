"""Integration tests for MCP conversation tools.

Pattern follows test_mcp_server.py — commit-friendly fixture so the
MCP middleware's separate session can see seeded state.
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
    created_accounts: list[int] = []
    try:
        sessionmaker = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        async with sessionmaker() as session:
            session._mcp_accts = created_accounts  # type: ignore[attr-defined]
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


async def _seed(session: AsyncSession, *, suffix: str, scope: str = "write"):
    """Seed account + token + one inbox + one conversation. Returns
    (owner, token, conversation)."""
    import secrets

    suffix = f"{suffix}-{secrets.token_hex(4)}"
    owner = await AccountBuilder(
        session,
        AccountBuilderParams(
            email=f"admin{suffix}@mcpc.example.com",
            account_name=f"MCPC{suffix}",
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
        source_id=f"mcp-src-{contact.id}",
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


def _call(client: Client, name: str, **kwargs):
    return client.call_tool(name, kwargs)


# ---------------------------------------------------------------------------
# list_conversations
# ---------------------------------------------------------------------------
async def test_list_conversations_returns_account_scope(mcp_session):
    owner, token, conv = await _seed(mcp_session, suffix="-li")
    os.environ["MCP_BEARER_TOKEN"] = token
    mcp = build_server()
    async with Client(mcp) as client:
        result = await _call(client, "list_conversations")
        body = result.structured_content or result.data
        assert len(body["conversations"]) == 1
        assert body["conversations"][0]["id"] == conv.id
        assert body["conversations"][0]["status"] == "open"


async def test_list_conversations_filters_by_status(mcp_session):
    owner, token, conv = await _seed(mcp_session, suffix="-fs")
    os.environ["MCP_BEARER_TOKEN"] = token
    mcp = build_server()
    async with Client(mcp) as client:
        result = await _call(
            client, "list_conversations", status="resolved"
        )
        body = result.structured_content or result.data
        assert body["conversations"] == []


# ---------------------------------------------------------------------------
# show_conversation
# ---------------------------------------------------------------------------
async def test_show_conversation_includes_message_tail(mcp_session):
    owner, token, conv = await _seed(mcp_session, suffix="-sh")
    # Add a couple of messages.
    await create_message(
        mcp_session,
        conversation=conv,
        params=MessageBuilderParams(content="hi", message_type="incoming"),
        user_id=None,
    )
    await create_message(
        mcp_session,
        conversation=conv,
        params=MessageBuilderParams(
            content="how can I help?", message_type="outgoing"
        ),
        user_id=owner.user.id,
    )
    await mcp_session.commit()
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await _call(
            client, "show_conversation", conversation_id=conv.id
        )
        body = result.structured_content or result.data
        assert body["id"] == conv.id
        assert len(body["messages"]) == 2
        # Chronological order.
        assert body["messages"][0]["content"] == "hi"
        assert body["messages"][1]["content"] == "how can I help?"


async def test_show_conversation_404_across_accounts(mcp_session):
    """A token's account scope must isolate conversations from
    other accounts."""
    owner_a, token_a, _conv_a = await _seed(mcp_session, suffix="-aa")
    owner_b, _token_b, conv_b = await _seed(mcp_session, suffix="-bb")
    os.environ["MCP_BEARER_TOKEN"] = token_a
    mcp = build_server()
    with pytest.raises(Exception, match="not found in this account"):
        async with Client(mcp) as client:
            await _call(
                client,
                "show_conversation",
                conversation_id=conv_b.id,
            )


# ---------------------------------------------------------------------------
# resolve / reopen / change_status / change_priority
# ---------------------------------------------------------------------------
async def test_resolve_conversation_flips_status(mcp_session):
    owner, token, conv = await _seed(mcp_session, suffix="-rs")
    os.environ["MCP_BEARER_TOKEN"] = token
    mcp = build_server()
    async with Client(mcp) as client:
        result = await _call(
            client, "resolve_conversation", conversation_id=conv.id
        )
        body = result.structured_content or result.data
        assert body["status"] == "resolved"


async def test_change_priority(mcp_session):
    owner, token, conv = await _seed(mcp_session, suffix="-cp")
    os.environ["MCP_BEARER_TOKEN"] = token
    mcp = build_server()
    async with Client(mcp) as client:
        result = await _call(
            client,
            "change_priority",
            conversation_id=conv.id,
            priority="urgent",
        )
        body = result.structured_content or result.data
        assert body["priority"] == "urgent"


# ---------------------------------------------------------------------------
# add_label / remove_label
# ---------------------------------------------------------------------------
async def test_add_label_then_remove_label(mcp_session):
    owner, token, conv = await _seed(mcp_session, suffix="-lb")
    os.environ["MCP_BEARER_TOKEN"] = token
    mcp = build_server()
    async with Client(mcp) as client:
        added = await _call(
            client,
            "add_label",
            conversation_id=conv.id,
            labels=["refund", "priority"],
        )
        body = added.structured_content or added.data
        assert set(body["labels"]) == {"refund", "priority"}

        dropped = await _call(
            client,
            "remove_label",
            conversation_id=conv.id,
            labels=["priority"],
        )
        body = dropped.structured_content or dropped.data
        assert body["labels"] == ["refund"]


# ---------------------------------------------------------------------------
# get_ai_mode / set_ai_mode
# ---------------------------------------------------------------------------
async def test_ai_mode_defaults_off_and_round_trips(mcp_session):
    """v2.8: ``ai_mode`` is a real bool column; default is ``false``
    (no AI in charge). ``set_ai_mode(on=true, ai_assignee=...)`` flips
    both fields and the next ``get_ai_mode`` reflects them."""
    owner, token, conv = await _seed(mcp_session, suffix="-ai")
    os.environ["MCP_BEARER_TOKEN"] = token
    mcp = build_server()
    async with Client(mcp) as client:
        initial = await _call(
            client, "get_ai_mode", conversation_id=conv.id
        )
        body = initial.structured_content or initial.data
        assert body["ai_mode"] is False
        assert body["ai_assignee"] is None

        await _call(
            client,
            "set_ai_mode",
            conversation_id=conv.id,
            on=True,
            ai_assignee="alicia-v3",
        )
        after = await _call(
            client, "get_ai_mode", conversation_id=conv.id
        )
        body = after.structured_content or after.data
        assert body["ai_mode"] is True
        assert body["ai_assignee"] == "alicia-v3"

        # Hand back to humans — empty string clears the slot.
        await _call(
            client,
            "set_ai_mode",
            conversation_id=conv.id,
            on=False,
            ai_assignee="",
        )
        back = await _call(
            client, "get_ai_mode", conversation_id=conv.id
        )
        body = back.structured_content or back.data
        assert body["ai_mode"] is False
        assert body["ai_assignee"] is None


# ---------------------------------------------------------------------------
# Permission scope
# ---------------------------------------------------------------------------
async def test_read_token_cannot_resolve(mcp_session):
    """A read-only token can list but can't resolve."""
    owner, token, conv = await _seed(
        mcp_session, suffix="-rt", scope="read"
    )
    os.environ["MCP_BEARER_TOKEN"] = token
    mcp = build_server()
    async with Client(mcp) as client:
        # List works.
        list_result = await _call(client, "list_conversations")
        assert list_result.structured_content or list_result.data
        # Resolve fails.
        with pytest.raises(Exception, match="requires 'write'"):
            await _call(
                client,
                "resolve_conversation",
                conversation_id=conv.id,
            )


async def test_read_token_can_get_but_not_set_ai_mode(mcp_session):
    """v2.8: ``get_ai_mode`` is read-scope (observability) but
    ``set_ai_mode`` is write-scope — a misconfigured read-only token
    must not be able to flip the AI takeover flag."""
    owner, token, conv = await _seed(
        mcp_session, suffix="-airead", scope="read"
    )
    os.environ["MCP_BEARER_TOKEN"] = token
    mcp = build_server()
    async with Client(mcp) as client:
        # GET works — read-scope is sufficient.
        body = (
            await _call(client, "get_ai_mode", conversation_id=conv.id)
        ).structured_content
        assert body is not None
        assert body["ai_mode"] is False
        # SET fails on permission.
        with pytest.raises(Exception, match="requires 'write'"):
            await _call(
                client,
                "set_ai_mode",
                conversation_id=conv.id,
                on=True,
            )


async def test_assign_agent_to_owner_user(mcp_session):
    """assign_agent with a valid user_id of the account succeeds."""
    owner, token, conv = await _seed(mcp_session, suffix="-aa2")
    os.environ["MCP_BEARER_TOKEN"] = token
    mcp = build_server()
    async with Client(mcp) as client:
        result = await _call(
            client,
            "assign_agent",
            conversation_id=conv.id,
            agent_id=owner.user.id,
        )
        body = result.structured_content or result.data
        assert body["assignee_id"] == owner.user.id
