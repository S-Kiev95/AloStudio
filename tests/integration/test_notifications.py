"""Integration tests for the notifications surface.

Anchors:
  app/domains/notifications/router.py
  app/domains/notifications/listener.py
  app/domains/notifications/service.py
"""

from __future__ import annotations

from collections.abc import AsyncIterator

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
from app.domains.conversations.models import (
    MESSAGE_TYPE_INCOMING,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
)
from app.domains.inboxes.models import InboxMember
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.notifications.models import (
    NOTIFICATION_TYPE_ASSIGNED_CONVERSATION_NEW_MESSAGE,
    NOTIFICATION_TYPE_CONVERSATION_ASSIGNMENT,
    NOTIFICATION_TYPE_CONVERSATION_CREATION,
    Notification,
)
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------
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
            email=f"u{suffix}@notif.example.com",
            account_name=f"Notif{suffix}",
            user_full_name=f"U{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _add_member(db_session, account, user, role: int = ACCOUNT_USER_ROLE_AGENT):
    db_session.add(
        AccountUser(account_id=account.id, user_id=user.id, role=role)
    )
    await db_session.flush()


async def _make_inbox_with_member(
    db_session, owner, member_user, *, auto_assign: bool = False
):
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API",
            channel_type="api",
            channel_params={"webhook_url": "https://x.example.com"},
        ),
    ).perform()
    # By default disable auto-assignment so ``create_conversation``
    # doesn't fire an extra ASSIGNEE_CHANGED event for the only inbox
    # member, which would otherwise pollute the per-test notification
    # count. ``auto_assign=True`` opts into the realistic default path
    # (see ``test_default_auto_assign_produces_two_notifications``).
    result.inbox.enable_auto_assignment = auto_assign
    db_session.add(result.inbox)
    db_session.add(InboxMember(inbox_id=result.inbox.id, user_id=member_user.id))
    await db_session.flush()
    return result.inbox


async def _make_conversation(db_session, owner, inbox, *, assignee_id=None):
    contact = Contact(account_id=owner.account.id, name="Test contact")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    conv = await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )
    if assignee_id is not None:
        conv.assignee_id = assignee_id
        db_session.add(conv)
        await db_session.flush()
    return conv, contact


# ---------------------------------------------------------------------------
# Listener — creates rows on the right events
# ---------------------------------------------------------------------------
async def test_conversation_created_notifies_every_inbox_member(
    client, db_session
):
    """create_conversation already dispatches CONVERSATION_CREATED, so
    the listener runs without us calling broadcast_event manually."""
    owner, _ = await _seed_user(db_session, "-cc-o")
    member, _ = await _seed_user(db_session, "-cc-m")
    await _add_member(db_session, owner.account, member.user)
    inbox = await _make_inbox_with_member(db_session, owner, member.user)
    conv, _contact = await _make_conversation(db_session, owner, inbox)

    rows = list(
        (
            await db_session.exec(
                select(Notification).where(
                    Notification.account_id == owner.account.id,
                    Notification.user_id == member.user.id,
                )
            )
        ).all()
    )
    assert len(rows) == 1
    assert (
        rows[0].notification_type
        == NOTIFICATION_TYPE_CONVERSATION_CREATION
    )
    assert rows[0].primary_actor_type == "Conversation"
    assert rows[0].primary_actor_id == conv.id


async def test_default_auto_assign_produces_two_notifications(
    client, db_session
):
    """Realistic default path (auto-assignment ON, the production
    default). Creating a conversation on an inbox whose only member is
    eligible auto-assigns it to that member, so they receive BOTH:

      * ``conversation_creation`` (from CONVERSATION_CREATED → members)
      * ``conversation_assignment`` (from the auto-assignment's
        ASSIGNEE_CHANGED dispatch)

    The listener intentionally does NOT dedup these — they're distinct
    events, matching Chatwoot. This documents/locks that behaviour so a
    future dedup change is a conscious decision, and covers the path the
    other tests skip by disabling auto-assignment.
    """
    owner, _ = await _seed_user(db_session, "-aa-o")
    member, _ = await _seed_user(db_session, "-aa-m")
    await _add_member(db_session, owner.account, member.user)
    inbox = await _make_inbox_with_member(
        db_session, owner, member.user, auto_assign=True
    )
    conv, _contact = await _make_conversation(db_session, owner, inbox)

    # The auto-assignment must actually have happened for this test to be
    # meaningful — guard against a silent regression where the member
    # stops being an eligible candidate.
    await db_session.refresh(conv)
    assert conv.assignee_id == member.user.id, (
        "expected auto-assignment to pick the sole inbox member"
    )

    rows = list(
        (
            await db_session.exec(
                select(Notification)
                .where(
                    Notification.account_id == owner.account.id,
                    Notification.user_id == member.user.id,
                )
                .order_by(Notification.notification_type)  # type: ignore[arg-type]
            )
        ).all()
    )
    types = {r.notification_type for r in rows}
    assert len(rows) == 2, f"expected creation + assignment, got {types}"
    assert NOTIFICATION_TYPE_CONVERSATION_CREATION in types
    assert NOTIFICATION_TYPE_CONVERSATION_ASSIGNMENT in types
    # Both point at the same conversation.
    assert all(r.primary_actor_id == conv.id for r in rows)


async def test_assignee_changed_notifies_the_new_assignee(
    client, db_session
):
    owner, _ = await _seed_user(db_session, "-ac-o")
    assignee, _ = await _seed_user(db_session, "-ac-a")
    await _add_member(db_session, owner.account, assignee.user)
    inbox = await _make_inbox_with_member(db_session, owner, assignee.user)
    conv, _ = await _make_conversation(
        db_session, owner, inbox, assignee_id=assignee.user.id
    )

    await broadcast_event(
        db_session, ev.ASSIGNEE_CHANGED, conversation=conv
    )

    rows = list(
        (
            await db_session.exec(
                select(Notification).where(
                    Notification.user_id == assignee.user.id,
                    Notification.notification_type
                    == NOTIFICATION_TYPE_CONVERSATION_ASSIGNMENT,
                )
            )
        ).all()
    )
    assert len(rows) == 1
    assert rows[0].primary_actor_id == conv.id


async def test_message_created_notifies_assignee_only_on_incoming(
    client, db_session
):
    owner, _ = await _seed_user(db_session, "-mc-o")
    assignee, _ = await _seed_user(db_session, "-mc-a")
    await _add_member(db_session, owner.account, assignee.user)
    inbox = await _make_inbox_with_member(db_session, owner, assignee.user)
    conv, contact = await _make_conversation(
        db_session, owner, inbox, assignee_id=assignee.user.id
    )

    incoming = Message(
        account_id=owner.account.id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_INCOMING,
        content="hola",
        sender_type="Contact",
        sender_id=contact.id,
    )
    db_session.add(incoming)
    await db_session.flush()
    incoming.conversation = conv  # type: ignore[assignment]

    await broadcast_event(
        db_session, ev.MESSAGE_CREATED, message=incoming
    )

    rows = list(
        (
            await db_session.exec(
                select(Notification).where(
                    Notification.user_id == assignee.user.id,
                    Notification.notification_type
                    == NOTIFICATION_TYPE_ASSIGNED_CONVERSATION_NEW_MESSAGE,
                )
            )
        ).all()
    )
    assert len(rows) == 1
    assert rows[0].secondary_actor_type == "Message"
    assert rows[0].secondary_actor_id == incoming.id


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------
async def test_index_and_unread_count(client, db_session):
    owner, headers = await _seed_user(db_session, "-idx-o")
    inbox = await _make_inbox_with_member(db_session, owner, owner.user)
    conv, _ = await _make_conversation(db_session, owner, inbox)
    # create_conversation already dispatches CONVERSATION_CREATED.

    res = await client.get(
        f"/api/v1/accounts/{owner.account.id}/notifications", headers=headers
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["meta"]["count"] == 1
    assert body["meta"]["unread_count"] == 1
    assert len(body["payload"]) == 1
    row = body["payload"][0]
    assert row["notification_type"] == "conversation_creation"
    assert row["primary_actor"]["id"] == conv.id

    # Bare unread_count endpoint mirrors Rails' int return.
    res = await client.get(
        f"/api/v1/accounts/{owner.account.id}/notifications/unread_count",
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json() == 1


async def test_mark_read_flips_read_at(client, db_session):
    owner, headers = await _seed_user(db_session, "-mr-o")
    inbox = await _make_inbox_with_member(db_session, owner, owner.user)
    _conv, _ = await _make_conversation(db_session, owner, inbox)
    nid = (
        await db_session.exec(
            select(Notification).where(
                Notification.account_id == owner.account.id,
                Notification.user_id == owner.user.id,
            )
        )
    ).first().id

    res = await client.post(
        f"/api/v1/accounts/{owner.account.id}/notifications/{nid}/read",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["read_at"] is not None


async def test_read_all_clears_unread(client, db_session):
    owner, headers = await _seed_user(db_session, "-ra-o")
    inbox = await _make_inbox_with_member(db_session, owner, owner.user)
    # Create three conversations → three notifications (each
    # create_conversation auto-dispatches CONVERSATION_CREATED).
    for _ in range(3):
        await _make_conversation(db_session, owner, inbox)

    res = await client.post(
        f"/api/v1/accounts/{owner.account.id}/notifications/read_all",
        headers=headers,
    )
    assert res.status_code == 200

    res = await client.get(
        f"/api/v1/accounts/{owner.account.id}/notifications/unread_count",
        headers=headers,
    )
    assert res.json() == 0


async def test_destroy_removes_the_row(client, db_session):
    owner, headers = await _seed_user(db_session, "-d-o")
    inbox = await _make_inbox_with_member(db_session, owner, owner.user)
    _conv, _ = await _make_conversation(db_session, owner, inbox)
    nid = (
        await db_session.exec(
            select(Notification).where(
                Notification.account_id == owner.account.id,
                Notification.user_id == owner.user.id,
            )
        )
    ).first().id

    res = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/notifications/{nid}",
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json() == {}

    surviving = (
        await db_session.exec(
            select(Notification).where(Notification.id == nid)
        )
    ).first()
    assert surviving is None


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
async def test_settings_get_creates_default_then_patch(client, db_session):
    owner, headers = await _seed_user(db_session, "-ns-o")

    # First GET lazily seeds defaults — all 8 notification types subscribed.
    res = await client.get(
        f"/api/v1/accounts/{owner.account.id}/notification_settings",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "conversation_creation" in body["selected_email_flags"]
    assert "conversation_assignment" in body["selected_push_flags"]

    # Narrow the email list down.
    res = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/notification_settings",
        headers=headers,
        json={
            "selected_email_flags": ["conversation_assignment"],
            "selected_push_flags": [
                "conversation_creation",
                "conversation_assignment",
            ],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["selected_email_flags"] == ["conversation_assignment"]
    assert sorted(body["selected_push_flags"]) == [
        "conversation_assignment",
        "conversation_creation",
    ]
