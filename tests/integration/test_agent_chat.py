"""Agent chat: OpenAI with the publishing MCP tools, writes confirmed by the
user. OpenAI is mocked with respx; each test scripts the model's replies."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.agent.models import AgentThread
from app.domains.agent.service import READ_TOOLS, WRITE_TOOLS
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.publishing import service as publishing_svc
from app.domains.publishing.models import Publication, PublishingChannel
from app.domains.teams import models as _teams  # noqa: F401
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app

pytestmark = pytest.mark.integration

OPENAI = "https://api.openai.com/v1/chat/completions"
ZONE = "America/Montevideo"


class FakeOpenAI:
    """Answers each chat completion with the next scripted reply and keeps
    what was asked."""

    def __init__(self) -> None:
        self.replies: list[httpx.Response] = []
        self.requests: list[dict[str, Any]] = []

    def queue(self, *replies: httpx.Response) -> None:
        self.replies.extend(replies)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        if not self.replies:
            return httpx.Response(500, json={"error": {"message": "no scripted reply"}})
        return self.replies.pop(0)


def say(content: str) -> httpx.Response:
    return _completion({"role": "assistant", "content": content})


def call(name: str, arguments: dict[str, Any], call_id: str) -> httpx.Response:
    return _completion(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }
            ],
        }
    )


def _completion(message: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"index": 0, "message": message, "finish_reason": "stop"}]}
    )


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
    fake = FakeOpenAI()
    with respx.mock(assert_all_called=False) as mock:
        mock.post(OPENAI).mock(side_effect=fake)
        yield fake


async def _auth(db_session, user) -> dict[str, str]:
    headers, tokens = create_new_auth_token(user_tokens=user.tokens, uid=user.uid)
    user.tokens = tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@agent.example.com",
            account_name=f"AGT{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    return owner, await _auth(db_session, owner.user)


async def _seed_agent(db_session, account_id: int, suffix: str) -> dict[str, str]:
    other = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agent{suffix}@agent.example.com",
            account_name=f"AGTAGENT{suffix}",
            user_full_name=f"Agent{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(account_id=account_id, user_id=other.user.id, role=ACCOUNT_USER_ROLE_AGENT)
    )
    await db_session.flush()
    return await _auth(db_session, other.user)


async def _channel(db_session, account) -> PublishingChannel:
    channel = PublishingChannel(
        account_id=account.id,
        network="threads",
        name="Mi Threads",
        external_id="8801",
        credentials={"access_token": "LONG"},
    )
    db_session.add(channel)
    await db_session.flush()
    return channel


async def _publications(db_session, account_id: int) -> list[Publication]:
    return list(
        (
            await db_session.exec(select(Publication).where(Publication.account_id == account_id))
        ).all()
    )


def _tool_names(request: dict[str, Any]) -> list[str]:
    return [t["function"]["name"] for t in request.get("tools", [])]


def _next_month_at_ten() -> tuple[str, str]:
    """A naive local date the model might send, and the UTC instant it means
    in the user's zone."""
    day = (datetime.now(UTC) + timedelta(days=30)).date()
    local = datetime(day.year, day.month, day.day, 10, 0)
    return local.isoformat(), local.replace(tzinfo=ZoneInfo(ZONE)).astimezone(UTC).isoformat()


# ---------------------------------------------------------------------------
async def test_status_follows_the_key_and_the_role(client, db_session, monkeypatch):
    owner, h = await _seed(db_session, "-st")
    agent_h = await _seed_agent(db_session, owner.account.id, "-st")
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    settings = get_settings()

    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    status = (await client.get(base, headers=h)).json()
    assert status == {"enabled": True, "model": settings.openai_agent_model, "can_write": True}
    assert (await client.get(base, headers=agent_h)).json()["can_write"] is False

    monkeypatch.setattr(settings, "openai_api_key", "")
    assert (await client.get(base, headers=h)).json()["enabled"] is False
    r = await client.post(f"{base}/threads", headers=h, json={"content": "Hola"})
    assert r.status_code == 503
    assert "OpenAI" in r.json()["message"]


async def test_a_read_tool_runs_and_the_agent_answers(client, db_session, openai):
    owner, h = await _seed(db_session, "-read")
    await _channel(db_session, owner.account)
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    openai.queue(
        call("list_publication_channels", {}, "call_1"),
        say("Tenés un canal: Mi Threads."),
    )

    r = await client.post(
        f"{base}/threads", headers=h, json={"content": "¿Qué canales tengo?", "timezone": ZONE}
    )
    assert r.status_code == 200, r.text
    chat = r.json()
    assert chat["title"] == "¿Qué canales tengo?"
    assert chat["pending_action"] is None
    assert [(i["kind"], i.get("status")) for i in chat["items"]] == [
        ("user", None),
        ("tool", "done"),
        ("assistant", None),
    ]
    tool = chat["items"][1]
    assert (tool["tool"], tool["label"], tool["publication_id"]) == (
        "list_publication_channels",
        "Consultó tus canales",
        None,
    )
    assert chat["items"][2]["content"] == "Tenés un canal: Mi Threads."

    first, second = openai.requests
    assert _tool_names(first) == list(READ_TOOLS + WRITE_TOOLS)
    assert first["parallel_tool_calls"] is False
    assert first["model"] == get_settings().openai_agent_model
    system = first["messages"][0]
    assert system["role"] == "system" and ZONE in system["content"]
    (answer,) = [m for m in second["messages"] if m["role"] == "tool"]
    assert answer["tool_call_id"] == "call_1"
    assert "Mi Threads" in answer["content"]

    threads = (await client.get(f"{base}/threads", headers=h)).json()["threads"]
    assert [(t["id"], t["has_pending_action"]) for t in threads] == [(chat["id"], False)]


async def test_a_publication_waits_for_confirmation(client, db_session, openai):
    owner, h = await _seed(db_session, "-pub")
    channel = await _channel(db_session, owner.account)
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    local, utc = _next_month_at_ten()
    openai.queue(
        call(
            "create_publication",
            {"channel_ids": [channel.id], "content": "¡Hola!", "scheduled_for": local},
            "call_pub",
        )
    )

    chat = (
        await client.post(
            f"{base}/threads", headers=h, json={"content": "Programá un saludo", "timezone": ZONE}
        )
    ).json()
    pending = chat["pending_action"]
    assert pending == {
        "id": "call_pub",
        "tool": "create_publication",
        "title": "Programar publicación",
        "confirm_label": "Programar",
        "publication": {
            "id": None,
            "content": "¡Hola!",
            # The model's naive "10:00" is the user's local time, not UTC.
            "scheduled_for": utc,
            "channels": [{"id": channel.id, "name": "Mi Threads", "network": "threads"}],
            "media": [],
        },
    }
    assert chat["items"][-1]["status"] == "pending"
    assert chat["items"][-1]["label"] == "Espera tu confirmación"
    # The trial run left nothing behind.
    assert await _publications(db_session, owner.account.id) == []
    threads = (await client.get(f"{base}/threads", headers=h)).json()["threads"]
    assert threads[0]["has_pending_action"] is True

    openai.queue(say("Listo, quedó programada."))
    r = await client.post(
        f"{base}/threads/{chat['id']}/actions/call_pub/confirm", headers=h
    )
    assert r.status_code == 200, r.text
    chat = r.json()
    assert chat["pending_action"] is None
    done = [i for i in chat["items"] if i["kind"] == "tool"][-1]
    assert (done["status"], done["label"]) == ("done", "Programó la publicación")
    (publication,) = await _publications(db_session, owner.account.id)
    assert done["publication_id"] == publication.id
    assert publication.created_by_id == owner.user.id
    assert publication.scheduled_for.isoformat() == utc
    assert chat["items"][-1]["content"] == "Listo, quedó programada."
    follow_up = openai.requests[-1]
    (answer,) = [m for m in follow_up["messages"] if m["role"] == "tool"]
    assert answer["tool_call_id"] == "call_pub"

    r = await client.post(f"{base}/threads/{chat['id']}/actions/call_pub/confirm", headers=h)
    assert r.status_code == 409


async def test_cancelling_shows_the_publication_and_survives_it_being_gone(
    client, db_session, openai
):
    owner, h = await _seed(db_session, "-can")
    channel = await _channel(db_session, owner.account)
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    publication = await publishing_svc.create_publication(
        db_session,
        account_id=owner.account.id,
        payload={
            "content": "Promo del viernes",
            "scheduled_for": datetime.now(UTC) + timedelta(days=3),
            "targets": [{"channel_id": channel.id}],
        },
    )
    openai.queue(call("cancel_publication", {"publication_id": publication.id}, "call_del"))

    chat = (
        await client.post(f"{base}/threads", headers=h, json={"content": "Borrá la promo"})
    ).json()
    pending = chat["pending_action"]
    assert (pending["tool"], pending["title"], pending["confirm_label"]) == (
        "cancel_publication",
        "Borrar publicación",
        "Borrar",
    )
    assert pending["publication"]["id"] == publication.id
    assert pending["publication"]["content"] == "Promo del viernes"
    assert pending["publication"]["channels"] == [
        {"id": channel.id, "name": "Mi Threads", "network": "threads"}
    ]

    # Deleted from the calendar before the user answered the card.
    await publishing_svc.delete_publication(db_session, publication=publication)
    chat = (await client.get(f"{base}/threads/{chat['id']}", headers=h)).json()
    assert chat["pending_action"]["publication"] == {
        "id": publication.id,
        "content": None,
        "scheduled_for": None,
        "channels": [],
        "media": [],
    }
    openai.queue(say("Esa publicación ya no estaba."))
    chat = (
        await client.post(f"{base}/threads/{chat['id']}/actions/call_del/confirm", headers=h)
    ).json()
    tool = [i for i in chat["items"] if i["kind"] == "tool"][-1]
    assert (tool["status"], tool["label"]) == ("error", "No se pudo borrar la publicación")
    assert chat["pending_action"] is None


async def test_an_invalid_proposal_goes_back_to_the_model(client, db_session, openai):
    owner, h = await _seed(db_session, "-inv")
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    openai.queue(
        call("create_publication", {"channel_ids": [987654321], "content": "Hola"}, "call_bad"),
        say("No encontré ese canal. ¿Cuál querés usar?"),
    )

    chat = (
        await client.post(f"{base}/threads", headers=h, json={"content": "Publicá hola"})
    ).json()
    assert chat["pending_action"] is None
    tool = next(i for i in chat["items"] if i["kind"] == "tool")
    assert (tool["status"], tool["label"]) == ("error", "La propuesta no pasó la revisión")
    assert "no existe" in tool["detail"]
    (answer,) = [m for m in openai.requests[1]["messages"] if m["role"] == "tool"]
    assert "no existe" in answer["content"]


async def test_rejecting_or_writing_drops_the_proposal(client, db_session, openai):
    owner, h = await _seed(db_session, "-rej")
    channel = await _channel(db_session, owner.account)
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    local, _ = _next_month_at_ten()
    proposal = {"channel_ids": [channel.id], "content": "Hola", "scheduled_for": local}
    openai.queue(call("create_publication", proposal, "call_a"))
    chat = (
        await client.post(f"{base}/threads", headers=h, json={"content": "Programá hola"})
    ).json()
    asked = len(openai.requests)

    chat = (
        await client.post(f"{base}/threads/{chat['id']}/actions/call_a/reject", headers=h)
    ).json()
    assert chat["pending_action"] is None
    assert chat["items"][-1]["status"] == "rejected"
    assert len(openai.requests) == asked  # rejecting does not call the model

    # A new proposal, answered with words instead of the buttons.
    openai.queue(call("create_publication", proposal, "call_b"))
    chat = (
        await client.post(
            f"{base}/threads/{chat['id']}/messages", headers=h, json={"content": "De nuevo"}
        )
    ).json()
    assert chat["pending_action"]["id"] == "call_b"
    openai.queue(say("Dale, ¿a qué hora?"))
    chat = (
        await client.post(
            f"{base}/threads/{chat['id']}/messages",
            headers=h,
            json={"content": "Mejor a las 11", "timezone": ZONE},
        )
    ).json()
    assert chat["pending_action"] is None
    assert [i["status"] for i in chat["items"] if i["kind"] == "tool"] == ["rejected", "rejected"]
    tail = openai.requests[-1]["messages"][-2:]
    assert tail[0]["role"] == "tool" and tail[0]["tool_call_id"] == "call_b"
    assert "rejected" in tail[0]["content"]
    assert tail[1] == {"role": "user", "content": "Mejor a las 11"}
    assert await _publications(db_session, owner.account.id) == []


async def test_agents_only_get_read_tools(client, db_session, openai):
    owner, _ = await _seed(db_session, "-ag")
    channel = await _channel(db_session, owner.account)
    agent_h = await _seed_agent(db_session, owner.account.id, "-ag")
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    openai.queue(
        call("create_publication", {"channel_ids": [channel.id], "content": "Hola"}, "call_x"),
        say("Eso lo tiene que hacer un administrador."),
    )

    chat = (
        await client.post(f"{base}/threads", headers=agent_h, json={"content": "Publicá hola"})
    ).json()
    assert _tool_names(openai.requests[0]) == list(READ_TOOLS)
    assert "no es administrador" in openai.requests[0]["messages"][0]["content"]
    assert chat["pending_action"] is None
    tool = next(i for i in chat["items"] if i["kind"] == "tool")
    assert tool["status"] == "error"
    assert await _publications(db_session, owner.account.id) == []


async def test_a_model_failure_keeps_the_message(client, db_session, openai):
    owner, h = await _seed(db_session, "-fail")
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    openai.queue(httpx.Response(500, json={"error": {"message": "boom"}}))

    r = await client.post(f"{base}/threads", headers=h, json={"content": "Hola"})
    assert r.status_code == 502
    body = r.json()
    assert body["message"] and body["thread_id"]
    chat = (await client.get(f"{base}/threads/{body['thread_id']}", headers=h)).json()
    assert [(i["kind"], i["content"]) for i in chat["items"]] == [("user", "Hola")]

    # The chat was released: the next message goes through.
    openai.queue(say("¡Hola! ¿En qué te ayudo?"))
    r = await client.post(
        f"{base}/threads/{body['thread_id']}/messages", headers=h, json={"content": "¿Estás?"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["items"][-1]["content"] == "¡Hola! ¿En qué te ayudo?"


async def test_a_busy_chat_and_someone_elses_chat(client, db_session, openai):
    owner, h = await _seed(db_session, "-busy")
    agent_h = await _seed_agent(db_session, owner.account.id, "-busy")
    base = f"/api/v1/accounts/{owner.account.id}/agent"
    openai.queue(say("Hola"))
    chat = (await client.post(f"{base}/threads", headers=h, json={"content": "Hola"})).json()

    await db_session.exec(  # type: ignore[call-overload]
        update(AgentThread)
        .where(AgentThread.id == chat["id"])
        .values(running_since=datetime.now(UTC))
    )
    r = await client.post(f"{base}/threads/{chat['id']}/messages", headers=h, json={"content": "?"})
    assert r.status_code == 409
    assert r.json()["message"]

    # Chats are private, even inside the account.
    assert (await client.get(f"{base}/threads/{chat['id']}", headers=agent_h)).status_code == 404
    assert (await client.get(f"{base}/threads", headers=agent_h)).json() == {"threads": []}

    assert (await client.delete(f"{base}/threads/{chat['id']}", headers=h)).status_code == 200
    assert (await client.get(f"{base}/threads/{chat['id']}", headers=h)).status_code == 404


async def test_the_message_is_validated(client, db_session, openai):
    owner, h = await _seed(db_session, "-val")
    base = f"/api/v1/accounts/{owner.account.id}/agent/threads"

    for payload in (
        {"content": "   "},
        {"content": "x" * 4001},
        {"content": "Hola", "timezone": "Mars/Olympus"},
    ):
        r = await client.post(base, headers=h, json=payload)
        assert r.status_code == 422, payload
        assert r.json()["message"]
    assert openai.requests == []
