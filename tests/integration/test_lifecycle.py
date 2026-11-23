"""Contact lifecycle (F17): stages from new lead to customer."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.core.i18n import DEFAULT_LOCALE, t
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import MESSAGE_TYPE_ACTIVITY, Message
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
)
from app.domains.inboxes.models import InboxMember
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.lifecycle import service as lifecycle
from app.domains.lifecycle.models import ContactLifecycle, LifecycleChange
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
            email="admin@stages.example.com",
            account_name="Instituto",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="sofia@stages.example.com",
            account_name="Otra",
            user_full_name="Sofía",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(account_id=owner.account.id, user_id=agent.user.id, role=ACCOUNT_USER_ROLE_AGENT)
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
        "contact": contact,
        "conversation": conversation,
        "base": f"/api/v1/accounts/{owner.account.id}/lifecycle",
    }


async def _turn_on(db_session, seeded, stages=None) -> None:
    await lifecycle.save_settings(
        db_session, account_id=seeded["account"].id, enabled=True, stages=stages
    )


async def _stage_key(db_session, contact_id: int) -> str | None:
    row = await db_session.get(ContactLifecycle, contact_id)
    return row.stage_key if row else None


async def test_respond_ios_stages_come_first_and_admins_shape_them(client, db_session, seeded):
    agent_h = await _headers(db_session, seeded["agent"])
    shown = (await client.get(f"{seeded['base']}/settings", headers=agent_h)).json()
    assert shown["enabled"] is False
    assert [(s["key"], s["kind"], s["default"]) for s in shown["stages"]] == [
        ("new_lead", "stage", True),
        ("hot_lead", "stage", False),
        ("payment", "stage", False),
        ("customer", "stage", False),
        ("cold_lead", "lost", False),
    ]
    assert shown["stages"][0]["name"] == t(DEFAULT_LOCALE, "lifecycle.default.new_lead.name")

    url = f"{seeded['base']}/settings"
    refused = await client.put(url, json={"enabled": True}, headers=agent_h)
    assert refused.status_code == 401

    admin_h = await _headers(db_session, seeded["admin"])
    stages = shown["stages"]
    twice = await client.put(
        url,
        json={"enabled": True, "stages": [{**stages[0]}, {**stages[1], "name": f" {stages[0]['name']} "}]},
        headers=admin_h,
    )
    assert twice.json()["code"] == "lifecycle.duplicate_name"
    lost_default = await client.put(
        url,
        json={"enabled": True, "stages": [{**stages[0], "default": False}, {**stages[4], "default": True}]},
        headers=admin_h,
    )
    assert lost_default.json()["code"] == "lifecycle.default"
    only_lost = await client.put(url, json={"enabled": True, "stages": [stages[4]]}, headers=admin_h)
    assert only_lost.json()["code"] == "lifecycle.no_stage"

    renamed = [
        {**stages[0], "name": "Consultó"},
        stages[1],
        {"name": "Se inscribió", "emoji": "🎓", "kind": "stage"},
        stages[4],
    ]
    saved = await client.put(url, json={"enabled": True, "stages": renamed}, headers=admin_h)
    assert saved.status_code == 200, saved.text
    assert [(s["key"], s["name"]) for s in saved.json()["stages"]] == [
        ("new_lead", "Consultó"),
        ("hot_lead", stages[1]["name"]),
        ("se_inscribio", "Se inscribió"),
        ("cold_lead", stages[4]["name"]),
    ]


async def test_moving_a_contact_leaves_a_line_and_the_history(client, db_session, seeded):
    agent_h = await _headers(db_session, seeded["agent"])
    contact, conversation = seeded["contact"], seeded["conversation"]
    url = f"{seeded['base']}/contacts/{contact.id}"

    off = await client.put(url, json={"stage_key": "hot_lead"}, headers=agent_h)
    assert off.json()["code"] == "lifecycle.disabled"

    await _turn_on(db_session, seeded)
    moved = await client.put(
        url,
        json={"stage_key": "hot_lead", "conversation_id": conversation.display_id},
        headers=agent_h,
    )
    assert moved.status_code == 200, moved.text
    body = moved.json()
    assert body["stage"]["key"] == "hot_lead"
    assert body["changed_by"]["name"] == "Sofía"
    shown = (await client.get(url, headers=agent_h)).json()
    assert shown["stage"]["key"] == "hot_lead"

    unknown = await client.put(url, json={"stage_key": "vip"}, headers=agent_h)
    assert unknown.json()["code"] == "lifecycle.stage"
    cleared = await client.put(
        url, json={"stage_key": None, "conversation_id": conversation.display_id}, headers=agent_h
    )
    assert cleared.json()["stage"] is None

    lines = (
        await db_session.exec(
            select(Message.content)
            .where(
                Message.conversation_id == conversation.id,
                Message.message_type == MESSAGE_TYPE_ACTIVITY,
            )
            .order_by(Message.id)  # type: ignore[arg-type]
        )
    ).all()
    hot = t(DEFAULT_LOCALE, "lifecycle.default.hot_lead.name")
    assert lines[-2:] == [
        t(DEFAULT_LOCALE, "lifecycle.activity", name="Sofía", stage=hot),
        t(DEFAULT_LOCALE, "lifecycle.activity_cleared", name="Sofía"),
    ]
    history = (
        await db_session.exec(
            select(LifecycleChange.from_key, LifecycleChange.to_key)
            .where(LifecycleChange.contact_id == contact.id)
            .order_by(LifecycleChange.id)  # type: ignore[arg-type]
        )
    ).all()
    assert [tuple(h) for h in history] == [(None, "hot_lead"), ("hot_lead", None)]

    stranger = await client.put(
        f"{seeded['base']}/contacts/999999", json={"stage_key": "hot_lead"}, headers=agent_h
    )
    assert stranger.status_code == 404


async def test_a_first_message_puts_the_contact_in_the_default_stage(db_session, seeded):
    contact, conversation = seeded["contact"], seeded["conversation"]

    async def customer_writes() -> None:
        await create_message(
            db_session,
            conversation=conversation,
            params=MessageBuilderParams(content="Hola, ¿cuánto sale?", message_type="incoming"),
            user_id=None,
        )

    await customer_writes()
    assert await _stage_key(db_session, contact.id) is None, "off: nothing happens"

    await _turn_on(db_session, seeded)
    await customer_writes()
    assert await _stage_key(db_session, contact.id) == "new_lead"

    # Moved on by someone: a later message does not send them back.
    await lifecycle.set_stage(
        db_session,
        account_id=seeded["account"].id,
        contact=contact,
        stage_key="customer",
        user=seeded["agent"],
    )
    await customer_writes()
    assert await _stage_key(db_session, contact.id) == "customer"


async def test_a_removed_stage_lets_its_contacts_go_and_the_report_counts(client, db_session, seeded):
    await _turn_on(db_session, seeded)
    contact = seeded["contact"]
    for key in ("new_lead", "payment"):
        await lifecycle.set_stage(
            db_session,
            account_id=seeded["account"].id,
            contact=contact,
            stage_key=key,
            user=seeded["admin"],
        )
    agent_h = await _headers(db_session, seeded["agent"])
    report = (await client.get(f"{seeded['base']}/report?days=7", headers=agent_h)).json()
    counts = {s["key"]: (s["count"], s["entered"]) for s in report["stages"]}
    assert counts["payment"] == (1, 1)
    assert counts["new_lead"] == (0, 1)
    assert report["enabled"] is True

    stages = (await lifecycle.present_settings(db_session, seeded["account"].id))["stages"]
    await lifecycle.save_settings(
        db_session,
        account_id=seeded["account"].id,
        enabled=True,
        stages=[s for s in stages if s["key"] != "payment"],
    )
    assert await _stage_key(db_session, contact.id) is None


async def test_the_contacts_list_filters_by_stage(client, db_session, seeded):
    await _turn_on(db_session, seeded)
    other = Contact(account_id=seeded["account"].id, name="Pedro Gómez")
    db_session.add(other)
    await db_session.flush()
    await lifecycle.set_stage(
        db_session,
        account_id=seeded["account"].id,
        contact=seeded["contact"],
        stage_key="hot_lead",
        user=seeded["admin"],
    )
    headers = await _headers(db_session, seeded["agent"])
    url = f"/api/v1/accounts/{seeded['account'].id}/contacts"

    hot = (await client.get(f"{url}?stage=hot_lead", headers=headers)).json()
    assert [c["name"] for c in hot["payload"]] == ["Lucía Pereira"]
    assert hot["meta"]["count"] == 1
    assert (await client.get(f"{url}?stage=customer", headers=headers)).json()["payload"] == []
    everyone = (await client.get(url, headers=headers)).json()
    assert {c["name"] for c in everyone["payload"]} >= {"Lucía Pereira", "Pedro Gómez"}


async def test_stages_carry_no_emojis(client, db_session, seeded):
    admin_h = await _headers(db_session, seeded["admin"])
    url = f"{seeded['base']}/settings"
    shown = (await client.get(url, headers=admin_h)).json()
    assert {s["emoji"] for s in shown["stages"]} == {""}
    saved = await client.put(
        url,
        json={"enabled": True, "stages": [{**shown["stages"][0], "emoji": "🎓"}]},
        headers=admin_h,
    )
    assert saved.json()["stages"][0]["emoji"] == ""
