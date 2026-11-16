"""F4 medium priority — catalogue, appointments, macros, reports, CSAT,
campaigns and the publishing presets, all scoped to the token's account."""

from __future__ import annotations

import os
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from sqlalchemy import NullPool, delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.models_registry import import_all_models
from app.domains.accounts.models import Account
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.conversations.models import Conversation
from app.domains.inboxes.models import WHATSAPP_PROVIDER_CLOUD
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.macros.models import MACRO_VISIBILITY_GLOBAL, Macro
from app.domains.products.models import Product
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
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    created: list[int] = []
    try:
        sm = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
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


async def _account(session: AsyncSession, suffix: str):
    suffix = f"{suffix}-{secrets.token_hex(4)}"
    owner = await AccountBuilder(
        session,
        AccountBuilderParams(
            email=f"admin{suffix}@mcpf4m.example.com",
            account_name=f"MCPF4M{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    return owner


async def _use_token(session: AsyncSession, owner) -> None:
    token = await create_token(
        session,
        account_id=owner.account.id,
        name=f"agent-{secrets.token_hex(3)}",
        scope="write",
        user_id=owner.user.id,
    )
    await session.commit()
    os.environ["MCP_BEARER_TOKEN"] = token.token


def _body(result):
    return result.structured_content or result.data


async def test_products_and_rescheduling(mcp_session):
    owner = await _account(mcp_session, "-cat")
    contact = Contact(account_id=owner.account.id, name="Cliente")
    mcp_session.add(contact)
    await mcp_session.flush()
    await _use_token(mcp_session, owner)
    start = datetime.now(UTC) + timedelta(days=2)

    async with Client(build_server()) as client:
        product = _body(
            await client.call_tool(
                "create_product",
                {"name": "Curso de Excel", "price": 2900, "currency": "UYU"},
            )
        )
        product = _body(
            await client.call_tool(
                "update_product", {"product_id": product["id"], "price": 3100}
            )
        )
        assert float(product["price"]) == 3100
        appt = _body(
            await client.call_tool(
                "create_appointment",
                {
                    "contact_id": contact.id,
                    "title": "Entrevista",
                    "starts_at": start.isoformat(),
                    "product_id": product["id"],
                },
            )
        )
        moved = start + timedelta(days=1)
        appt = _body(
            await client.call_tool(
                "update_appointment",
                {"appointment_id": appt["id"], "starts_at": moved.isoformat()},
            )
        )
        assert appt["starts_at"] is not None
        assert appt["title"] == "Entrevista"


async def test_macros_run_on_the_accounts_conversations(mcp_session):
    owner = await _account(mcp_session, "-macro")
    inbox = (
        await InboxBuilder(
            mcp_session,
            InboxBuilderParams(account=owner.account, name="API", channel_type="api", channel_params={}),
        ).perform()
    ).inbox
    contact = Contact(account_id=owner.account.id, name="Cliente")
    mcp_session.add(contact)
    macro = Macro(
        account_id=owner.account.id,
        name="Marcar VIP",
        visibility=MACRO_VISIBILITY_GLOBAL,
        created_by_id=owner.user.id,
        actions=[{"action_name": "add_label", "action_params": ["vip"]}],
    )
    mcp_session.add(macro)
    await mcp_session.flush()
    await _use_token(mcp_session, owner)

    async with Client(build_server()) as client:
        conv = _body(
            await client.call_tool(
                "create_conversation", {"inbox_id": inbox.id, "contact_id": contact.id}
            )
        )
        macros = _body(await client.call_tool("list_macros", {}))["macros"]
        assert [m["name"] for m in macros] == ["Marcar VIP"]
        ran = _body(
            await client.call_tool(
                "execute_macro", {"macro_id": macro.id, "conversation_ids": [conv["id"]]}
            )
        )
        assert ran["conversations"] == 1

    row = await mcp_session.get(Conversation, conv["id"])
    await mcp_session.refresh(row)
    assert "vip" in (row.cached_label_list or "")


async def test_reports_and_csat_answer(mcp_session):
    owner = await _account(mcp_session, "-rep")
    await _use_token(mcp_session, owner)
    async with Client(build_server()) as client:
        for group_by in ("agent", "team", "inbox"):
            report = _body(await client.call_tool("get_report_by", {"group_by": group_by}))
            assert report["group_by"] == group_by
            assert isinstance(report["rows"], list)
        csat = _body(await client.call_tool("get_csat", {}))
        assert "metrics" in csat and csat["responses"] == []
        with pytest.raises(ToolError):
            await client.call_tool("get_report_by", {"group_by": "agent", "from": "ayer"})


async def test_whatsapp_campaign_needs_a_template_and_own_contacts(mcp_session):
    owner = await _account(mcp_session, "-camp")
    other = await _account(mcp_session, "-camp-other")
    inbox = (
        await InboxBuilder(
            mcp_session,
            InboxBuilderParams(
                account=owner.account,
                name="WA",
                channel_type="whatsapp",
                channel_params={
                    "phone_number": f"+5984{secrets.randbelow(10**7):07d}",
                    "provider": WHATSAPP_PROVIDER_CLOUD,
                    "provider_config": {"api_key": "t", "phone_number_id": "pc", "business_account_id": "b"},
                },
            ),
        ).perform()
    ).inbox
    mine = Contact(account_id=owner.account.id, name="Ana", phone_number="+59899000001")
    theirs = Contact(account_id=other.account.id, name="Ajeno", phone_number="+59899000002")
    mcp_session.add_all([mine, theirs])
    await mcp_session.flush()
    await _use_token(mcp_session, owner)
    when = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    base = {
        "title": "Inscripciones",
        "inbox_id": inbox.id,
        "message": "Abrimos inscripciones",
        "scheduled_at": when,
    }

    async with Client(build_server()) as client:
        with pytest.raises(ToolError) as exc:
            await client.call_tool("create_campaign", {**base, "contact_ids": [mine.id]})
        assert "template" in str(exc.value)
        with pytest.raises(ToolError) as exc:
            await client.call_tool(
                "create_campaign",
                {**base, "contact_ids": [mine.id, theirs.id], "template_name": "aviso", "template_language": "es"},
            )
        assert str(theirs.id) in str(exc.value)
        campaign = _body(
            await client.call_tool(
                "create_campaign",
                {
                    **base,
                    "contact_ids": [mine.id],
                    "template_name": "aviso",
                    "template_language": "es",
                    "template_params": ["Ana"],
                },
            )
        )
        assert campaign["campaign_type"] == "one_off"
        assert campaign["audience"] == [{"type": "Contact", "id": mine.id}]
        listed = _body(await client.call_tool("list_campaigns", {}))["campaigns"]
        assert [c["title"] for c in listed] == ["Inscripciones"]
        result = _body(await client.call_tool("get_campaign_result", {"campaign_id": campaign["id"]}))
        assert result["campaign"]["id"] == campaign["id"]


async def test_publishing_presets_and_networks(mcp_session):
    owner = await _account(mcp_session, "-presets")
    await _use_token(mcp_session, owner)
    async with Client(build_server()) as client:
        networks = _body(await client.call_tool("list_publishing_networks", {}))["networks"]
        assert networks and all("fields" not in n for n in networks)
        assert _body(await client.call_tool("list_signatures", {}))["signatures"] == []
        assert _body(await client.call_tool("list_publication_sets", {}))["sets"] == []


async def test_medium_tools_do_not_reach_another_account(mcp_session):
    owner = await _account(mcp_session, "-iso")
    other = await _account(mcp_session, "-iso-other")
    product = Product(account_id=other.account.id, name="Ajeno")
    macro = Macro(
        account_id=other.account.id,
        name="Ajena",
        visibility=MACRO_VISIBILITY_GLOBAL,
        created_by_id=other.user.id,
        actions=[],
    )
    mcp_session.add_all([product, macro])
    await mcp_session.flush()
    await _use_token(mcp_session, owner)

    async with Client(build_server()) as client:
        for tool, args in (
            ("update_product", {"product_id": product.id, "name": "x"}),
            ("execute_macro", {"macro_id": macro.id, "conversation_ids": [1]}),
            ("get_campaign_result", {"campaign_id": 1}),
        ):
            with pytest.raises(ToolError):
                await client.call_tool(tool, args)
        assert _body(await client.call_tool("list_macros", {}))["macros"] == []
