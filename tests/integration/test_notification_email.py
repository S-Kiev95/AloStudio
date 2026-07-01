"""Integration tests for the notification email worker.

Exercises ``send_notification_email`` directly (the ARQ task body just
wraps it in a session): it must send only when the recipient's
``NotificationSetting.email_subscriptions`` includes the notification's
type. SMTP is stubbed so no real mail server is needed.
"""

from __future__ import annotations

import pytest

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.notifications import mailer as mailer_mod
from app.domains.notifications.mailer import send_notification_email
from app.domains.notifications.models import (
    NOTIFICATION_TYPE_CONVERSATION_ASSIGNMENT,
    Notification,
    NotificationSetting,
)
from app.domains.teams import models as _teams  # noqa: F401  (mapper)

pytestmark = pytest.mark.integration


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@ne.example.com",
            account_name=f"NE{suffix}",
            user_full_name="Ana Agente",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="API",
                channel_type="api",
                channel_params={"webhook_url": "https://x.example.com"},
            ),
        ).perform()
    ).inbox
    contact = Contact(
        account_id=owner.account.id, name="C", email=f"c{suffix}@ne.example.com"
    )
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    await db_session.refresh(ci, ["inbox"])
    conv = await create_conversation(
        db_session, contact_inbox=ci, params=ConversationBuilderParams()
    )
    return owner, conv


def _make_notification(owner, conv) -> Notification:
    return Notification(
        account_id=owner.account.id,
        user_id=owner.user.id,
        notification_type=NOTIFICATION_TYPE_CONVERSATION_ASSIGNMENT,
        primary_actor_type="Conversation",
        primary_actor_id=conv.id,
    )


async def test_sends_email_when_subscribed(db_session, monkeypatch):
    owner, conv = await _seed(db_session, "-sub")
    notif = _make_notification(owner, conv)
    db_session.add(notif)
    db_session.add(
        NotificationSetting(
            account_id=owner.account.id,
            user_id=owner.user.id,
            email_subscriptions=["conversation_assignment"],
            push_subscriptions=[],
        )
    )
    await db_session.flush()

    captured: dict = {}

    async def fake_send(message, **kwargs):
        captured["msg"] = message

    monkeypatch.setattr(mailer_mod.aiosmtplib, "send", fake_send)

    sent = await send_notification_email(db_session, notification_id=notif.id)
    assert sent is True
    assert captured["msg"]["To"] == owner.user.email
    assert f"#{conv.display_id}" in captured["msg"]["Subject"]


async def test_skips_email_when_not_subscribed(db_session, monkeypatch):
    owner, conv = await _seed(db_session, "-nosub")
    notif = _make_notification(owner, conv)
    db_session.add(notif)
    db_session.add(
        NotificationSetting(
            account_id=owner.account.id,
            user_id=owner.user.id,
            email_subscriptions=[],  # not subscribed to anything
            push_subscriptions=[],
        )
    )
    await db_session.flush()

    called = False

    async def fake_send(message, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(mailer_mod.aiosmtplib, "send", fake_send)

    sent = await send_notification_email(db_session, notification_id=notif.id)
    assert sent is False
    assert called is False
