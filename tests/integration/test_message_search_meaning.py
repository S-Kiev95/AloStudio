"""Meaning-based search (F8, step 2).

The model is stubbed and the vectors are built by hand, so each test says
exactly how close a message is to the query: what is under test is what
the search *does* with distances — the threshold, the fusion with text,
falling back when the service is down, the permission scope — not the
model, whose distances were measured separately against the real one.
"""

from __future__ import annotations

import math
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.core.embeddings import GEMMA_DIM, MODEL_GEMMA, EmbeddingServiceError
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.conversations import message_embeddings as writer
from app.domains.conversations import message_search
from app.domains.conversations.message_embeddings import MessageEmbedding, embed_pending
from app.domains.conversations.models import (
    MESSAGE_TYPE_ACTIVITY,
    MESSAGE_TYPE_INCOMING,
    Conversation,
    Message,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app

pytestmark = pytest.mark.integration


def at_distance(d: float, axis: int) -> list[float]:
    """A unit vector at cosine distance ``d`` from the query (axis 0)."""
    v = [0.0] * GEMMA_DIM
    v[0] = 1 - d
    v[axis] = math.sqrt(1 - (1 - d) ** 2)
    return v


QUERY = at_distance(0.0, 1)


@pytest.fixture
def model_up(monkeypatch):
    async def embed_query(text, *, task, title=None):
        return QUERY

    monkeypatch.setattr(message_search, "gemma_enabled", lambda: True)
    monkeypatch.setattr(message_search, "embed_gemma_one", embed_query)


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


async def _headers(db_session, user):
    headers, tokens = create_new_auth_token(user_tokens=user.tokens, uid=user.uid)
    user.tokens = tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


@pytest.fixture
async def world(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@sentido.example.com",
            account_name="Sentido",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    account = owner.account
    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=account, name="Ventas", channel_type="api",
                channel_params={"webhook_url": ""},
            ),
        ).perform()
    ).inbox
    contact = Contact(account_id=account.id, name="Ana")
    db_session.add(contact)
    await db_session.flush()
    ci = ContactInbox(contact_id=contact.id, inbox_id=inbox.id, source_id="sen-1")
    db_session.add(ci)
    await db_session.flush()
    conv = Conversation(
        account_id=account.id, inbox_id=inbox.id, contact_id=contact.id,
        contact_inbox_id=ci.id, display_id=1,
    )
    db_session.add(conv)
    await db_session.flush()

    messages = {}
    # (text, distance to the query or None for no vector)
    for key, text, distance, axis in (
        ("financiar", "¿puedo pagarlo en 3 veces con tarjeta?", 0.12, 2),
        ("cuotas", "lo de las cuotas lo vemos el lunes", 0.10, 3),
        ("horario", "¿a qué hora abren el sábado?", 0.60, 4),
        ("borde", "me cobraron dos veces este mes", 0.26, 5),
    ):
        msg = Message(
            account_id=account.id, inbox_id=inbox.id, conversation_id=conv.id,
            message_type=MESSAGE_TYPE_INCOMING, content=text,
        )
        db_session.add(msg)
        await db_session.flush()
        db_session.add(
            MessageEmbedding(
                message_id=msg.id, account_id=account.id, model=MODEL_GEMMA,
                embedding=at_distance(distance, axis),
            )
        )
        messages[key] = msg
    await db_session.flush()

    agent = (
        await AccountBuilder(
            db_session,
            AccountBuilderParams(
                email="agente@sentido.example.com", account_name="Otra",
                user_full_name="Agente", user_password="Password123!", confirmed=True,
            ),
        ).perform()
    ).user
    db_session.add(
        AccountUser(account_id=account.id, user_id=agent.id, role=ACCOUNT_USER_ROLE_AGENT)
    )
    await db_session.flush()
    return {
        "account": account,
        "messages": messages,
        "admin": await _headers(db_session, owner.user),
        "agent": await _headers(db_session, agent),
    }


async def _search(client, world, q, who="admin"):
    resp = await client.get(
        f"/api/v1/accounts/{world['account'].id}/search/messages",
        params={"q": q},
        headers=world[who],
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["payload"]


async def test_a_message_with_no_word_in_common_is_found_by_meaning(
    client, world, model_up
):
    hits = await _search(client, world, "financiación")
    by_text = {h["snippet"]: h["match"] for h in hits}
    assert by_text["¿puedo pagarlo en 3 veces con tarjeta?"] == "meaning"


async def test_far_messages_and_the_threshold_edge_stay_out(client, world, model_up):
    snippets = {h["snippet"] for h in await _search(client, world, "financiación")}
    assert "¿a qué hora abren el sábado?" not in snippets  # 0.60
    assert "me cobraron dos veces este mes" not in snippets  # 0.26 > 0.25


async def test_when_text_and_meaning_agree_it_comes_first(client, world, model_up):
    hits = await _search(client, world, "cuotas")
    assert hits[0]["snippet"] == "lo de las cuotas lo vemos el lunes"
    assert hits[0]["match"] == "both"


async def test_without_the_service_text_search_still_answers(
    client, world, monkeypatch
):
    async def down(text, *, task, title=None):
        raise EmbeddingServiceError("restarting")

    monkeypatch.setattr(message_search, "gemma_enabled", lambda: True)
    monkeypatch.setattr(message_search, "embed_gemma_one", down)
    hits = await _search(client, world, "cuotas")
    assert [(h["snippet"], h["match"]) for h in hits] == [
        ("lo de las cuotas lo vemos el lunes", "text")
    ]


async def test_meaning_hits_respect_the_inboxes_an_agent_can_see(
    client, world, model_up
):
    # The agent belongs to no inbox: neither text nor meaning may leak.
    assert await _search(client, world, "financiación", who="agent") == []


async def test_the_writer_vectorises_what_is_worth_it_once(db_session, world, monkeypatch):
    account = world["account"]
    conv_id = world["messages"]["cuotas"].conversation_id
    inbox_id = world["messages"]["cuotas"].inbox_id
    for kind, text in (
        (MESSAGE_TYPE_INCOMING, "necesito cambiar la dirección de entrega"),
        (MESSAGE_TYPE_INCOMING, "ok gracias"),  # too short to mean anything
        (MESSAGE_TYPE_ACTIVITY, "Conversación asignada a Bruno Sosa"),
    ):
        db_session.add(
            Message(
                account_id=account.id, inbox_id=inbox_id, conversation_id=conv_id,
                message_type=kind, content=text,
            )
        )
    await db_session.flush()

    sent: list[str] = []

    async def fake_embed(texts, *, task, titles=None):
        sent.extend(texts)
        return [at_distance(0.5, 6) for _ in texts]

    monkeypatch.setattr(writer, "embed_gemma", fake_embed)
    assert await embed_pending(db_session, account_id=account.id) == 1
    assert sent == ["necesito cambiar la dirección de entrega"]
    # Nothing left: the short one and the activity row are never picked up.
    assert await embed_pending(db_session, account_id=account.id) == 0

    stored = (
        await db_session.exec(
            select(MessageEmbedding).where(MessageEmbedding.account_id == account.id)
        )
    ).all()
    assert len(stored) == 5 and {e.model for e in stored} == {MODEL_GEMMA}
