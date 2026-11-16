"""F4 low priority — configuration tools behind the ``admin`` scope:
automation rules, webhooks, business hours, autoposts, plugs, Help Center
articles, and merging / blocking contacts."""

from __future__ import annotations

import os
import secrets
from collections.abc import AsyncIterator

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
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.portals.models import Portal
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
            email=f"admin{suffix}@mcpf4b.example.com",
            account_name=f"MCPF4B{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    return owner


async def _use_token(session: AsyncSession, owner, scope: str = "admin") -> None:
    token = await create_token(
        session,
        account_id=owner.account.id,
        name=f"agent-{secrets.token_hex(3)}",
        scope=scope,
        user_id=owner.user.id,
    )
    await session.commit()
    os.environ["MCP_BEARER_TOKEN"] = token.token


async def _api_inbox(session: AsyncSession, owner):
    return (
        await InboxBuilder(
            session,
            InboxBuilderParams(account=owner.account, name="API", channel_type="api", channel_params={}),
        ).perform()
    ).inbox


def _body(result):
    return result.structured_content or result.data


async def test_configuration_needs_an_admin_token(mcp_session):
    owner = await _account(mcp_session, "-scope")
    await _use_token(mcp_session, owner, scope="write")
    async with Client(build_server()) as client:
        with pytest.raises(ToolError) as exc:
            await client.call_tool("list_automation_rules", {})
    assert "admin" in str(exc.value)


async def test_automation_rule_lifecycle(mcp_session):
    owner = await _account(mcp_session, "-rule")
    await _use_token(mcp_session, owner)
    async with Client(build_server()) as client:
        rule = _body(
            await client.call_tool(
                "create_automation_rule",
                {
                    "name": "Etiquetar nuevas",
                    "event_name": "conversation_created",
                    "conditions": [
                        {
                            "attribute_key": "status",
                            "filter_operator": "equal_to",
                            "values": ["open"],
                            "query_operator": None,
                        }
                    ],
                    "actions": [{"action_name": "add_label", "action_params": ["nueva"]}],
                },
            )
        )
        rules = _body(await client.call_tool("list_automation_rules", {}))["rules"]
        assert [r["name"] for r in rules] == ["Etiquetar nuevas"]
        paused = _body(
            await client.call_tool("update_automation_rule", {"rule_id": rule["id"], "active": False})
        )
        assert paused["active"] is False
        await client.call_tool("delete_automation_rule", {"rule_id": rule["id"]})
        assert _body(await client.call_tool("list_automation_rules", {}))["rules"] == []


async def test_webhooks_and_business_hours(mcp_session):
    owner = await _account(mcp_session, "-hooks")
    other = await _account(mcp_session, "-hooks-other")
    inbox = await _api_inbox(mcp_session, owner)
    foreign = await _api_inbox(mcp_session, other)
    await _use_token(mcp_session, owner)

    async with Client(build_server()) as client:
        hook = _body(
            await client.call_tool(
                "create_webhook",
                {"url": "https://hooks.example.com/alo", "subscriptions": ["message_created"]},
            )
        )
        assert hook["secret"]
        with pytest.raises(ToolError):
            await client.call_tool(
                "create_webhook",
                {
                    "url": "https://hooks.example.com/otra",
                    "subscriptions": ["message_created"],
                    "inbox_id": foreign.id,
                },
            )
        assert len(_body(await client.call_tool("list_webhooks", {}))["webhooks"]) == 1
        await client.call_tool("delete_webhook", {"webhook_id": hook["id"]})

        hours = _body(await client.call_tool("get_working_hours", {"inbox_id": inbox.id}))
        assert len(hours["working_hours"]) == 7
        changed = _body(
            await client.call_tool(
                "set_working_hours",
                {
                    "inbox_id": inbox.id,
                    "schedule": [{"day_of_week": 1, "open_hour": 8, "open_minutes": 30}],
                },
            )
        )
        monday = next(h for h in changed["working_hours"] if h["day_of_week"] == 1)
        assert (monday["open_hour"], monday["open_minutes"]) == (8, 30)
        assert _body(await client.call_tool("list_autoposts", {}))["autoposts"] == []
        assert _body(await client.call_tool("list_plugs", {}))["plugs"] == []


async def test_help_center_articles(mcp_session):
    owner = await _account(mcp_session, "-hc")
    portal = Portal(
        account_id=owner.account.id, name="Ayuda", slug=f"ayuda-{secrets.token_hex(4)}"
    )
    mcp_session.add(portal)
    await mcp_session.flush()
    await _use_token(mcp_session, owner)

    async with Client(build_server()) as client:
        centers = _body(await client.call_tool("list_help_centers", {}))["help_centers"]
        assert [c["slug"] for c in centers] == [portal.slug]
        article = _body(
            await client.call_tool(
                "create_article",
                {
                    "portal_slug": portal.slug,
                    "title": "Cómo inscribirse",
                    "content": "Completá el formulario en la web.",
                },
            )
        )
        assert article["status"] == "draft"
        published = _body(
            await client.call_tool(
                "update_article",
                {"portal_slug": portal.slug, "article_id": article["id"], "status": "published"},
            )
        )
        assert published["status"] == "published"
        found = _body(
            await client.call_tool(
                "list_articles", {"portal_slug": portal.slug, "query": "inscribirse"}
            )
        )["articles"]
        assert [a["id"] for a in found] == [article["id"]]
        with pytest.raises(ToolError):
            await client.call_tool(
                "create_article",
                {"portal_slug": "no-existe", "title": "x", "content": "y"},
            )


async def test_merge_and_block_contacts(mcp_session):
    owner = await _account(mcp_session, "-merge")
    other = await _account(mcp_session, "-merge-other")
    base = Contact(account_id=owner.account.id, name="Ana", email="ana@x.example.com")
    dup = Contact(account_id=owner.account.id, name="Ana P", phone_number="+59899555444")
    theirs = Contact(account_id=other.account.id, name="Ajena")
    mcp_session.add_all([base, dup, theirs])
    await mcp_session.flush()
    await _use_token(mcp_session, owner)

    async with Client(build_server()) as client:
        merged = _body(
            await client.call_tool(
                "merge_contacts", {"base_contact_id": base.id, "mergee_contact_id": dup.id}
            )
        )
        assert merged["id"] == base.id
        assert merged["phone_number"] == "+59899555444"
        blocked = _body(
            await client.call_tool("set_contact_blocked", {"contact_id": base.id, "blocked": True})
        )
        assert blocked["blocked"] is True
        with pytest.raises(ToolError):
            await client.call_tool(
                "merge_contacts", {"base_contact_id": base.id, "mergee_contact_id": theirs.id}
            )
