"""Integration tests for MCP contact tools."""

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
    create_conversation,
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


async def _seed_account_token(
    session: AsyncSession, *, suffix: str, scope: str = "write"
):
    owner = await AccountBuilder(
        session,
        AccountBuilderParams(
            email=f"admin{suffix}@mcpct.example.com",
            account_name=f"MCPCT{suffix}",
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
# list_contacts
# ---------------------------------------------------------------------------
async def test_list_contacts_no_query_returns_all_in_account(mcp_session):
    owner, token = await _seed_account_token(mcp_session, suffix="-li")
    for i, name in enumerate(["Alice", "Bob", "Carol"]):
        mcp_session.add(
            Contact(
                account_id=owner.account.id,
                name=name,
                email=f"{name.lower()}{i}@x.example.com",
            )
        )
    await mcp_session.commit()
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool("list_contacts", {})
        body = _body(result)
        names = {c["name"] for c in body["contacts"]}
        assert names == {"Alice", "Bob", "Carol"}


async def test_list_contacts_query_filters_ilike(mcp_session):
    owner, token = await _seed_account_token(mcp_session, suffix="-qy")
    mcp_session.add(
        Contact(
            account_id=owner.account.id,
            name="Diana",
            email="diana@enterprise.example.com",
        )
    )
    mcp_session.add(
        Contact(
            account_id=owner.account.id,
            name="Other",
            email="other@unrelated.example.com",
        )
    )
    await mcp_session.commit()
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "list_contacts", {"query": "enterprise"}
        )
        body = _body(result)
        names = {c["name"] for c in body["contacts"]}
        assert names == {"Diana"}


async def test_list_contacts_isolates_per_account(mcp_session):
    owner_a, token_a = await _seed_account_token(
        mcp_session, suffix="-ai"
    )
    owner_b, _ = await _seed_account_token(mcp_session, suffix="-bi")
    mcp_session.add(
        Contact(account_id=owner_b.account.id, name="OnlyOnB")
    )
    await mcp_session.commit()
    mcp_session._mcp_accts.append(owner_a.account.id)  # type: ignore[attr-defined]
    mcp_session._mcp_accts.append(owner_b.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token_a

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool("list_contacts", {})
        body = _body(result)
        names = {c["name"] for c in body["contacts"]}
        assert "OnlyOnB" not in names


# ---------------------------------------------------------------------------
# show_contact
# ---------------------------------------------------------------------------
async def test_show_contact(mcp_session):
    owner, token = await _seed_account_token(mcp_session, suffix="-sh")
    c = Contact(
        account_id=owner.account.id,
        name="Probe",
        email="probe@x.example.com",
    )
    mcp_session.add(c)
    await mcp_session.commit()
    await mcp_session.refresh(c)
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "show_contact", {"contact_id": c.id}
        )
        body = _body(result)
        assert body["name"] == "Probe"
        assert body["email"] == "probe@x.example.com"


async def test_show_contact_cross_account_404(mcp_session):
    owner_a, token_a = await _seed_account_token(
        mcp_session, suffix="-aa"
    )
    owner_b, _ = await _seed_account_token(mcp_session, suffix="-bb")
    c = Contact(account_id=owner_b.account.id, name="OtherB")
    mcp_session.add(c)
    await mcp_session.commit()
    await mcp_session.refresh(c)
    mcp_session._mcp_accts.append(owner_a.account.id)  # type: ignore[attr-defined]
    mcp_session._mcp_accts.append(owner_b.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token_a

    mcp = build_server()
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="not found in this account"):
            await client.call_tool(
                "show_contact", {"contact_id": c.id}
            )


# ---------------------------------------------------------------------------
# set_contact_custom_attribute
# ---------------------------------------------------------------------------
async def test_set_contact_custom_attribute_round_trips(mcp_session):
    owner, token = await _seed_account_token(mcp_session, suffix="-ca")
    c = Contact(account_id=owner.account.id, name="X")
    mcp_session.add(c)
    await mcp_session.commit()
    await mcp_session.refresh(c)
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        set_result = await client.call_tool(
            "set_contact_custom_attribute",
            {
                "contact_id": c.id,
                "key": "vip_tier",
                "value": "gold",
            },
        )
        body = _body(set_result)
        assert body["custom_attributes"]["vip_tier"] == "gold"

        # null value drops the key.
        drop_result = await client.call_tool(
            "set_contact_custom_attribute",
            {"contact_id": c.id, "key": "vip_tier", "value": None},
        )
        body = _body(drop_result)
        assert "vip_tier" not in body["custom_attributes"]


async def test_set_contact_custom_attribute_blocked_for_read_token(
    mcp_session,
):
    owner, token = await _seed_account_token(
        mcp_session, suffix="-rt", scope="read"
    )
    c = Contact(account_id=owner.account.id, name="X")
    mcp_session.add(c)
    await mcp_session.commit()
    await mcp_session.refresh(c)
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="requires 'write'"):
            await client.call_tool(
                "set_contact_custom_attribute",
                {"contact_id": c.id, "key": "x", "value": "y"},
            )


# ---------------------------------------------------------------------------
# set_conversation_custom_attribute
# ---------------------------------------------------------------------------
async def test_set_conversation_custom_attribute(mcp_session):
    owner, token = await _seed_account_token(mcp_session, suffix="-cv")
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
    c = Contact(account_id=owner.account.id, name="X")
    mcp_session.add(c)
    await mcp_session.flush()
    ci = await ContactInboxBuilder(
        session=mcp_session,
        contact=c,
        inbox=inbox,
        source_id=f"src-{c.id}",
    ).perform()
    conv = await create_conversation(
        mcp_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    await mcp_session.commit()
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "set_conversation_custom_attribute",
            {
                "conversation_id": conv.id,
                "key": "intent",
                "value": "refund_request",
            },
        )
        body = _body(result)
        assert body["custom_attributes"]["intent"] == "refund_request"
