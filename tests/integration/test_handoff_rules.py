"""Integration tests for the handoff responsibles (PLAN.agente-ia.md, 2a).

* ``bot_handoff`` assigns by chat, then label, then inbox, then account,
  and leaves a line saying which rule chose (not for the inbox level).
* A rule that can't be used (person out of the account, AloStudio's AI
  when it isn't there) passes to the next level.
* ``/handoff`` — administrators only, validates targets and labels.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import delete, select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import MESSAGE_TYPE_ACTIVITY, Message
from app.domains.conversations.service import (
    ConversationBuilderParams,
    bot_handoff,
    create_conversation,
)
from app.domains.handoff.models import (
    SCOPE_ACCOUNT,
    SCOPE_CONTACT,
    SCOPE_LABEL,
    HandoffRule,
)
from app.domains.inboxes.models import InboxMember
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.labels.models import Label
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


async def _seed_user(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"u{suffix}@handoff-rules.example.com",
            account_name=f"Rules{suffix}",
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


async def _inbox(db_session, owner):
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Web",
            channel_type="web_widget",
            channel_params={"website_url": "https://ctc.example.com"},
        ),
    ).perform()
    result.inbox.enable_auto_assignment = False
    db_session.add(result.inbox)
    await db_session.flush()
    return result.inbox


async def _member(db_session, owner, inbox, suffix: str):
    member, headers = await _seed_user(db_session, suffix)
    db_session.add(
        AccountUser(
            account_id=owner.account.id, user_id=member.user.id, role=ACCOUNT_USER_ROLE_AGENT
        )
    )
    db_session.add(InboxMember(inbox_id=inbox.id, user_id=member.user.id))
    await db_session.flush()
    return member.user, headers


async def _conversation(db_session, owner, inbox, *, labels: str = ""):
    contact = Contact(account_id=owner.account.id, name="Ana")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox, source_id=f"web-{contact.id}"
    ).perform()
    conv = await create_conversation(db_session, contact_inbox=ci, params=ConversationBuilderParams())
    conv.cached_label_list = labels
    db_session.add(conv)
    await db_session.flush()
    return conv


async def _label(db_session, owner, title: str) -> Label:
    label = Label(account_id=owner.account.id, title=title)
    db_session.add(label)
    await db_session.flush()
    return label


def _rule(owner, scope: str, **kw) -> HandoffRule:
    return HandoffRule(account_id=owner.account.id, scope=scope, **kw)


async def _activities(db_session, conv) -> list[str]:
    rows = (
        await db_session.exec(
            select(Message.content).where(
                Message.conversation_id == conv.id,
                Message.message_type == MESSAGE_TYPE_ACTIVITY,
            )
        )
    ).all()
    return [r or "" for r in rows]


# ---------------------------------------------------------------------------
# bot_handoff
# ---------------------------------------------------------------------------
async def test_label_rule_wins_over_the_inbox_and_says_why(db_session):
    owner, _ = await _seed_user(db_session, "-lab-o")
    inbox = await _inbox(db_session, owner)
    sofia, _ = await _member(db_session, owner, inbox, "-lab-1")
    yamila, _ = await _member(db_session, owner, inbox, "-lab-2")
    inbox.handoff_assignee_id = sofia.id
    db_session.add(inbox)
    admin = await _label(db_session, owner, "admin")
    other = await _label(db_session, owner, "ventas")
    db_session.add(_rule(owner, SCOPE_LABEL, label_id=other.id, user_id=sofia.id, position=0))
    db_session.add(_rule(owner, SCOPE_LABEL, label_id=admin.id, user_id=yamila.id, position=1))
    await db_session.flush()
    conv = await _conversation(db_session, owner, inbox, labels="Admin")

    await bot_handoff(db_session, conversation=conv)

    assert conv.assignee_id == yamila.id
    assert "Derivada por la etiqueta admin" in await _activities(db_session, conv)


async def test_first_label_rule_in_order_wins(db_session):
    owner, _ = await _seed_user(db_session, "-ord-o")
    inbox = await _inbox(db_session, owner)
    one, _ = await _member(db_session, owner, inbox, "-ord-1")
    two, _ = await _member(db_session, owner, inbox, "-ord-2")
    a = await _label(db_session, owner, "a")
    b = await _label(db_session, owner, "b")
    db_session.add(_rule(owner, SCOPE_LABEL, label_id=b.id, user_id=two.id, position=0))
    db_session.add(_rule(owner, SCOPE_LABEL, label_id=a.id, user_id=one.id, position=1))
    await db_session.flush()
    conv = await _conversation(db_session, owner, inbox, labels="a,b")

    await bot_handoff(db_session, conversation=conv)

    assert conv.assignee_id == two.id


async def test_chat_rule_wins_over_labels(db_session):
    owner, _ = await _seed_user(db_session, "-chat-o")
    inbox = await _inbox(db_session, owner)
    sofia, _ = await _member(db_session, owner, inbox, "-chat-1")
    yamila, _ = await _member(db_session, owner, inbox, "-chat-2")
    admin = await _label(db_session, owner, "admin")
    db_session.add(_rule(owner, SCOPE_LABEL, label_id=admin.id, user_id=yamila.id))
    await db_session.flush()
    conv = await _conversation(db_session, owner, inbox, labels="admin")
    db_session.add(_rule(owner, SCOPE_CONTACT, contact_id=conv.contact_id, user_id=sofia.id))
    await db_session.flush()

    await bot_handoff(db_session, conversation=conv)

    assert conv.assignee_id == sofia.id
    assert "Derivada al responsable de este chat" in await _activities(db_session, conv)


async def test_inbox_wins_over_account_and_adds_no_reason_line(db_session):
    owner, _ = await _seed_user(db_session, "-inb-o")
    inbox = await _inbox(db_session, owner)
    sofia, _ = await _member(db_session, owner, inbox, "-inb-1")
    yamila, _ = await _member(db_session, owner, inbox, "-inb-2")
    inbox.handoff_assignee_id = sofia.id
    db_session.add(inbox)
    db_session.add(_rule(owner, SCOPE_ACCOUNT, user_id=yamila.id))
    await db_session.flush()
    conv = await _conversation(db_session, owner, inbox)

    await bot_handoff(db_session, conversation=conv)

    assert conv.assignee_id == sofia.id
    assert not [a for a in await _activities(db_session, conv) if a.startswith("Derivada")]


async def test_account_rule_takes_the_rest(db_session):
    owner, _ = await _seed_user(db_session, "-acc-o")
    inbox = await _inbox(db_session, owner)
    sofia, _ = await _member(db_session, owner, inbox, "-acc-1")
    db_session.add(_rule(owner, SCOPE_ACCOUNT, user_id=sofia.id))
    await db_session.flush()
    conv = await _conversation(db_session, owner, inbox, labels="sin-regla")

    await bot_handoff(db_session, conversation=conv)

    assert conv.assignee_id == sofia.id
    assert "Derivada al responsable general" in await _activities(db_session, conv)


async def test_unusable_rules_pass_to_the_next_level(db_session):
    owner, _ = await _seed_user(db_session, "-skip-o")
    inbox = await _inbox(db_session, owner)
    gone, _ = await _member(db_session, owner, inbox, "-skip-1")
    sofia, _ = await _member(db_session, owner, inbox, "-skip-2")
    admin = await _label(db_session, owner, "admin")
    db_session.add(_rule(owner, SCOPE_LABEL, label_id=admin.id, user_id=gone.id))
    db_session.add(_rule(owner, SCOPE_ACCOUNT, user_id=sofia.id))
    await db_session.flush()
    conv = await _conversation(db_session, owner, inbox, labels="admin")
    # The chat names the AI (not there, and the AI itself is handing off)
    # and the label's person left the account.
    db_session.add(_rule(owner, SCOPE_CONTACT, contact_id=conv.contact_id, to_ai=True))
    await db_session.exec(  # type: ignore[call-overload]
        delete(AccountUser).where(AccountUser.user_id == gone.id)  # type: ignore[arg-type]
    )
    await db_session.flush()

    await bot_handoff(db_session, conversation=conv)

    assert conv.assignee_id == sofia.id


async def test_no_rule_leaves_it_unassigned(db_session):
    owner, _ = await _seed_user(db_session, "-none-o")
    inbox = await _inbox(db_session, owner)
    await _member(db_session, owner, inbox, "-none-1")
    conv = await _conversation(db_session, owner, inbox)

    await bot_handoff(db_session, conversation=conv)

    assert conv.assignee_id is None


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
async def test_admin_saves_account_label_and_chat_rules(client, db_session):
    owner, headers = await _seed_user(db_session, "-api-o")
    inbox = await _inbox(db_session, owner)
    sofia, _ = await _member(db_session, owner, inbox, "-api-1")
    yamila, _ = await _member(db_session, owner, inbox, "-api-2")
    admin = await _label(db_session, owner, "admin")
    ventas = await _label(db_session, owner, "ventas")
    conv = await _conversation(db_session, owner, inbox)
    base = f"/api/v1/accounts/{owner.account.id}/handoff"

    rules = [
        {"label_id": ventas.id, "user_id": sofia.id},
        {"label_id": admin.id, "user_id": yamila.id},
    ]
    res = await client.put(
        base, headers=headers, json={"account": {"user_id": sofia.id}, "labels": rules}
    )
    assert res.status_code == 200, res.text
    assert res.json()["account"] == {"user_id": sofia.id, "to_ai": False}
    assert [r["label_id"] for r in res.json()["labels"]] == [ventas.id, admin.id]

    url = f"{base}/contacts/{conv.contact_id}"
    res = await client.put(url, headers=headers, json={"user_id": yamila.id})
    assert res.status_code == 200, res.text
    res = await client.get(url, headers=headers)
    assert res.json() == {"contact": {"user_id": yamila.id, "to_ai": False}, "ai_available": False}

    res = await client.get(base, headers=headers)
    body = res.json()
    assert body["account"]["user_id"] == sofia.id
    assert [r["user_id"] for r in body["labels"]] == [sofia.id, yamila.id]

    # Empty clears.
    res = await client.put(url, headers=headers, json={})
    assert res.json() == {"contact": None}
    res = await client.put(base, headers=headers, json={"account": {}, "labels": []})
    assert res.json() == {"account": None, "labels": [], "ai_available": False}


async def test_a_refused_save_writes_nothing(client, db_session):
    owner, headers = await _seed_user(db_session, "-atom-o")
    inbox = await _inbox(db_session, owner)
    sofia, _ = await _member(db_session, owner, inbox, "-atom-1")
    admin = await _label(db_session, owner, "admin")
    base = f"/api/v1/accounts/{owner.account.id}/handoff"

    res = await client.put(
        base,
        headers=headers,
        json={"account": {"user_id": sofia.id}, "labels": [{"label_id": admin.id}]},
    )

    assert res.status_code == 422
    assert (await client.get(base, headers=headers)).json()["account"] is None


async def test_a_person_who_left_shows_as_no_one(client, db_session):
    owner, headers = await _seed_user(db_session, "-left-o")
    inbox = await _inbox(db_session, owner)
    gone, _ = await _member(db_session, owner, inbox, "-left-1")
    admin = await _label(db_session, owner, "admin")
    db_session.add(_rule(owner, SCOPE_ACCOUNT, user_id=gone.id))
    db_session.add(_rule(owner, SCOPE_LABEL, label_id=admin.id, user_id=gone.id))
    await db_session.exec(  # type: ignore[call-overload]
        delete(AccountUser).where(AccountUser.user_id == gone.id)  # type: ignore[arg-type]
    )
    await db_session.flush()

    body = (await client.get(f"/api/v1/accounts/{owner.account.id}/handoff", headers=headers)).json()

    assert body["account"] == {"user_id": None, "to_ai": False}
    assert body["labels"] == [{"label_id": admin.id, "user_id": None, "to_ai": False}]


@pytest.mark.parametrize(
    ("case", "code"),
    [
        ("stranger", "handoff.not_a_member"),
        ("ai", "handoff.ai_unavailable"),
        ("both", "handoff.one_target"),
        ("repeated", "handoff.repeated_label"),
        ("unknown", "handoff.unknown_label"),
        ("empty", "handoff.no_target"),
    ],
)
async def test_invalid_rules_are_refused(client, db_session, case, code):
    owner, headers = await _seed_user(db_session, f"-bad-{case}-o")
    inbox = await _inbox(db_session, owner)
    sofia, _ = await _member(db_session, owner, inbox, f"-bad-{case}-1")
    stranger, _ = await _seed_user(db_session, f"-bad-{case}-x")
    admin = await _label(db_session, owner, "admin")
    foreign = await _label(db_session, stranger, "ajena")
    base = f"/api/v1/accounts/{owner.account.id}/handoff"
    rule = {"label_id": admin.id, "user_id": sofia.id}
    payload = {
        "stranger": [{**rule, "user_id": stranger.user.id}],
        "ai": [{"label_id": admin.id, "to_ai": True}],
        "both": [{**rule, "to_ai": True}],
        "repeated": [rule, rule],
        "unknown": [{**rule, "label_id": foreign.id}],
        "empty": [{"label_id": admin.id}],
    }[case]

    res = await client.put(base, headers=headers, json={"account": {}, "labels": payload})

    assert res.status_code == 422, res.text
    assert code in res.text


async def test_agents_cannot_see_or_change_rules(client, db_session):
    owner, _ = await _seed_user(db_session, "-agt-o")
    inbox = await _inbox(db_session, owner)
    _, agent_headers = await _member(db_session, owner, inbox, "-agt-1")
    base = f"/api/v1/accounts/{owner.account.id}/handoff"

    assert (await client.get(base, headers=agent_headers)).status_code == 401
    res = await client.put(base, headers=agent_headers, json={"account": {}, "labels": []})
    assert res.status_code == 401
