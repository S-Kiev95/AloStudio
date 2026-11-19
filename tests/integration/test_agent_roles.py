"""Agent chat as the user (PLAN.agente-ia.md, paso 1): the MCP tools see
what the user's role sees in the panel. An agent only reaches the
conversations of their inboxes, never gets the tools the panel keeps to
administrators, and every write waits for their confirmation. OpenAI is
mocked like in ``test_agent_chat.py``."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import Conversation, Message
from app.domains.conversations.service import ConversationBuilderParams, create_conversation
from app.domains.inboxes.models import InboxMember
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app
from tests.integration.test_agent_chat import (
    OPENAI,
    FakeOpenAI,
    _auth,
    _seed,
    _tool_names,
    call,
    say,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def openai(monkeypatch) -> AsyncIterator[FakeOpenAI]:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "openai_base_url", "https://api.openai.com")
    # An administrator allowed Fast (test_fast_needs_an_administrators_yes).
    monkeypatch.setattr("app.domains.help_assistant.service.fast_allowed", lambda account: True)
    fake = FakeOpenAI()
    with respx.mock(assert_all_called=False) as mock:
        mock.post(OPENAI).mock(side_effect=fake)
        yield fake


async def _inbox_with_conversation(db_session, account, name: str, contact_name: str):
    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=account,
                name=name,
                channel_type="api",
                channel_params={"webhook_url": "https://x.example.com"},
            ),
        ).perform()
    ).inbox
    contact = Contact(account_id=account.id, name=contact_name)
    db_session.add(contact)
    await db_session.flush()
    contact_inbox = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox, source_id=f"src-{contact.id}"
    ).perform()
    conversation = await create_conversation(
        db_session, contact_inbox=contact_inbox, params=ConversationBuilderParams()
    )
    return inbox, conversation


async def _world(db_session, suffix: str):
    """An account with two inboxes; the agent is a member of the first."""
    owner, admin_h = await _seed(db_session, suffix)
    mine, my_conv = await _inbox_with_conversation(db_session, owner.account, "Ventas", "Ana")
    _, other_conv = await _inbox_with_conversation(db_session, owner.account, "Cobranzas", "Beto")
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agente{suffix}@roles.example.com",
            account_name=f"ROLES{suffix}",
            user_full_name="Sofía",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(account_id=owner.account.id, user_id=agent.user.id, role=ACCOUNT_USER_ROLE_AGENT)
    )
    db_session.add(InboxMember(inbox_id=mine.id, user_id=agent.user.id))
    await db_session.flush()
    agent_h = await _auth(db_session, agent.user)
    return owner, admin_h, agent_h, my_conv, other_conv


def _tool_result(request: dict, call_id: str) -> dict:
    (msg,) = [m for m in request["messages"] if m.get("tool_call_id") == call_id]
    return json.loads(msg["content"])


async def test_an_agent_gets_the_tools_of_their_role(client, db_session, openai):
    owner, admin_h, agent_h, _, _ = await _world(db_session, "-tools")
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    openai.queue(say("Hola"), say("Hola"))

    await client.post(f"{base}/threads", headers=admin_h, json={"content": "Hola"})
    await client.post(f"{base}/threads", headers=agent_h, json={"content": "Hola"})
    admin_tools, agent_tools = (_tool_names(r) for r in openai.requests)

    assert admin_tools == sorted(admin_tools)  # stable prefix for the prompt cache
    for name in ("send_message", "list_conversations", "create_publication", "create_webhook"):
        assert name in admin_tools
    for name in ("send_message", "list_conversations", "add_private_note", "create_appointment"):
        assert name in agent_tools
    for name in ("create_publication", "create_webhook", "create_campaign", "create_label",
                 "merge_contacts", "list_instagram_posts"):
        assert name not in agent_tools
    assert "Es agente" in openai.requests[1]["messages"][0]["content"]
    status = (await client.get(base, headers=agent_h)).json()
    assert (status["can_write"], status["is_administrator"]) == (True, False)


async def test_an_agent_only_reaches_their_inboxes(client, db_session, openai):
    owner, _, agent_h, my_conv, other_conv = await _world(db_session, "-vis")
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    openai.queue(
        call("list_conversations", {}, "c1"),
        call("show_conversation", {"conversation_id": other_conv.id}, "c2"),
        call("list_messages", {"conversation_id": other_conv.id}, "c3"),
        say("Solo veo la de Ana."),
    )

    chat = (
        await client.post(f"{base}/threads", headers=agent_h, json={"content": "¿Qué hay abierto?"})
    ).json()

    listed = _tool_result(openai.requests[1], "c1")
    assert [c["id"] for c in listed["conversations"]] == [my_conv.id]
    assert "not found" in _tool_result(openai.requests[2], "c2")["error"]
    assert "not found" in _tool_result(openai.requests[3], "c3")["error"]
    statuses = [i["status"] for i in chat["items"] if i["kind"] == "tool"]
    assert statuses == ["done", "error", "error"]


async def test_an_administrator_reaches_every_inbox(client, db_session, openai):
    owner, admin_h, _, my_conv, other_conv = await _world(db_session, "-adm")
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    openai.queue(call("list_conversations", {}, "c1"), say("Dos."))

    await client.post(f"{base}/threads", headers=admin_h, json={"content": "¿Qué hay abierto?"})

    listed = _tool_result(openai.requests[1], "c1")
    assert sorted(c["id"] for c in listed["conversations"]) == sorted([my_conv.id, other_conv.id])


async def test_a_reply_waits_for_confirmation_and_is_not_tried_before(
    client, db_session, openai
):
    owner, _, agent_h, my_conv, _ = await _world(db_session, "-reply")
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    openai.queue(
        call("send_message", {"conversation_id": my_conv.id, "content": "¡Hola Ana!"}, "c1"),
    )

    chat = (
        await client.post(f"{base}/threads", headers=agent_h, json={"content": "Saludá a Ana"})
    ).json()

    # Nothing reached the conversation yet: no trial run of a reply.
    sent = (
        await db_session.exec(select(Message).where(Message.conversation_id == my_conv.id))
    ).all()
    assert [m.content for m in sent if m.content == "¡Hola Ana!"] == []
    action = chat["pending_action"]
    assert action["tool"] == "send_message" and action["publication"] is None
    assert action["title"] == "Confirmá esta acción"
    assert {"label": "Conversación", "value": f"#{my_conv.display_id} · Ana"} in action["details"]
    assert {"label": "Mensaje", "value": "¡Hola Ana!"} in action["details"]

    openai.queue(say("Listo, se lo mandé."))
    r = await client.post(
        f"{base}/threads/{chat['id']}/actions/{action['id']}/confirm", headers=agent_h
    )
    assert r.status_code == 200, r.text
    sent = (
        await db_session.exec(select(Message).where(Message.conversation_id == my_conv.id))
    ).all()
    assert [m.content for m in sent if m.content == "¡Hola Ana!"] == ["¡Hola Ana!"]
    done = [i for i in r.json()["items"] if i["kind"] == "tool"][-1]
    assert (done["status"], done["label"]) == ("done", "Hecho")


async def test_an_agent_cannot_write_in_another_inbox(client, db_session, openai):
    owner, _, agent_h, _, other_conv = await _world(db_session, "-deny")
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    # The model guessed an id it never saw: the proposal waits, and the
    # confirmation fails without touching the conversation.
    openai.queue(
        call("add_private_note", {"conversation_id": other_conv.id, "content": "Ojo"}, "c1"),
    )
    chat = (
        await client.post(f"{base}/threads", headers=agent_h, json={"content": "Anotá algo"})
    ).json()
    action = chat["pending_action"]
    # The card doesn't name a conversation the agent can't see.
    assert {"label": "Conversación", "value": str(other_conv.id)} in action["details"]

    openai.queue(say("No pude: esa conversación no está en tus bandejas."))
    r = await client.post(
        f"{base}/threads/{chat['id']}/actions/{action['id']}/confirm", headers=agent_h
    )
    assert r.status_code == 200
    notes = (
        await db_session.exec(select(Message).where(Message.conversation_id == other_conv.id))
    ).all()
    assert [m for m in notes if m.content == "Ojo"] == []
    failed = [i for i in r.json()["items"] if i["kind"] == "tool"][-1]
    assert failed["status"] == "error" and "not found" in failed["detail"]
    conv = await db_session.get(Conversation, other_conv.id)
    assert conv is not None


# ---------------------------------------------------------------------------
# What the review of paso 1 found
# ---------------------------------------------------------------------------
async def test_an_agent_cannot_run_a_macro_on_another_inbox(client, db_session, openai):
    from app.domains.macros.models import MACRO_VISIBILITY_GLOBAL, Macro

    owner, _, agent_h, my_conv, other_conv = await _world(db_session, "-macro")
    macro = Macro(
        account_id=owner.account.id,
        name="Cerrar",
        visibility=MACRO_VISIBILITY_GLOBAL,
        created_by_id=owner.user.id,
        actions=[{"action_name": "resolve_conversation", "action_params": []}],
    )
    db_session.add(macro)
    await db_session.flush()
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    openai.queue(
        call(
            "execute_macro",
            {"macro_id": macro.id, "conversation_ids": [my_conv.id, other_conv.id]},
            "c1",
        )
    )
    chat = (
        await client.post(f"{base}/threads", headers=agent_h, json={"content": "Cerrá todo"})
    ).json()
    details = chat["pending_action"]["details"]
    assert {"label": "Macro", "value": "Cerrar"} in details
    # The card names only what the agent can see.
    assert {
        "label": "Conversaciones",
        "value": f"#{my_conv.display_id} · Ana, {other_conv.id}",
    } in details

    openai.queue(say("No pude."))
    r = await client.post(
        f"{base}/threads/{chat['id']}/actions/{chat['pending_action']['id']}/confirm",
        headers=agent_h,
    )
    failed = [i for i in r.json()["items"] if i["kind"] == "tool"][-1]
    assert failed["status"] == "error" and "not found" in failed["detail"]
    await db_session.refresh(my_conv)
    await db_session.refresh(other_conv)
    assert my_conv.status == other_conv.status == 0  # both still open


async def test_an_agent_lists_only_their_inboxes(client, db_session, openai):
    owner, admin_h, agent_h, _, _ = await _world(db_session, "-inb")
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    openai.queue(call("list_inboxes", {}, "c1"), say("Una."), call("list_inboxes", {}, "c2"), say("Dos."))

    await client.post(f"{base}/threads", headers=agent_h, json={"content": "¿Mis bandejas?"})
    await client.post(f"{base}/threads", headers=admin_h, json={"content": "¿Las bandejas?"})

    agent_view = _tool_result(openai.requests[1], "c1")["inboxes"]
    admin_view = _tool_result(openai.requests[3], "c2")["inboxes"]
    assert [i["name"] for i in agent_view] == ["Ventas"]
    assert sorted(i["name"] for i in admin_view) == ["Cobranzas", "Ventas"]


async def test_assigning_someone_who_is_not_there_fails(client, db_session, openai):
    owner, admin_h, _, my_conv, _ = await _world(db_session, "-asg")
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    for tool, args in (
        ("assign_agent", {"conversation_id": my_conv.id, "agent_id": 999_999}),
        ("assign_team", {"conversation_id": my_conv.id, "team_id": 999_999}),
    ):
        openai.queue(call(tool, args, "c1"))
        chat = (
            await client.post(f"{base}/threads", headers=admin_h, json={"content": "Asigná"})
        ).json()
        openai.queue(say("No existe."))
        r = await client.post(
            f"{base}/threads/{chat['id']}/actions/{chat['pending_action']['id']}/confirm",
            headers=admin_h,
        )
        failed = [i for i in r.json()["items"] if i["kind"] == "tool"][-1]
        assert failed["status"] == "error" and "not found" in failed["detail"], tool


async def test_search_gives_the_internal_conversation_id(client, db_session, openai):
    from app.domains.conversations.service import MessageBuilderParams, create_message

    owner, admin_h, _, my_conv, _ = await _world(db_session, "-srch")
    await create_message(
        db_session,
        conversation=my_conv,
        params=MessageBuilderParams(content="Consulta por la cuota de marzo", message_type="incoming"),
        user_id=None,
    )
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    openai.queue(call("search_messages", {"query": "cuota"}, "c1"), say("Encontré una."))

    await client.post(f"{base}/threads", headers=admin_h, json={"content": "Buscá cuota"})

    (found,) = _tool_result(openai.requests[1], "c1")["messages"]
    assert found["conversation_id"] == my_conv.id
    assert found["conversation_display_id"] == my_conv.display_id


async def test_a_tool_whose_service_commits_is_confirmed_once(
    client, db_session, openai, monkeypatch
):
    """Some services commit on their own (an Instagram attachment): the
    confirmation must not fail after the message already went out."""
    from app.mcp.tools import messages as message_tools

    original = message_tools.create_message

    async def committing(session, **kwargs):
        message = await original(session, **kwargs)
        await session.commit()
        return message

    monkeypatch.setattr(message_tools, "create_message", committing)
    owner, admin_h, _, my_conv, _ = await _world(db_session, "-commit")
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    openai.queue(call("send_message", {"conversation_id": my_conv.id, "content": "Hola"}, "c1"))
    chat = (
        await client.post(f"{base}/threads", headers=admin_h, json={"content": "Saludá"})
    ).json()

    openai.queue(say("Listo."))
    r = await client.post(
        f"{base}/threads/{chat['id']}/actions/{chat['pending_action']['id']}/confirm",
        headers=admin_h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["pending_action"] is None
    assert [i["status"] for i in r.json()["items"] if i["kind"] == "tool"][-1] == "done"


async def test_panel_admin_tools_refuse_an_agent_acting_as_themself(db_session):
    """Defense in depth: even called directly (an OAuth app of an agent),
    a tool the panel keeps to administrators refuses them."""
    from app.domains.agent.service import _mcp_server
    from app.domains.users.models import User
    from app.mcp.context import MCPContext, bind_mcp_context, reset_mcp_context
    from app.mcp.permissions import MCPPermissionError

    owner, _, _, _, _ = await _world(db_session, "-pa")
    agent_user = (
        await db_session.exec(select(User).where(User.email == "agente-pa@roles.example.com"))
    ).one()
    tool = await _mcp_server().get_tool("create_label")
    binding = bind_mcp_context(
        MCPContext(
            user=agent_user, account=owner.account, scope="write", session=db_session, user_scoped=True
        )
    )
    try:
        with pytest.raises(Exception) as caught:
            await tool.run({"title": "vip"})
    finally:
        reset_mcp_context(binding)
    assert isinstance(caught.value, MCPPermissionError) or "administrator" in str(caught.value)
