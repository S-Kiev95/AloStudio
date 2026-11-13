"""MCP tools for the CRM sales pipeline (F11): pipelines, opportunities and
follow-up activities, scoped to the token's account."""

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
from app.domains.crm import service as crm_service
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
            email=f"admin{suffix}@mcpcrm.example.com",
            account_name=f"MCPCRM{suffix}",
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


async def test_opportunity_moves_through_the_pipeline(mcp_session):
    owner = await _account(mcp_session, "-deal")
    pipeline = await crm_service.save_pipeline(
        mcp_session, account_id=owner.account.id, pipeline=None, payload={"name": "Ventas"}
    )
    contact = Contact(account_id=owner.account.id, name="Ana")
    mcp_session.add(contact)
    await mcp_session.flush()
    await _use_token(mcp_session, owner)

    async with Client(build_server()) as client:
        (listed,) = _body(await client.call_tool("list_pipelines", {}))["pipelines"]
        assert listed["id"] == pipeline.id
        stages = listed["stages"]
        won = next(s for s in stages if s["kind"] == "won")

        deal = _body(
            await client.call_tool(
                "create_opportunity",
                {"title": "Curso de Excel para Ana", "contact_id": contact.id, "value": 2900},
            )
        )
        # Without a stage it lands in the first one, worked by the token's user.
        assert deal["stage_id"] == stages[0]["id"]
        assert deal["owner_id"] == owner.user.id

        deal = _body(
            await client.call_tool(
                "update_opportunity", {"opportunity_id": deal["id"], "stage_id": won["id"]}
            )
        )
        # A won stage closes it.
        assert deal["stage_id"] == won["id"]
        assert deal["closed_at"] is not None
        won_list = _body(await client.call_tool("list_opportunities", {"status": "won"}))
        assert [o["id"] for o in won_list["opportunities"]] == [deal["id"]]


async def test_follow_up_activities(mcp_session):
    owner = await _account(mcp_session, "-act")
    contact = Contact(account_id=owner.account.id, name="Ana")
    mcp_session.add(contact)
    await mcp_session.flush()
    await _use_token(mcp_session, owner)
    due = (datetime.now(UTC) + timedelta(days=1)).isoformat()

    async with Client(build_server()) as client:
        task = _body(
            await client.call_tool(
                "create_crm_activity",
                {"title": "Llamar a Ana", "kind": "call", "due_at": due, "contact_id": contact.id},
            )
        )
        pending = _body(await client.call_tool("list_crm_activities", {"status": "pending"}))
        assert [a["id"] for a in pending["activities"]] == [task["id"]]
        _body(await client.call_tool("update_crm_activity", {"activity_id": task["id"], "done": True}))
        done = _body(await client.call_tool("list_crm_activities", {"status": "done"}))
        assert [a["id"] for a in done["activities"]] == [task["id"]]


async def test_crm_tools_do_not_reach_another_account(mcp_session):
    owner = await _account(mcp_session, "-iso")
    other = await _account(mcp_session, "-iso-other")
    their_pipeline = await crm_service.save_pipeline(
        mcp_session, account_id=other.account.id, pipeline=None, payload={"name": "Ajeno"}
    )
    theirs = Contact(account_id=other.account.id, name="Ajeno")
    mcp_session.add(theirs)
    await mcp_session.flush()
    their_deal = await crm_service.save_opportunity(
        mcp_session,
        account_id=other.account.id,
        opportunity=None,
        payload={"title": "Ajena", "owner_id": other.user.id},
    )
    await _use_token(mcp_session, owner)

    async with Client(build_server()) as client:
        # The account gets its own default pipeline; never the other one's.
        pipelines = _body(await client.call_tool("list_pipelines", {}))["pipelines"]
        assert their_pipeline.id not in [p["id"] for p in pipelines]
        assert _body(await client.call_tool("list_opportunities", {}))["opportunities"] == []
        for tool, args in (
            ("create_opportunity", {"title": "x", "contact_id": theirs.id}),
            ("update_opportunity", {"opportunity_id": their_deal.id, "title": "x"}),
            ("create_crm_activity", {"title": "x", "contact_id": theirs.id}),
        ):
            with pytest.raises(ToolError):
                await client.call_tool(tool, args)
