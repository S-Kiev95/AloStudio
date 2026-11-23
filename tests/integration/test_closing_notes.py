"""Closing notes (F17): why a conversation was closed, and the report."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.core.i18n import DEFAULT_LOCALE, t
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.closing.models import ConversationClosing
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    CONVERSATION_STATUS_OPEN,
    CONVERSATION_STATUS_RESOLVED,
    Message,
)
from app.domains.conversations.service import ConversationBuilderParams, create_conversation
from app.domains.inboxes.models import InboxMember
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


async def _headers(db_session, user) -> dict[str, str]:
    headers, tokens = create_new_auth_token(user_tokens=user.tokens, uid=user.uid)
    user.tokens = tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


@pytest.fixture
async def seeded(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@closing.example.com",
            account_name="Instituto",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="sofia@closing.example.com",
            account_name="Otra",
            user_full_name="Sofía",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    outsider = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="otro@closing.example.com",
            account_name="Otra 2",
            user_full_name="Otro",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    for user in (agent.user, outsider.user):
        db_session.add(
            AccountUser(account_id=owner.account.id, user_id=user.id, role=ACCOUNT_USER_ROLE_AGENT)
        )
    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Web",
                channel_type="api",
                channel_params={"webhook_url": "https://example.com/h"},
            ),
        ).perform()
    ).inbox
    db_session.add(InboxMember(inbox_id=inbox.id, user_id=agent.user.id))
    contact = Contact(account_id=owner.account.id, name="Lucía Pereira")
    db_session.add(contact)
    await db_session.flush()
    contact_inbox = await ContactInboxBuilder(session=db_session, contact=contact, inbox=inbox).perform()
    await db_session.refresh(contact_inbox, ["inbox"])
    conversation = await create_conversation(
        db_session, contact_inbox=contact_inbox, params=ConversationBuilderParams()
    )
    return {
        "account": owner.account,
        "admin": owner.user,
        "agent": agent.user,
        "outsider": outsider.user,
        "conversation": conversation,
        "base": f"/api/v1/accounts/{owner.account.id}/closing_notes",
    }


async def _turn_on(client, db_session, seeded, **extra) -> None:
    admin_h = await _headers(db_session, seeded["admin"])
    resp = await client.put(
        f"{seeded['base']}/settings", json={"enabled": True, **extra}, headers=admin_h
    )
    assert resp.status_code == 200, resp.text


async def test_settings_start_off_with_our_categories(client, db_session, seeded):
    agent_h = await _headers(db_session, seeded["agent"])
    shown = (await client.get(f"{seeded['base']}/settings", headers=agent_h)).json()
    assert shown["enabled"] is False
    assert shown["required"] is False
    assert shown["categories"][0] == t(DEFAULT_LOCALE, "closing.default.answered")
    assert len(shown["categories"]) == 5


async def test_only_admins_change_the_settings_and_categories_hold_up(client, db_session, seeded):
    agent_h = await _headers(db_session, seeded["agent"])
    refused = await client.put(f"{seeded['base']}/settings", json={"enabled": True}, headers=agent_h)
    assert refused.status_code == 401

    admin_h = await _headers(db_session, seeded["admin"])
    url = f"{seeded['base']}/settings"
    twice = await client.put(
        url, json={"enabled": True, "categories": ["Venta", " venta "]}, headers=admin_h
    )
    assert twice.json()["code"] == "closing.duplicate_category"
    empty = await client.put(url, json={"enabled": True, "categories": ["  "]}, headers=admin_h)
    assert empty.json()["code"] == "closing.categories"
    saved = await client.put(
        url,
        json={"enabled": True, "required": True, "categories": ["Se inscribió", "  Pidió  precio "]},
        headers=admin_h,
    )
    assert saved.json() == {
        "enabled": True,
        "required": True,
        "categories": ["Se inscribió", "Pidió precio"],
    }


async def test_closing_with_a_reason_resolves_and_leaves_a_private_note(client, db_session, seeded):
    await _turn_on(client, db_session, seeded, categories=["Se inscribió", "Pidió precio"])
    agent_h = await _headers(db_session, seeded["agent"])
    conversation = seeded["conversation"]

    resp = await client.post(
        f"{seeded['base']}/{conversation.display_id}",
        json={"category": "Se inscribió", "note": "  Arranca en marzo, turno noche. "},
        headers=agent_h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "status": "resolved",
        "category": "Se inscribió",
        "note": "Arranca en marzo, turno noche.",
    }
    await db_session.refresh(conversation)
    assert conversation.status == CONVERSATION_STATUS_RESOLVED
    closing = (
        await db_session.exec(
            select(ConversationClosing).where(ConversationClosing.conversation_id == conversation.id)
        )
    ).one()
    assert closing.user_id == seeded["agent"].id
    note = await db_session.get(Message, closing.message_id)
    assert note.private is True
    assert note.content == (
        f"{t(DEFAULT_LOCALE, 'closing.note_title')}: Se inscribió\nArranca en marzo, turno noche."
    )


async def test_a_required_reason_and_one_from_the_list(client, db_session, seeded):
    await _turn_on(client, db_session, seeded, required=True, categories=["Se inscribió"])
    agent_h = await _headers(db_session, seeded["agent"])
    url = f"{seeded['base']}/{seeded['conversation'].display_id}"

    missing = await client.post(url, json={"note": "Sin motivo"}, headers=agent_h)
    assert missing.status_code == 422
    assert missing.json()["code"] == "closing.required"
    unknown = await client.post(url, json={"category": "Otra cosa"}, headers=agent_h)
    assert unknown.json()["code"] == "closing.category"
    await db_session.refresh(seeded["conversation"])
    assert seeded["conversation"].status != CONVERSATION_STATUS_RESOLVED


async def test_optional_reasons_let_it_close_without_one(client, db_session, seeded):
    await _turn_on(client, db_session, seeded)
    agent_h = await _headers(db_session, seeded["agent"])
    resp = await client.post(
        f"{seeded['base']}/{seeded['conversation'].display_id}", json={}, headers=agent_h
    )
    assert resp.json() == {"status": "resolved", "category": None, "note": None}
    rows = (await db_session.exec(select(ConversationClosing))).all()
    assert [r for r in rows if r.conversation_id == seeded["conversation"].id] == []


async def test_off_and_unseen_conversations_are_refused(client, db_session, seeded):
    agent_h = await _headers(db_session, seeded["agent"])
    url = f"{seeded['base']}/{seeded['conversation'].display_id}"
    off = await client.post(url, json={"category": "x"}, headers=agent_h)
    assert off.json()["code"] == "closing.disabled"

    await _turn_on(client, db_session, seeded)
    outsider_h = await _headers(db_session, seeded["outsider"])
    unseen = await client.post(url, json={}, headers=outsider_h)
    assert unseen.status_code == 404


async def test_the_report_counts_closings_by_reason(client, db_session, seeded):
    await _turn_on(client, db_session, seeded, categories=["Se inscribió", "Pidió precio"])
    agent_h = await _headers(db_session, seeded["agent"])
    conversation = seeded["conversation"]
    for category in ("Se inscribió", "Pidió precio", "Se inscribió", None):
        conversation.status = CONVERSATION_STATUS_OPEN  # as if the customer wrote back
        db_session.add(conversation)
        await db_session.flush()
        body = {"category": category} if category else {"note": "Volvió a escribir"}
        resp = await client.post(f"{seeded['base']}/{conversation.display_id}", json=body, headers=agent_h)
        assert resp.status_code == 200, resp.text

    report = (await client.get(f"{seeded['base']}/report?days=7", headers=agent_h)).json()
    assert report == {
        "days": 7,
        "total": 4,
        "categories": [
            {"category": "Se inscribió", "count": 2},
            {"category": "Pidió precio", "count": 1},
            {"category": None, "count": 1},
        ],
    }
