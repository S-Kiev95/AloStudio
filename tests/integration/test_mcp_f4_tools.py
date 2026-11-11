"""F4 — MCP tools an agent needs to work without getting stuck.

Account lookups (inboxes, agents, teams, canned responses), contacts,
starting conversations, attachments and WhatsApp templates, and the
publication/media tools. Every lookup is scoped to the token's account.
"""

from __future__ import annotations

import io
import os
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError
from PIL import Image
from sqlalchemy import NullPool, delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.models_registry import import_all_models
from app.domains.accounts.models import Account
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.canned_responses.models import CannedResponse
from app.domains.contacts.models import Contact
from app.domains.conversations.models import Attachment, Message
from app.domains.inboxes.models import WHATSAPP_PROVIDER_CLOUD
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.media_library import service as media_svc
from app.domains.publishing import service as pub_svc
from app.domains.teams.models import Team
from app.mcp.server import build_server
from app.mcp.service import create_token
from tests.integration._publishing import channel_id_of

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
            email=f"admin{suffix}@mcpf4.example.com",
            account_name=f"MCPF4{suffix}",
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


async def _inbox(session: AsyncSession, owner, channel_type: str, params: dict, name: str):
    return (
        await InboxBuilder(
            session,
            InboxBuilderParams(
                account=owner.account,
                name=name,
                channel_type=channel_type,
                channel_params=params,
                enable_auto_assignment=False,
            ),
        ).perform()
    ).inbox


def _body(result):
    return result.structured_content or result.data


# ---------------------------------------------------------------------------
# Account lookups
# ---------------------------------------------------------------------------
async def test_lookups_list_only_this_account(mcp_session):
    owner = await _account(mcp_session, "-look")
    other = await _account(mcp_session, "-look-other")
    await _inbox(mcp_session, owner, "api", {}, "Mine")
    await _inbox(mcp_session, other, "api", {}, "Theirs")
    mcp_session.add(Team(account_id=owner.account.id, name="Ventas"))
    mcp_session.add(Team(account_id=other.account.id, name="Otro equipo"))
    mcp_session.add(
        CannedResponse(account_id=owner.account.id, short_code="hola", content="¡Hola! ¿En qué te ayudo?")
    )
    await _use_token(mcp_session, owner)

    async with Client(build_server()) as client:
        inboxes = _body(await client.call_tool("list_inboxes", {}))["inboxes"]
        agents = _body(await client.call_tool("list_agents", {}))["agents"]
        teams = _body(await client.call_tool("list_teams", {}))["teams"]
        canned = _body(await client.call_tool("list_canned_responses", {"search": "hola"}))

    assert [i["name"] for i in inboxes] == ["Mine"]
    assert [a["email"] for a in agents] == [owner.user.email]
    assert agents[0]["role"] == "administrator"
    assert [t["name"] for t in teams] == ["Ventas"]
    assert canned["canned_responses"][0]["short_code"] == "hola"


async def test_create_label_reports_a_duplicate_clearly(mcp_session):
    owner = await _account(mcp_session, "-label")
    await _use_token(mcp_session, owner)
    async with Client(build_server()) as client:
        created = _body(await client.call_tool("create_label", {"title": "urgente"}))
        assert created["title"] == "urgente"
        with pytest.raises(ToolError) as exc:
            await client.call_tool("create_label", {"title": "urgente"})
    # The service's own message, not "422: {...}".
    assert "422" not in str(exc.value)


# ---------------------------------------------------------------------------
# Contacts and conversations
# ---------------------------------------------------------------------------
async def test_create_and_update_contact(mcp_session):
    owner = await _account(mcp_session, "-contact")
    await _use_token(mcp_session, owner)
    async with Client(build_server()) as client:
        created = _body(
            await client.call_tool(
                "create_contact",
                {"name": "Ana Pérez", "email": "ana@cliente.example.com", "phone_number": "+59899111222"},
            )
        )
        assert created["phone_number"] == "+59899111222"
        updated = _body(
            await client.call_tool(
                "update_contact", {"contact_id": created["id"], "name": "Ana P."}
            )
        )
        assert updated["name"] == "Ana P."
        assert updated["email"] == "ana@cliente.example.com"
        with pytest.raises(ToolError):
            await client.call_tool(
                "create_contact", {"name": "Otra Ana", "email": "ana@cliente.example.com"}
            )


async def test_create_conversation_with_message_and_assignee(mcp_session):
    owner = await _account(mcp_session, "-conv")
    other = await _account(mcp_session, "-conv-other")
    inbox = await _inbox(mcp_session, owner, "api", {}, "API")
    contact = Contact(account_id=owner.account.id, name="Cliente")
    mcp_session.add(contact)
    await mcp_session.flush()
    await _use_token(mcp_session, owner)

    async with Client(build_server()) as client:
        conv = _body(
            await client.call_tool(
                "create_conversation",
                {
                    "inbox_id": inbox.id,
                    "contact_id": contact.id,
                    "message": "Hola, te escribimos por tu consulta",
                    "assignee_id": owner.user.id,
                },
            )
        )
        messages = _body(
            await client.call_tool("list_messages", {"conversation_id": conv["id"]})
        )["messages"]
        assert [m["content"] for m in messages] == ["Hola, te escribimos por tu consulta"]

        # Someone from another account can't be the assignee.
        with pytest.raises(ToolError):
            await client.call_tool(
                "create_conversation",
                {"inbox_id": inbox.id, "contact_id": contact.id, "assignee_id": other.user.id},
            )


async def test_create_conversation_follows_each_channels_rules(mcp_session):
    owner = await _account(mcp_session, "-rules")
    wa = await _inbox(
        mcp_session,
        owner,
        "whatsapp",
        {
            "phone_number": f"+5984{secrets.randbelow(10**7):07d}",
            "provider": WHATSAPP_PROVIDER_CLOUD,
            "provider_config": {"api_key": "t", "phone_number_id": "p", "business_account_id": "b"},
        },
        "WA",
    )
    ig = await _inbox(
        mcp_session,
        owner,
        "instagram",
        {"instagram_id": f"1784{secrets.randbelow(10**10):010d}", "access_token": "t"},
        "IG",
    )
    no_phone = Contact(account_id=owner.account.id, name="Sin teléfono")
    with_phone = Contact(account_id=owner.account.id, name="Con teléfono", phone_number="+59899123456")
    mcp_session.add_all([no_phone, with_phone])
    await mcp_session.flush()
    await _use_token(mcp_session, owner)

    async with Client(build_server()) as client:
        with pytest.raises(ToolError) as exc:
            await client.call_tool(
                "create_conversation", {"inbox_id": wa.id, "contact_id": no_phone.id}
            )
        assert "phone" in str(exc.value)
        conv = _body(
            await client.call_tool(
                "create_conversation", {"inbox_id": wa.id, "contact_id": with_phone.id}
            )
        )
        assert conv["inbox_id"] == wa.id
        # Instagram only lets a business answer someone who wrote first.
        with pytest.raises(ToolError) as exc:
            await client.call_tool(
                "create_conversation", {"inbox_id": ig.id, "contact_id": with_phone.id}
            )
        assert "wrote first" in str(exc.value)


# ---------------------------------------------------------------------------
# Messages: attachments and WhatsApp templates
# ---------------------------------------------------------------------------
async def test_send_message_with_an_attachment(mcp_session):
    owner = await _account(mcp_session, "-att")
    inbox = await _inbox(mcp_session, owner, "api", {}, "API")
    contact = Contact(account_id=owner.account.id, name="Cliente")
    mcp_session.add(contact)
    await mcp_session.flush()
    await _use_token(mcp_session, owner)

    async with Client(build_server()) as client:
        conv = _body(
            await client.call_tool(
                "create_conversation", {"inbox_id": inbox.id, "contact_id": contact.id}
            )
        )
        msg = _body(
            await client.call_tool(
                "send_message",
                {
                    "conversation_id": conv["id"],
                    "content": "Te paso el folleto",
                    "attachments": [
                        {"url": "https://cdn.example.com/folleto.pdf", "file_type": "file"}
                    ],
                },
            )
        )
        with pytest.raises(ToolError):
            await client.call_tool(
                "send_message",
                {"conversation_id": conv["id"], "attachments": [{"url": "http://insecure/x.png"}]},
            )

    rows = (
        await mcp_session.exec(select(Attachment).where(Attachment.message_id == msg["id"]))
    ).all()
    assert [a.external_url for a in rows] == ["https://cdn.example.com/folleto.pdf"]


async def test_whatsapp_templates_list_and_send(mcp_session):
    owner = await _account(mcp_session, "-tpl")
    inbox = await _inbox(
        mcp_session,
        owner,
        "whatsapp",
        {
            "phone_number": f"+5984{secrets.randbelow(10**7):07d}",
            "provider": WHATSAPP_PROVIDER_CLOUD,
            "provider_config": {"api_key": "t", "phone_number_id": "p-tpl", "business_account_id": "b"},
        },
        "WA",
    )
    from app.domains.inboxes.models import WhatsappChannel

    channel = await mcp_session.get(WhatsappChannel, inbox.channel_id)
    channel.message_templates = [
        {
            "name": "recordatorio",
            "language": "es",
            "status": "APPROVED",
            "category": "UTILITY",
            "components": [{"type": "BODY", "text": "Hola {{1}}, tu turno es el {{2}}."}],
        },
        {"name": "borrador", "language": "es", "status": "PENDING", "components": []},
    ]
    mcp_session.add(channel)
    contact = Contact(account_id=owner.account.id, name="Ana", phone_number="+59899000111")
    mcp_session.add(contact)
    await mcp_session.flush()
    await _use_token(mcp_session, owner)

    with respx.mock(assert_all_called=False) as mock:
        mock.post(url__regex=r"https://graph\.facebook\.com/.*").mock(
            return_value=httpx.Response(200, json={"messages": [{"id": "wamid.tpl"}]})
        )
        async with Client(build_server()) as client:
            listed = _body(await client.call_tool("list_whatsapp_templates", {"inbox_id": inbox.id}))
            assert [(t["name"], t["variables"]) for t in listed["templates"]] == [("recordatorio", 2)]
            conv = _body(
                await client.call_tool(
                    "create_conversation", {"inbox_id": inbox.id, "contact_id": contact.id}
                )
            )
            sent = _body(
                await client.call_tool(
                    "send_whatsapp_template",
                    {
                        "conversation_id": conv["id"],
                        "name": "recordatorio",
                        "language": "es",
                        "body_params": ["Ana", "martes 10:00"],
                    },
                )
            )
            assert sent["content"] == "Hola Ana, tu turno es el martes 10:00."
            assert sent["additional_attributes"]["template_params"]["name"] == "recordatorio"
            with pytest.raises(ToolError):
                await client.call_tool(
                    "send_whatsapp_template",
                    {"conversation_id": conv["id"], "name": "borrador", "language": "es"},
                )


# ---------------------------------------------------------------------------
# Publications and media
# ---------------------------------------------------------------------------
async def test_show_update_and_retry_publication(mcp_session, monkeypatch):
    owner = await _account(mcp_session, "-pub")
    inbox = await _inbox(
        mcp_session,
        owner,
        "facebook",
        {"page_id": f"P{secrets.token_hex(4)}", "page_access_token": "t"},
        "Página",
    )
    channel_id = await channel_id_of(mcp_session, inbox)
    publication = await pub_svc.create_publication(
        mcp_session,
        account_id=owner.account.id,
        created_by_id=owner.user.id,
        payload={
            "content": "Inscripciones abiertas",
            "media": [],
            "scheduled_for": datetime.now(UTC) + timedelta(days=3),
            "targets": [{"channel_id": channel_id, "settings": {}}],
        },
    )
    await _use_token(mcp_session, owner)

    async with Client(build_server()) as client:
        shown = _body(await client.call_tool("show_publication", {"publication_id": publication.id}))
        assert shown["content"] == "Inscripciones abiertas"
        updated = _body(
            await client.call_tool(
                "update_publication",
                {"publication_id": publication.id, "content": "Inscripciones abiertas hasta el viernes"},
            )
        )
        assert updated["content"] == "Inscripciones abiertas hasta el viernes"
        # Only a failed publication can be retried; the service says so.
        with pytest.raises(ToolError) as exc:
            await client.call_tool("retry_publication", {"publication_id": publication.id})
        assert "reintenta" in str(exc.value)


async def test_upload_media_copies_a_public_image(mcp_session, monkeypatch):
    owner = await _account(mcp_session, "-media")
    await _use_token(mcp_session, owner)
    stored: dict[str, bytes] = {}

    async def _store(account_id, *, filename, content_type, data):
        key = f"accounts/{account_id}/uploads/{filename}"
        stored[key] = data
        return {"key": key, "file_url": f"http://minio/{key}"}

    async def _public(url):  # the test host is not resolvable from here
        return None

    monkeypatch.setattr(media_svc, "store_upload_blob", _store)
    monkeypatch.setattr("app.core.outbound.check_destination", _public)

    png = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 30, 30)).save(png, format="PNG")
    with respx.mock(assert_all_called=False) as mock:
        mock.get("https://files.example.com/flyer.png").mock(
            return_value=httpx.Response(200, content=png.getvalue(), headers={"content-type": "image/png"})
        )
        async with Client(build_server()) as client:
            asset = _body(
                await client.call_tool("upload_media", {"url": "https://files.example.com/flyer.png"})
            )
            with pytest.raises(ToolError):
                await client.call_tool("upload_media", {"url": "http://files.example.com/x.png"})

    assert asset["kind"] == "image"
    assert len(stored) == 1


async def test_new_tools_do_not_reach_another_account(mcp_session):
    owner = await _account(mcp_session, "-iso")
    other = await _account(mcp_session, "-iso-other")
    their_inbox = await _inbox(mcp_session, other, "api", {}, "Theirs")
    their_contact = Contact(account_id=other.account.id, name="Ajeno")
    mcp_session.add(their_contact)
    await mcp_session.flush()
    await _use_token(mcp_session, owner)

    async with Client(build_server()) as client:
        for tool, args in (
            ("update_contact", {"contact_id": their_contact.id, "name": "x"}),
            ("create_conversation", {"inbox_id": their_inbox.id, "contact_id": their_contact.id}),
            ("list_whatsapp_templates", {"inbox_id": their_inbox.id}),
        ):
            with pytest.raises(ToolError):
                await client.call_tool(tool, args)

    untouched = await mcp_session.get(Contact, their_contact.id)
    await mcp_session.refresh(untouched)
    assert untouched.name == "Ajeno"
    assert (
        await mcp_session.exec(select(Message).where(Message.inbox_id == their_inbox.id))
    ).first() is None
