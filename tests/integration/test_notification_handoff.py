"""Integration tests for the bot handoff notice.

* ``conversation.bot_handoff`` → ``conversation_bot_handoff`` notification
  for the assignee, or every inbox member when nobody is assigned.
* ``PATCH /notification_settings`` — WhatsApp flags and number.
* ``send_notification_whatsapp`` — opt-in, needs the approved template.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations import events as ev
from app.domains.conversations.listeners import broadcast_event
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
)
from app.domains.inboxes.models import (
    WHATSAPP_PROVIDER_CLOUD,
    InboxMember,
    WhatsappChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.notifications import whatsapp as wa_notice
from app.domains.notifications.models import (
    NOTIFICATION_TYPE_CONVERSATION_BOT_HANDOFF,
    Notification,
)
from app.domains.notifications.service import (
    create_notification,
    get_or_create_settings,
)
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app

pytestmark = pytest.mark.integration

_TEMPLATE = {
    "name": "aviso_derivacion",
    "language": "es",
    "status": "APPROVED",
    "category": "UTILITY",
}


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


async def _seed_user(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"u{suffix}@handoff.example.com",
            account_name=f"Handoff{suffix}",
            user_full_name=f"U{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(user_tokens=owner.user.tokens, uid=owner.user.uid)
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _whatsapp_inbox(db_session, owner, *, templates: list[dict[str, Any]]):
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WA Instituto",
            channel_type="whatsapp",
            channel_params={
                "phone_number": "+59847325025",
                "provider": WHATSAPP_PROVIDER_CLOUD,
                "provider_config": {
                    "api_key": "EAAxxxx",
                    "phone_number_id": "p1",
                    "business_account_id": "b1",
                },
            },
        ),
    ).perform()
    assert isinstance(result.channel, WhatsappChannel)
    result.inbox.enable_auto_assignment = False
    result.channel.message_templates = templates
    db_session.add(result.inbox)
    db_session.add(result.channel)
    await db_session.flush()
    return result.inbox


async def _conversation(db_session, owner, inbox, *, assignee_id=None):
    contact = Contact(account_id=owner.account.id, name="Ana\nPérez")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox,
        source_id=f"5989900{contact.id}",
    ).perform()
    conv = await create_conversation(
        db_session, contact_inbox=ci, params=ConversationBuilderParams()
    )
    if assignee_id is not None:
        conv.assignee_id = assignee_id
        db_session.add(conv)
        await db_session.flush()
    return conv


async def _handoff_rows(db_session, conv) -> list[Notification]:
    return list(
        (
            await db_session.exec(
                select(Notification).where(
                    Notification.primary_actor_id == conv.id,
                    Notification.notification_type == NOTIFICATION_TYPE_CONVERSATION_BOT_HANDOFF,
                )
            )
        ).all()
    )


async def _with_member(db_session, owner, inbox, suffix: str):
    member, _ = await _seed_user(db_session, suffix)
    db_session.add(
        AccountUser(
            account_id=owner.account.id,
            user_id=member.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    db_session.add(InboxMember(inbox_id=inbox.id, user_id=member.user.id))
    await db_session.flush()
    return member.user


# ---------------------------------------------------------------------------
# Listener
# ---------------------------------------------------------------------------
async def test_handoff_without_assignee_notifies_every_inbox_member(db_session):
    owner, _ = await _seed_user(db_session, "-all-o")
    inbox = await _whatsapp_inbox(db_session, owner, templates=[])
    one = await _with_member(db_session, owner, inbox, "-all-1")
    two = await _with_member(db_session, owner, inbox, "-all-2")
    conv = await _conversation(db_session, owner, inbox)

    await broadcast_event(db_session, ev.CONVERSATION_BOT_HANDOFF, conversation=conv)

    rows = await _handoff_rows(db_session, conv)
    assert sorted(r.user_id for r in rows) == sorted([one.id, two.id])


async def test_handoff_with_assignee_notifies_only_the_assignee(db_session):
    owner, _ = await _seed_user(db_session, "-one-o")
    inbox = await _whatsapp_inbox(db_session, owner, templates=[])
    assignee = await _with_member(db_session, owner, inbox, "-one-1")
    await _with_member(db_session, owner, inbox, "-one-2")
    conv = await _conversation(db_session, owner, inbox, assignee_id=assignee.id)

    await broadcast_event(db_session, ev.CONVERSATION_BOT_HANDOFF, conversation=conv)

    rows = await _handoff_rows(db_session, conv)
    assert [r.user_id for r in rows] == [assignee.id]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
async def test_settings_store_whatsapp_flags_and_number(client, db_session):
    owner, headers = await _seed_user(db_session, "-set")
    url = f"/api/v1/accounts/{owner.account.id}/notification_settings"

    body = (await client.get(url, headers=headers)).json()
    # Opt-in: new users get every type by email/push but nothing on WhatsApp.
    assert "conversation_bot_handoff" in body["selected_push_flags"]
    assert body["selected_whatsapp_flags"] == []
    assert body["whatsapp_number"] is None

    res = await client.patch(
        url,
        headers=headers,
        json={
            "selected_whatsapp_flags": ["conversation_bot_handoff"],
            "whatsapp_number": "+598 99 123-456",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["selected_whatsapp_flags"] == ["conversation_bot_handoff"]
    assert body["whatsapp_number"] == "59899123456"

    bad = await client.patch(url, headers=headers, json={"whatsapp_number": "099"})
    assert bad.status_code == 422

    # Leaving the number out keeps it; an empty string clears it.
    res = await client.patch(url, headers=headers, json={"selected_push_flags": []})
    assert res.json()["whatsapp_number"] == "59899123456"
    res = await client.patch(url, headers=headers, json={"whatsapp_number": ""})
    assert res.json()["whatsapp_number"] is None


# ---------------------------------------------------------------------------
# WhatsApp delivery
# ---------------------------------------------------------------------------
async def _handoff_notification(db_session, suffix: str, *, templates, opted_in: bool):
    owner, _ = await _seed_user(db_session, suffix)
    inbox = await _whatsapp_inbox(db_session, owner, templates=templates)
    conv = await _conversation(db_session, owner, inbox)
    setting = await get_or_create_settings(
        db_session, account_id=owner.account.id, user_id=owner.user.id
    )
    setting.whatsapp_number = "59899123456"
    setting.whatsapp_subscriptions = ["conversation_bot_handoff"] if opted_in else []
    db_session.add(setting)
    notification = await create_notification(
        db_session,
        account_id=owner.account.id,
        user_id=owner.user.id,
        notification_type=NOTIFICATION_TYPE_CONVERSATION_BOT_HANDOFF,
        primary_actor_type="Conversation",
        primary_actor_id=conv.id,  # type: ignore[arg-type]
    )
    return notification, conv


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    async def _fake_send(session, **kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(wa_notice, "send_template_message", _fake_send)
    return calls


async def test_whatsapp_notice_goes_out_when_opted_in(db_session, sent):
    notification, conv = await _handoff_notification(
        db_session, "-wa-ok", templates=[_TEMPLATE], opted_in=True
    )

    assert await wa_notice.send_notification_whatsapp(db_session, notification_id=notification.id)
    assert len(sent) == 1
    call = sent[0]
    assert call["to_phone"] == "59899123456"
    assert call["message"] is None
    info = call["template_info"]
    assert info["name"] == "aviso_derivacion" and info["lang_code"] == "es"
    texts = [p["text"] for p in info["parameters"][0]["parameters"]]
    # The contact's newline is flattened: Meta refuses it in a parameter.
    assert texts == ["Ana Pérez", "WA Instituto", str(conv.display_id)]


async def test_whatsapp_notice_needs_opt_in(db_session, sent):
    notification, _ = await _handoff_notification(
        db_session, "-wa-off", templates=[_TEMPLATE], opted_in=False
    )
    assert not await wa_notice.send_notification_whatsapp(
        db_session, notification_id=notification.id
    )
    assert sent == []


async def test_whatsapp_notice_needs_the_approved_template(db_session, sent):
    pending = {**_TEMPLATE, "status": "PENDING"}
    notification, _ = await _handoff_notification(
        db_session, "-wa-pending", templates=[pending], opted_in=True
    )
    assert not await wa_notice.send_notification_whatsapp(
        db_session, notification_id=notification.id
    )
    assert sent == []
