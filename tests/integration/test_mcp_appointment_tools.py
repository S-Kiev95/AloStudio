"""Integration tests for MCP appointment & product tools."""

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
from app.domains.contacts.models import Contact
from app.domains.products import service as psvc
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


async def _seed_account_token(
    session: AsyncSession, *, suffix: str, scope: str = "write"
):
    suffix = f"{suffix}-{secrets.token_hex(4)}"
    owner = await AccountBuilder(
        session,
        AccountBuilderParams(
            email=f"admin{suffix}@mcpap.example.com",
            account_name=f"MCPAP{suffix}",
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


async def test_mcp_list_products_filters_enabled(mcp_session):
    owner, token = await _seed_account_token(
        mcp_session, suffix="-lp", scope="read"
    )
    await psvc.create_product(
        mcp_session,
        account_id=owner.account.id,
        payload={"name": "Activo", "enabled": True},
    )
    await psvc.create_product(
        mcp_session,
        account_id=owner.account.id,
        payload={"name": "Inactivo", "enabled": False},
    )
    await mcp_session.commit()
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        res_all = await client.call_tool("list_products", {})
        assert len(_body(res_all)["products"]) == 2

        res_on = await client.call_tool("list_products", {"enabled": True})
        assert [p["name"] for p in _body(res_on)["products"]] == ["Activo"]


async def test_mcp_create_list_and_update_appointment_status(mcp_session):
    owner, token = await _seed_account_token(mcp_session, suffix="-ca")
    contact = Contact(
        account_id=owner.account.id,
        name="Valentina",
        email="val@example.com",
    )
    mcp_session.add(contact)
    prod = await psvc.create_product(
        mcp_session,
        account_id=owner.account.id,
        payload={"name": "Limpieza", "price": 900, "currency": "UYU"},
    )
    await mcp_session.commit()
    await mcp_session.refresh(contact)
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token

    t_start = datetime(2026, 11, 5, 14, 0, tzinfo=UTC)
    t_end = t_start + timedelta(minutes=45)

    mcp = build_server()
    async with Client(mcp) as client:
        created = _body(
            await client.call_tool(
                "create_appointment",
                {
                    "contact_id": contact.id,
                    "product_id": prod.id,
                    "title": "Turno limpieza",
                    "starts_at": t_start.isoformat(),
                    "ends_at": t_end.isoformat(),
                    "notes": "Confirmar 24h antes",
                },
            )
        )
        assert created["title"] == "Turno limpieza"
        assert created["status"] == "scheduled"
        assert created["contact"]["id"] == contact.id
        assert created["product"]["id"] == prod.id

        listed = _body(
            await client.call_tool(
                "list_appointments",
                {
                    "from": (t_start - timedelta(hours=1)).isoformat(),
                    "to": (t_start + timedelta(hours=1)).isoformat(),
                    "contact_id": contact.id,
                    "status": "scheduled",
                },
            )
        )
        assert [a["id"] for a in listed["appointments"]] == [created["id"]]

        updated = _body(
            await client.call_tool(
                "update_appointment_status",
                {
                    "appointment_id": created["id"],
                    "status": "confirmed",
                },
            )
        )
        assert updated["status"] == "confirmed"


async def test_mcp_create_appointment_blocked_for_read_token(mcp_session):
    owner, token = await _seed_account_token(
        mcp_session, suffix="-ro", scope="read"
    )
    contact = Contact(account_id=owner.account.id, name="R")
    mcp_session.add(contact)
    await mcp_session.commit()
    await mcp_session.refresh(contact)
    mcp_session._mcp_accts.append(owner.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token

    mcp = build_server()
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="requires 'write'"):
            await client.call_tool(
                "create_appointment",
                {
                    "contact_id": contact.id,
                    "title": "Intento",
                    "starts_at": "2026-11-05T14:00:00Z",
                },
            )


async def test_mcp_cross_account_isolation(mcp_session):
    owner_a, token_a = await _seed_account_token(mcp_session, suffix="-isoA")
    owner_b, _ = await _seed_account_token(mcp_session, suffix="-isoB")
    contact_b = Contact(account_id=owner_b.account.id, name="Ajeno")
    mcp_session.add(contact_b)
    await mcp_session.commit()
    await mcp_session.refresh(contact_b)
    mcp_session._mcp_accts.append(owner_a.account.id)  # type: ignore[attr-defined]
    mcp_session._mcp_accts.append(owner_b.account.id)  # type: ignore[attr-defined]
    os.environ["MCP_BEARER_TOKEN"] = token_a

    mcp = build_server()
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="contacto"):
            await client.call_tool(
                "create_appointment",
                {
                    "contact_id": contact_b.id,
                    "title": "Cruzado",
                    "starts_at": "2026-11-05T14:00:00Z",
                },
            )
