"""Searching old conversations by message (F8, step 1).

Runs against the real indexes and the real ``alo_search_text`` from
migration ``0f8e5a1c2b3d`` — the matching lives in Postgres, so a test
that mocked it would test nothing. The cases are the reasons the old
``ILIKE`` was not enough: accents, word forms, fragments, typos, and an
answer that points at the message rather than the conversation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.conversations.models import (
    MESSAGE_TYPE_ACTIVITY,
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
)
from app.domains.inboxes.models import InboxMember
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app

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


async def _headers(db_session, user) -> dict[str, str]:
    headers, tokens = create_new_auth_token(user_tokens=user.tokens, uid=user.uid)
    user.tokens = tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


async def _account(db_session, suffix: str):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@busqueda.example.com",
            account_name=f"Busqueda{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


async def _inbox(db_session, account, name):
    return (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=account,
                name=name,
                channel_type="api",
                channel_params={"webhook_url": ""},
            ),
        ).perform()
    ).inbox


async def _conversation(db_session, account, inbox, display_id, contact_name, texts):
    contact = Contact(account_id=account.id, name=contact_name)
    db_session.add(contact)
    await db_session.flush()
    ci = ContactInbox(
        contact_id=contact.id, inbox_id=inbox.id, source_id=f"s-{inbox.id}-{display_id}"
    )
    db_session.add(ci)
    await db_session.flush()
    conv = Conversation(
        account_id=account.id,
        inbox_id=inbox.id,
        contact_id=contact.id,
        contact_inbox_id=ci.id,
        display_id=display_id,
    )
    db_session.add(conv)
    await db_session.flush()
    # A trigger assigns the real display_id on insert; the value passed
    # above is overwritten, and the object keeps the stale one until read.
    await db_session.refresh(conv)
    messages = []
    for kind, text, private in texts:
        msg = Message(
            account_id=account.id,
            inbox_id=inbox.id,
            conversation_id=conv.id,
            message_type=kind,
            content=text,
            private=private,
        )
        db_session.add(msg)
        await db_session.flush()
        messages.append(msg)
    return conv, messages


IN, OUT, ACT = MESSAGE_TYPE_INCOMING, MESSAGE_TYPE_OUTGOING, MESSAGE_TYPE_ACTIVITY


@pytest.fixture
async def world(db_session):
    owner = await _account(db_session, "")
    ventas = await _inbox(db_session, owner.account, "Ventas")
    soporte = await _inbox(db_session, owner.account, "Soporte")
    await _conversation(
        db_session, owner.account, ventas, 1, "Ana",
        [
            (IN, "Hola, ¿hacen envío al interior?", False),
            (OUT, "Sí, el Envío sale mañana", False),
            (IN, "¿Se puede pagar en tres cuotas?", False),
            (OUT, "Ojo: cliente pidió factura A", True),  # private note
            (ACT, "Asignado a Bruno — envío", False),  # activity
        ],
    )
    soporte_conv, _ = await _conversation(
        db_session, owner.account, soporte, 2, "Carla",
        [(IN, "Necesito el presupuesto del envío urgente", False)],
    )

    other = await _account(db_session, "-otra")
    otra_inbox = await _inbox(db_session, other.account, "Ajena")
    await _conversation(
        db_session, other.account, otra_inbox, 1, "Intrusa",
        [(IN, "envío secreto de otra cuenta", False)],
    )

    agent = await _account(db_session, "-agente")
    db_session.add(
        AccountUser(
            account_id=owner.account.id, user_id=agent.user.id, role=ACCOUNT_USER_ROLE_AGENT
        )
    )
    db_session.add(InboxMember(inbox_id=soporte.id, user_id=agent.user.id))
    await db_session.flush()

    return {
        "account": owner.account,
        "admin": await _headers(db_session, owner.user),
        "agent": await _headers(db_session, agent.user),
        "soporte_conv": soporte_conv.display_id,
    }


async def _search(client, world, q, who="admin", **params):
    resp = await client.get(
        f"/api/v1/accounts/{world['account'].id}/search/messages",
        params={"q": q, **params},
        headers=world[who],
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _texts(body):
    return [r["snippet"] for r in body["payload"]]


async def test_accents_do_not_matter(client, world):
    body = await _search(client, world, "envio")
    texts = _texts(body)
    assert "Sí, el Envío sale mañana" in texts
    assert "Hola, ¿hacen envío al interior?" in texts


async def test_a_word_finds_its_other_forms(client, world):
    # Spanish stemming: the singular finds the plural.
    assert _texts(await _search(client, world, "cuota")) == [
        "¿Se puede pagar en tres cuotas?"
    ]


async def test_a_fragment_is_enough(client, world):
    assert _texts(await _search(client, world, "presu")) == [
        "Necesito el presupuesto del envío urgente"
    ]


async def test_two_swapped_letters_still_find_it(client, world):
    # "presupeusto" scores 0.50 — under pg_trgm's default 0.6.
    assert _texts(await _search(client, world, "presupeusto")) == [
        "Necesito el presupuesto del envío urgente"
    ]


async def test_the_answer_points_at_the_message(client, world):
    body = await _search(client, world, "cuotas")
    [hit] = body["payload"]
    assert hit["conversation_id"] == 1
    assert hit["contact"]["name"] == "Ana"
    assert hit["inbox"]["name"] == "Ventas"
    assert hit["snippet"][slice(*hit["highlights"][0])] == "cuotas"
    assert isinstance(hit["message_id"], int) and hit["created_at"]


async def test_private_notes_are_found_activity_rows_are_not(client, world):
    assert _texts(await _search(client, world, "factura")) == [
        "Ojo: cliente pidió factura A"
    ]
    assert all(
        "Asignado" not in t for t in _texts(await _search(client, world, "envio"))
    )


async def test_another_account_never_appears(client, world):
    assert all("secreto" not in t for t in _texts(await _search(client, world, "envio")))


async def test_an_agent_only_finds_inboxes_they_belong_to(client, world):
    texts = _texts(await _search(client, world, "envio", who="agent"))
    assert texts == ["Necesito el presupuesto del envío urgente"]  # Soporte only


async def test_search_inside_one_conversation(client, world):
    texts = _texts(
        await _search(client, world, "envio", conversation_id=world["soporte_conv"])
    )
    assert texts == ["Necesito el presupuesto del envío urgente"]


async def test_jumping_to_a_hit_opens_the_conversation_around_it(
    client, db_session, world
):
    """``after`` returns the newest twenty after a cursor, so a hit from a
    year ago used to open at today. ``around`` opens at the hit."""
    account = world["account"]
    inbox = await _inbox(db_session, account, "Larga")
    conv, msgs = await _conversation(
        db_session, account, inbox, 9, "Dora",
        [(IN, f"mensaje {i}", False) for i in range(60)],
    )
    target = msgs[10]

    resp = await client.get(
        f"/api/v1/accounts/{account.id}/conversations/{conv.display_id}/messages",
        params={"around": target.id},
        headers=world["admin"],
    )
    assert resp.status_code == 200, resp.text
    contents = [m["content"] for m in resp.json()["payload"]]
    assert contents == [f"mensaje {i}" for i in range(0, 26)]


async def test_an_empty_query_is_refused(client, world):
    resp = await client.get(
        f"/api/v1/accounts/{world['account'].id}/search/messages",
        params={"q": ""},
        headers=world["admin"],
    )
    assert resp.status_code == 422
