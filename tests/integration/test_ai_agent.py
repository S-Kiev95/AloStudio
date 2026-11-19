"""Integration tests for AloStudio's AI answering customers (PLAN.agente-ia.md, 2b.1).

* A live AI bot on an inbox takes new conversations as ``pending`` (when
  its "when it answers" holds); shadow takes nothing.
* A customer message queues a run; the run answers as the bot, or hands
  off to a person with a private summary; a model failure hands off too.
* A person's reply makes the AI step aside.
* Shadow leaves a suggestion; sending it as is, edited, discarding it or
  writing something else settles it.
* A handoff rule may name the AI when Meta's agent hands off, never when
  the AI itself does.
* Bots of type AI from the API.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core import llm
from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.agent_bots.models import (
    AGENT_BOT_TYPE_AI,
    AgentBot,
    AgentBotInbox,
)
from app.domains.agent_bots.service import detach_bot_from_inbox, update_bot
from app.domains.ai_agent import service as ai
from app.domains.ai_agent import tools as ai_tools
from app.domains.ai_agent.models import (
    STATUS_ANSWERED,
    STATUS_DISCARDED,
    STATUS_EDITED,
    STATUS_FAILED,
    STATUS_HANDOFF,
    STATUS_SENT,
    STATUS_SUGGESTED,
    STATUS_SUPERSEDED,
    AiReply,
)
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    CONVERSATION_STATUS_OPEN,
    CONVERSATION_STATUS_PENDING,
    CONVERSATION_STATUS_RESOLVED,
    MESSAGE_TYPE_ACTIVITY,
    SENDER_TYPE_AGENT_BOT,
    Message,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    bot_handoff,
    create_conversation,
    create_message,
    update_assignee,
)
from app.domains.handoff.models import SCOPE_ACCOUNT, HandoffRule
from app.domains.inboxes.models import InboxMember
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.products.models import Product
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_AGENT,
    USER_AVAILABILITY_OFFLINE,
    AccountUser,
)
from app.domains.working_hours.models import WorkingHour
from app.domains.working_hours.service import open_at
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


@pytest.fixture
def queued(monkeypatch) -> list[tuple[int, int]]:
    """The runs queued (they wait for a commit the tests never make).
    The AI needs the OpenAI key to take anything."""
    runs: list[tuple[int, int]] = []

    def fake_enqueue(session, *, conversation_id: int, message_id: int) -> None:
        runs.append((conversation_id, message_id))

    monkeypatch.setattr("app.workers.ai_agent.enqueue_after_commit", fake_enqueue)
    monkeypatch.setattr(get_settings(), "openai_api_key", "sk-test")
    return runs


class FakeModel:
    """Scripted model answers; records what it was sent."""

    def __init__(self) -> None:
        self.replies: list[dict[str, Any] | Exception] = []
        self.calls: list[list[dict[str, Any]]] = []

    async def __call__(self, *, messages, tools=None, tool_choice=None) -> dict[str, Any]:
        self.calls.append(list(messages))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            # Something happens while the model thinks.
            return await reply()
        return reply


@pytest.fixture
def model(monkeypatch) -> FakeModel:
    fake = FakeModel()
    monkeypatch.setattr(get_settings(), "openai_api_key", "sk-test")
    monkeypatch.setattr(llm, "chat_completion", fake)
    return fake


def _call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": "",
        "tool_calls": [
            {
                "id": f"call-{name}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ],
    }


async def _seed_user(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"u{suffix}@ai-agent.example.com",
            account_name=f"Negocio{suffix}",
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


async def _inbox(db_session, owner, *, auto_assign: bool = True):
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API",
            channel_type="api",
            channel_params={"webhook_url": "https://x.example.com"},
        ),
    ).perform()
    result.inbox.enable_auto_assignment = auto_assign
    db_session.add(result.inbox)
    await db_session.flush()
    return result.inbox


async def _ai_bot(db_session, owner, inbox, **config) -> AgentBot:
    bot = AgentBot(
        account_id=owner.account.id,
        name="Sofi",
        bot_type=AGENT_BOT_TYPE_AI,
        bot_config={"instructions": "Vendemos cursos.", "mode": "live", **config},
    )
    db_session.add(bot)
    await db_session.flush()
    db_session.add(AgentBotInbox(account_id=owner.account.id, inbox_id=inbox.id, agent_bot_id=bot.id))
    await db_session.flush()
    return bot


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


async def _conversation(db_session, owner, inbox):
    contact = Contact(account_id=owner.account.id, name="Ana")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox, source_id=f"api-{contact.id}"
    ).perform()
    return await create_conversation(db_session, contact_inbox=ci, params=ConversationBuilderParams())


async def _incoming(db_session, conv, text: str) -> Message:
    return await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(content=text, message_type="incoming"),
        user_id=None,
    )


async def _reply(db_session, conv, user, text: str, **attrs) -> Message:
    return await create_message(
        db_session,
        conversation=conv,
        params=MessageBuilderParams(
            content=text, message_type="outgoing", content_attributes=attrs or None
        ),
        user_id=user.id,
    )


async def _contents(db_session, conversation_id: int) -> list[str | None]:
    """Fresh from the database (a run's rollback expires loaded rows)."""
    return list(
        (await db_session.exec(select(Message.content).where(Message.conversation_id == conversation_id))).all()
    )


async def _messages(db_session, conv) -> list[Message]:
    return list(
        (
            await db_session.exec(
                select(Message).where(Message.conversation_id == conv.id).order_by(Message.id)
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# Who holds the conversation
# ---------------------------------------------------------------------------
async def test_live_ai_takes_new_conversations_and_auto_assignment_skips_them(db_session, queued):
    owner, _ = await _seed_user(db_session, "take")
    inbox = await _inbox(db_session, owner)
    await _member(db_session, owner, inbox, "take-m")
    bot = await _ai_bot(db_session, owner, inbox)

    conv = await _conversation(db_session, owner, inbox)

    assert conv.status == CONVERSATION_STATUS_PENDING
    assert conv.assignee_agent_bot_id == bot.id
    assert conv.assignee_id is None

    message = await _incoming(db_session, conv, "Hola, ¿cuánto sale el curso?")
    assert queued == [(conv.id, message.id)]


async def test_shadow_and_webhook_bots_take_nothing(db_session, queued):
    owner, _ = await _seed_user(db_session, "shadow-take")
    inbox = await _inbox(db_session, owner, auto_assign=False)
    await _ai_bot(db_session, owner, inbox, mode="shadow")

    conv = await _conversation(db_session, owner, inbox)

    assert conv.status == CONVERSATION_STATUS_OPEN
    assert conv.assignee_agent_bot_id is None
    # Shadow still proposes an answer to each customer message.
    message = await _incoming(db_session, conv, "Hola")
    assert queued == [(conv.id, message.id)]


async def test_nobody_available_answers_only_when_nobody_is_online(db_session, queued):
    owner, _ = await _seed_user(db_session, "avail")
    inbox = await _inbox(db_session, owner, auto_assign=False)
    member, _ = await _member(db_session, owner, inbox, "avail-m")
    await _ai_bot(db_session, owner, inbox, respond_when="nobody_available")

    first = await _conversation(db_session, owner, inbox)
    assert first.status == CONVERSATION_STATUS_OPEN

    row = (
        await db_session.exec(
            select(AccountUser).where(
                AccountUser.account_id == owner.account.id, AccountUser.user_id == member.id
            )
        )
    ).one()
    row.availability = USER_AVAILABILITY_OFFLINE
    db_session.add(row)
    # The owner is an inbox member too when the builder adds them.
    owner_rows = (
        await db_session.exec(select(AccountUser).where(AccountUser.account_id == owner.account.id))
    ).all()
    for r in owner_rows:
        r.availability = USER_AVAILABILITY_OFFLINE
        db_session.add(r)
    await db_session.flush()

    second = await _conversation(db_session, owner, inbox)
    assert second.status == CONVERSATION_STATUS_PENDING


async def test_out_of_hours_follows_the_inbox_schedule(db_session, queued):
    owner, _ = await _seed_user(db_session, "hours")
    inbox = await _inbox(db_session, owner, auto_assign=False)
    await _ai_bot(db_session, owner, inbox, respond_when="out_of_hours")
    inbox.working_hours_enabled = True
    db_session.add(inbox)
    rows = (await db_session.exec(select(WorkingHour).where(WorkingHour.inbox_id == inbox.id))).all()
    assert rows, "the inbox builder seeds a schedule"
    for r in rows:
        r.open_all_day, r.closed_all_day = True, False
        db_session.add(r)
    await db_session.flush()

    assert (await _conversation(db_session, owner, inbox)).status == CONVERSATION_STATUS_OPEN

    for r in rows:
        r.open_all_day, r.closed_all_day = False, True
        db_session.add(r)
    await db_session.flush()
    assert (await _conversation(db_session, owner, inbox)).status == CONVERSATION_STATUS_PENDING


def test_open_at_reads_the_day_in_the_inbox_zone():
    monday_nine = WorkingHour(
        day_of_week=1, open_hour=9, open_minutes=0, close_hour=17, close_minutes=0
    )
    rows = [monday_nine]
    # Monday 2026-11-16 12:30 UTC = 09:30 in Montevideo (UTC-3).
    assert open_at(rows=rows, timezone_name="America/Montevideo", moment=datetime(2026, 11, 16, 12, 30, tzinfo=UTC))
    assert not open_at(rows=rows, timezone_name="America/Montevideo", moment=datetime(2026, 11, 16, 11, 30, tzinfo=UTC))
    # Tuesday has no row: closed.
    assert not open_at(rows=rows, timezone_name="UTC", moment=datetime(2026, 11, 17, 10, 0, tzinfo=UTC))
    assert open_at(rows=[], timezone_name="UTC", moment=datetime(2026, 11, 17, 10, 0, tzinfo=UTC))


async def test_a_person_replying_makes_the_ai_step_aside(db_session, queued):
    owner, _ = await _seed_user(db_session, "release")
    inbox = await _inbox(db_session, owner, auto_assign=False)
    await _ai_bot(db_session, owner, inbox)
    conv = await _conversation(db_session, owner, inbox)
    await _incoming(db_session, conv, "Hola")

    await _reply(db_session, conv, owner.user, "Hola Ana, te atiendo yo.")

    await db_session.refresh(conv)
    assert conv.status == CONVERSATION_STATUS_OPEN
    assert conv.assignee_agent_bot_id is None
    activities = [m.content for m in await _messages(db_session, conv) if m.message_type == MESSAGE_TYPE_ACTIVITY]
    assert any("la IA deja de contestar" in (a or "") for a in activities)
    queued.clear()
    await _incoming(db_session, conv, "Gracias")
    assert queued == []


async def test_a_resolved_conversation_goes_back_to_the_ai(db_session, queued):
    owner, _ = await _seed_user(db_session, "reopen")
    inbox = await _inbox(db_session, owner, auto_assign=False)
    bot = await _ai_bot(db_session, owner, inbox)
    conv = await _conversation(db_session, owner, inbox)
    conv.status = CONVERSATION_STATUS_RESOLVED
    conv.assignee_agent_bot_id = None
    db_session.add(conv)
    await db_session.flush()

    await _incoming(db_session, conv, "Otra consulta")

    await db_session.refresh(conv)
    assert conv.status == CONVERSATION_STATUS_PENDING
    assert conv.assignee_agent_bot_id == bot.id


# ---------------------------------------------------------------------------
# The run, live
# ---------------------------------------------------------------------------
async def test_live_answer_uses_the_tools_and_goes_out_as_the_bot(db_session, queued, model):
    owner, _ = await _seed_user(db_session, "answer")
    other, _ = await _seed_user(db_session, "answer-other")
    inbox = await _inbox(db_session, owner, auto_assign=False)
    bot = await _ai_bot(db_session, owner, inbox)
    db_session.add(Product(account_id=owner.account.id, name="Curso de Excel", price=1500, currency="UYU"))
    db_session.add(Product(account_id=other.account.id, name="Curso secreto", price=1, currency="UYU"))
    await db_session.flush()
    conv = await _conversation(db_session, owner, inbox)
    message = await _incoming(db_session, conv, "¿Cuánto sale el curso?")

    model.replies = [
        _call("list_products", {"query": "curso"}),
        {"content": "El Curso de Excel sale 1500 pesos."},
    ]
    reply = await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)

    assert reply is not None and reply.status == STATUS_ANSWERED
    assert reply.steps == [{"name": "list_products", "arguments": {"query": "curso"}}]
    # The tool only sees this account.
    tool_result = model.calls[1][-1]["content"]
    assert "Curso de Excel" in tool_result and "secreto" not in tool_result
    # The business instructions and the customer's words reach the model.
    assert "Vendemos cursos." in model.calls[0][0]["content"]
    assert model.calls[0][-1] == {"role": "user", "content": "¿Cuánto sale el curso?"}

    sent = (await _messages(db_session, conv))[-1]
    assert sent.content == "El Curso de Excel sale 1500 pesos."
    assert sent.sender_type == SENDER_TYPE_AGENT_BOT and sent.sender_id == bot.id
    assert reply.sent_message_id == sent.id
    await db_session.refresh(conv)
    # Its own message doesn't release it.
    assert conv.status == CONVERSATION_STATUS_PENDING


async def test_live_handoff_leaves_a_summary_and_goes_to_the_responsible(db_session, queued, model):
    owner, _ = await _seed_user(db_session, "handoff")
    inbox = await _inbox(db_session, owner, auto_assign=False)
    member, _ = await _member(db_session, owner, inbox, "handoff-m")
    db_session.add(HandoffRule(account_id=owner.account.id, scope=SCOPE_ACCOUNT, user_id=member.id))
    await _ai_bot(db_session, owner, inbox)
    conv = await _conversation(db_session, owner, inbox)
    message = await _incoming(db_session, conv, "Quiero hablar con alguien")

    model.replies = [
        _call(
            "hand_off_to_person",
            {"summary": "Ana pide hablar con una persona.", "reply": "Te paso con alguien del equipo."},
        )
    ]
    reply = await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)

    assert reply is not None and reply.status == STATUS_HANDOFF
    rows = await _messages(db_session, conv)
    assert any(m.content == "Te paso con alguien del equipo." and not m.private for m in rows)
    assert any(m.private and "Ana pide hablar con una persona." in (m.content or "") for m in rows)
    await db_session.refresh(conv)
    assert conv.status == CONVERSATION_STATUS_OPEN
    assert conv.assignee_agent_bot_id is None
    assert conv.assignee_id == member.id


async def test_a_model_failure_hands_off_live(db_session, queued, model):
    owner, _ = await _seed_user(db_session, "fail")
    inbox = await _inbox(db_session, owner, auto_assign=False)
    await _ai_bot(db_session, owner, inbox)
    conv = await _conversation(db_session, owner, inbox)
    message = await _incoming(db_session, conv, "Hola")

    model.replies = [llm.LlmError("down")]
    reply = await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)

    assert reply is not None and reply.status == STATUS_FAILED
    await db_session.refresh(conv)
    assert conv.status == CONVERSATION_STATUS_OPEN
    assert conv.assignee_agent_bot_id is None
    assert any(m.private and "no pudo responder" in (m.content or "") for m in await _messages(db_session, conv))


async def test_only_the_last_message_of_a_burst_is_answered(db_session, queued, model):
    owner, _ = await _seed_user(db_session, "burst")
    inbox = await _inbox(db_session, owner, auto_assign=False)
    await _ai_bot(db_session, owner, inbox)
    conv = await _conversation(db_session, owner, inbox)
    first = await _incoming(db_session, conv, "Hola")
    await _incoming(db_session, conv, "¿Están?")

    assert await ai.answer(db_session, conversation_id=conv.id, message_id=first.id) is None
    assert model.calls == []


# ---------------------------------------------------------------------------
# Shadow
# ---------------------------------------------------------------------------
async def _shadow_suggestion(db_session, owner, model, suffix: str):
    inbox = await _inbox(db_session, owner, auto_assign=False)
    await _ai_bot(db_session, owner, inbox, mode="shadow")
    conv = await _conversation(db_session, owner, inbox)
    message = await _incoming(db_session, conv, "¿Abren el sábado?")
    model.replies = [{"content": "Sí, de 9 a 13."}]
    reply = await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)
    return conv, reply


async def test_an_external_ai_claim_keeps_it_quiet(db_session, queued):
    owner, _ = await _seed_user(db_session, "ai-mode")
    inbox = await _inbox(db_session, owner, auto_assign=False)
    await _ai_bot(db_session, owner, inbox, mode="shadow")
    conv = await _conversation(db_session, owner, inbox)
    conv.ai_mode = True
    db_session.add(conv)
    await db_session.flush()

    await _incoming(db_session, conv, "Hola")
    assert queued == []


async def test_shadow_proposes_and_sending_it_as_is_counts(client, db_session, queued, model):
    owner, headers = await _seed_user(db_session, "sh-sent")
    conv, reply = await _shadow_suggestion(db_session, owner, model, "sent")

    assert reply.status == STATUS_SUGGESTED
    # Nothing went to the customer.
    assert (await _messages(db_session, conv))[-1].content == "¿Abren el sábado?"
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/ai_reply",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["ai_reply"]["content"] == "Sí, de 9 a 13."

    await _reply(db_session, conv, owner.user, "Sí,  de 9 a 13.", ai_reply_id=reply.id)
    await db_session.refresh(reply)
    assert reply.status == STATUS_SENT


async def test_shadow_edited_discarded_and_superseded(client, db_session, queued, model):
    owner, headers = await _seed_user(db_session, "sh-other")
    conv, reply = await _shadow_suggestion(db_session, owner, model, "edited")
    await _reply(db_session, conv, owner.user, "Sí, de 9 a 12.", ai_reply_id=reply.id)
    await db_session.refresh(reply)
    assert reply.status == STATUS_EDITED

    conv2, reply2 = await _shadow_suggestion(db_session, owner, model, "discard")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv2.display_id}/ai_reply/{reply2.id}/discard",
        headers=headers,
    )
    assert resp.status_code == 200
    await db_session.refresh(reply2)
    assert reply2.status == STATUS_DISCARDED

    conv3, reply3 = await _shadow_suggestion(db_session, owner, model, "other")
    await _reply(db_session, conv3, owner.user, "Te confirmo en un rato.")
    await db_session.refresh(reply3)
    assert reply3.status == STATUS_SUPERSEDED


async def test_an_agent_outside_the_inbox_cannot_read_the_suggestion(client, db_session, queued, model):
    owner, _ = await _seed_user(db_session, "sh-perm")
    conv, _reply_row = await _shadow_suggestion(db_session, owner, model, "perm")
    outsider, headers = await _seed_user(db_session, "sh-perm-out")
    db_session.add(
        AccountUser(account_id=owner.account.id, user_id=outsider.user.id, role=ACCOUNT_USER_ROLE_AGENT)
    )
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/ai_reply",
        headers=headers,
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# The AI as a handoff target
# ---------------------------------------------------------------------------
async def test_a_rule_can_hand_meta_handoffs_to_the_ai_but_not_the_ais_own(db_session, queued):
    owner, _ = await _seed_user(db_session, "to-ai")
    inbox = await _inbox(db_session, owner, auto_assign=False)
    bot = await _ai_bot(db_session, owner, inbox, respond_when="nobody_available")
    await _member(db_session, owner, inbox, "to-ai-m")
    db_session.add(HandoffRule(account_id=owner.account.id, scope=SCOPE_ACCOUNT, to_ai=True))
    await db_session.flush()
    # Someone is online, so the AI didn't take it on its own.
    conv = await _conversation(db_session, owner, inbox)
    assert conv.status == CONVERSATION_STATUS_OPEN
    message = await _incoming(db_session, conv, "Hola")

    await bot_handoff(db_session, conversation=conv, allow_ai=True)

    await db_session.refresh(conv)
    assert conv.status == CONVERSATION_STATUS_PENDING
    assert conv.assignee_agent_bot_id == bot.id
    assert queued[-1] == (conv.id, message.id)

    # The AI handing off skips the rule that names it.
    conv2 = await _conversation(db_session, owner, inbox)
    await bot_handoff(db_session, conversation=conv2)
    await db_session.refresh(conv2)
    assert conv2.status == CONVERSATION_STATUS_OPEN
    assert conv2.assignee_agent_bot_id is None


# ---------------------------------------------------------------------------
# Bots of type AI
# ---------------------------------------------------------------------------
async def test_ai_bots_from_the_api(client, db_session):
    owner, headers = await _seed_user(db_session, "api")
    base = f"/api/v1/accounts/{owner.account.id}/agent_bots"

    resp = await client.post(
        base,
        headers=headers,
        json={
            "name": "Sofi",
            "bot_type": "ai",
            "outgoing_url": "https://ignored.example.com",
            "bot_config": {"instructions": " Somos CTC. ", "mode": "live"},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["bot_type"] == "ai"
    assert body["outgoing_url"] is None
    assert body["bot_config"] == {
        "instructions": "Somos CTC.",
        "mode": "live",
        "respond_when": "always",
        "can_book": False,
        "slot_minutes": 60,
        "can_update_crm": False,
    }
    bad_slot = await client.patch(
        f"{base}/{body['id']}", headers=headers, json={"bot_config": {"slot_minutes": 7}}
    )
    assert bad_slot.json()["code"] == "agent_bots.slot_minutes"

    bad = await client.patch(
        f"{base}/{body['id']}", headers=headers, json={"bot_config": {"mode": "loud"}}
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "agent_bots.mode"

    webhook = await client.post(base, headers=headers, json={"name": "Hook", "outgoing_url": "https://h.example.com"})
    assert webhook.json()["bot_type"] == "webhook"
    wrong = await client.post(base, headers=headers, json={"name": "X", "bot_type": "robot"})
    assert wrong.status_code == 422


async def test_suggestions_are_listed_newest_first(db_session, queued, model):
    owner, _ = await _seed_user(db_session, "rows")
    conv, first = await _shadow_suggestion(db_session, owner, model, "rows")
    message = await _incoming(db_session, conv, "¿Y el domingo?")
    model.replies = [{"content": "El domingo cerramos."}]
    second = await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)

    await db_session.refresh(first)
    assert first.status == STATUS_SUPERSEDED
    assert (await ai.waiting_suggestion(db_session, conv.id)).id == second.id
    rows = (await db_session.exec(select(AiReply).where(AiReply.conversation_id == conv.id))).all()
    assert len(rows) == 2


async def test_the_inbox_says_which_bot_it_has(client, db_session):
    owner, headers = await _seed_user(db_session, "inbox-bot")
    inbox = await _inbox(db_session, owner, auto_assign=False)
    url = f"/api/v1/accounts/{owner.account.id}/inboxes/{inbox.id}/agent_bot"

    assert (await client.get(url, headers=headers)).json() == {"agent_bot": None}
    bot = await _ai_bot(db_session, owner, inbox, mode="shadow")
    body = (await client.get(url, headers=headers)).json()
    assert body["agent_bot"]["id"] == bot.id
    assert body["agent_bot"]["bot_type"] == "ai"


# ---------------------------------------------------------------------------
# Nobody is left waiting on the AI
# ---------------------------------------------------------------------------
async def _held(db_session, suffix: str, **config):
    owner, headers = await _seed_user(db_session, suffix)
    inbox = await _inbox(db_session, owner, auto_assign=False)
    bot = await _ai_bot(db_session, owner, inbox, **config)
    conv = await _conversation(db_session, owner, inbox)
    assert conv.status == CONVERSATION_STATUS_PENDING
    return owner, headers, inbox, bot, conv


async def test_meta_taking_the_thread_back_releases_the_ai(db_session, queued):
    from app.domains.whatsapp.business_agent import note_standby_means_ai_owner

    _owner, _h, _inbox, _bot, conv = await _held(db_session, "meta-back")
    conv.additional_attributes = {"thread_control": {"owner": "app"}}
    db_session.add(conv)
    await db_session.flush()

    await note_standby_means_ai_owner(db_session, conversation=conv)

    assert conv.assignee_agent_bot_id is None
    assert conv.status == CONVERSATION_STATUS_OPEN
    queued.clear()
    await _incoming(db_session, conv, "Hola")
    assert queued == []


async def test_assigning_a_person_opens_what_the_ai_held(db_session, queued):
    owner, _h, inbox, _bot, conv = await _held(db_session, "assign")
    member, _ = await _member(db_session, owner, inbox, "assign-m")

    await update_assignee(db_session, conversation=conv, assignee_id=member.id)

    assert conv.status == CONVERSATION_STATUS_OPEN
    assert conv.assignee_agent_bot_id is None


async def test_the_replier_keeps_the_conversation_with_auto_assignment_on(db_session, queued):
    owner, _ = await _seed_user(db_session, "replier")
    inbox = await _inbox(db_session, owner, auto_assign=True)
    member, _ = await _member(db_session, owner, inbox, "replier-m")
    await _member(db_session, owner, inbox, "replier-o")
    await _ai_bot(db_session, owner, inbox)
    conv = await _conversation(db_session, owner, inbox)

    await _reply(db_session, conv, member, "Te atiendo yo.")

    await db_session.refresh(conv)
    assert conv.status == CONVERSATION_STATUS_OPEN
    assert conv.assignee_id == member.id


async def test_detaching_or_shadowing_the_bot_releases_its_conversations(db_session, queued):
    _owner, _h, inbox, _bot, conv = await _held(db_session, "detach")
    await detach_bot_from_inbox(db_session, inbox=inbox)
    await db_session.refresh(conv)
    assert conv.status == CONVERSATION_STATUS_OPEN and conv.assignee_agent_bot_id is None

    _o, _h2, _inbox2, bot2, conv2 = await _held(db_session, "to-shadow")
    await update_bot(db_session, bot=bot2, payload={"bot_config": {"mode": "shadow"}})
    await db_session.refresh(conv2)
    assert conv2.status == CONVERSATION_STATUS_OPEN and conv2.assignee_agent_bot_id is None


async def test_an_external_ai_claim_isnt_reopened_for_the_ai(db_session, queued):
    _owner, _h, _inbox, _bot, conv = await _held(db_session, "claimed")
    conv.status = CONVERSATION_STATUS_RESOLVED
    conv.assignee_agent_bot_id = None
    conv.ai_mode = True
    db_session.add(conv)
    await db_session.flush()

    await _incoming(db_session, conv, "Hola de nuevo")

    await db_session.refresh(conv)
    assert conv.status == CONVERSATION_STATUS_OPEN
    assert conv.assignee_agent_bot_id is None


async def test_a_conversation_a_person_starts_isnt_taken(db_session, queued):
    from app.core.current import current_user_ctx

    owner, _ = await _seed_user(db_session, "outbound")
    inbox = await _inbox(db_session, owner, auto_assign=False)
    await _ai_bot(db_session, owner, inbox)
    token = current_user_ctx.set(owner.user)
    try:
        conv = await _conversation(db_session, owner, inbox)
    finally:
        current_user_ctx.reset(token)
    assert conv.status == CONVERSATION_STATUS_OPEN


async def test_no_openai_key_takes_nothing(db_session, queued, monkeypatch):
    monkeypatch.setattr(get_settings(), "openai_api_key", "")
    owner, _ = await _seed_user(db_session, "nokey")
    inbox = await _inbox(db_session, owner, auto_assign=False)
    await _ai_bot(db_session, owner, inbox)
    assert (await _conversation(db_session, owner, inbox)).status == CONVERSATION_STATUS_OPEN


async def test_a_failed_run_hands_the_conversation_to_the_team(db_session, queued):
    _o, _h, _inbox, _bot, conv = await _held(db_session, "rescue")
    await _incoming(db_session, conv, "Hola")

    await ai.rescue(db_session, conv.id)

    await db_session.refresh(conv)
    assert conv.status == CONVERSATION_STATUS_OPEN
    assert conv.assignee_agent_bot_id is None
    assert any(m.private and "no pudo responder" in (m.content or "") for m in await _messages(db_session, conv))


async def test_a_person_replying_while_the_model_thinks_wins(db_session, queued, model):
    owner, _h, _inbox, _bot, conv = await _held(db_session, "race")
    message = await _incoming(db_session, conv, "Hola")

    async def person_replies() -> dict[str, Any]:
        await _reply(db_session, conv, owner.user, "Hola, te atiendo yo.")
        return {"content": "Hola, soy la IA."}

    model.replies = [person_replies]
    conv_id = conv.id
    reply = await ai.answer(db_session, conversation_id=conv_id, message_id=message.id)

    assert reply is not None and reply.status == STATUS_SUPERSEDED
    assert "Hola, soy la IA." not in await _contents(db_session, conv_id)


async def test_a_newer_message_while_the_model_thinks_drops_the_answer(db_session, queued, model):
    _o, _h, _inbox, _bot, conv = await _held(db_session, "race-msg")
    message = await _incoming(db_session, conv, "Hola")

    async def customer_writes() -> dict[str, Any]:
        await _incoming(db_session, conv, "¿Están?")
        return {"content": "Hola!"}

    model.replies = [customer_writes]
    conv_id = conv.id
    reply = await ai.answer(db_session, conversation_id=conv_id, message_id=message.id)

    assert reply is not None and reply.status == STATUS_SUPERSEDED
    assert "Hola!" not in await _contents(db_session, conv_id)


async def test_a_tool_error_goes_back_to_the_model(db_session, queued, model, monkeypatch):
    _o, _h, _inbox, _bot, conv = await _held(db_session, "tool-err")
    message = await _incoming(db_session, conv, "¿Qué cursos hay?")

    async def broken(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setitem(ai_tools._HANDLERS, "list_products", broken)
    model.replies = [_call("list_products", {}), {"content": "Te consulto y te aviso."}]
    reply = await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)

    assert reply is not None and reply.status == STATUS_ANSWERED
    assert "No se pudo hacer" in model.calls[1][-1]["content"]


async def test_discarding_another_conversations_suggestion_is_refused(client, db_session, queued, model):
    owner, headers = await _seed_user(db_session, "sh-cross")
    conv, _reply_row = await _shadow_suggestion(db_session, owner, model, "a")
    _conv_b, reply_b = await _shadow_suggestion(db_session, owner, model, "b")

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/ai_reply/{reply_b.id}/discard",
        headers=headers,
    )
    assert resp.status_code == 409
    await db_session.refresh(reply_b)
    assert reply_b.status == STATUS_SUGGESTED


# ---------------------------------------------------------------------------
# Agenda and CRM (2b.2)
# ---------------------------------------------------------------------------
def _open_every_day(rows) -> None:
    for r in rows:
        r.open_all_day, r.closed_all_day = False, False
        r.open_hour, r.open_minutes, r.close_hour, r.close_minutes = 9, 0, 12, 0


async def _agenda_inbox(db_session, suffix: str, **config):
    owner, _headers = await _seed_user(db_session, suffix)
    inbox = await _inbox(db_session, owner, auto_assign=False)
    inbox.timezone = "America/Montevideo"
    inbox.working_hours_enabled = True
    db_session.add(inbox)
    rows = (await db_session.exec(select(WorkingHour).where(WorkingHour.inbox_id == inbox.id))).all()
    _open_every_day(rows)
    for r in rows:
        db_session.add(r)
    bot = await _ai_bot(db_session, owner, inbox, can_book=True, slot_minutes=60, **config)
    conv = await _conversation(db_session, owner, inbox)
    return owner, inbox, bot, conv


async def test_writing_tools_are_offered_only_when_allowed(db_session, queued, model):
    _o, _h, _inbox, _bot, conv = await _held(db_session, "offer")
    message = await _incoming(db_session, conv, "Hola")
    model.replies = [_call("book_appointment", {"starts_at": "2030-01-01T10:00:00-03:00"}), {"content": "Listo"}]
    await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)
    assert "no existe" in model.calls[1][-1]["content"]


async def test_free_times_skip_busy_and_closed_hours(db_session, queued, model):
    from app.domains.appointments.models import Appointment

    owner, _inbox, _bot, conv = await _agenda_inbox(db_session, "free")
    other_contact = Contact(account_id=owner.account.id, name="Otro")
    db_session.add(other_contact)
    await db_session.flush()
    # Tomorrow 10:00 Montevideo is taken.
    tomorrow = (datetime.now(UTC).astimezone(ZoneInfo("America/Montevideo")) + timedelta(days=1)).date()
    taken = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 10, 0, tzinfo=ZoneInfo("America/Montevideo"))
    db_session.add(
        Appointment(account_id=owner.account.id, contact_id=other_contact.id, title="X", starts_at=taken, status="scheduled")
    )
    await db_session.flush()
    message = await _incoming(db_session, conv, "¿Tenés turno mañana?")

    model.replies = [_call("list_free_times", {"from_date": tomorrow.isoformat()}), {"content": "Tengo 9 y 11."}]
    await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)

    result = json.loads(model.calls[1][-1]["content"])
    times = result["free_times"]
    assert result["minutes"] == 60
    assert times[:2] == [
        datetime(tomorrow.year, tomorrow.month, tomorrow.day, 9, 0, tzinfo=ZoneInfo("America/Montevideo")).isoformat(),
        datetime(tomorrow.year, tomorrow.month, tomorrow.day, 11, 0, tzinfo=ZoneInfo("America/Montevideo")).isoformat(),
    ]


async def test_live_booking_creates_the_appointment_and_says_so(db_session, queued, model):
    from app.domains.appointments.models import Appointment

    owner, _inbox, _bot, conv = await _agenda_inbox(db_session, "book")
    db_session.add(Product(account_id=owner.account.id, name="Entrevista", price=0, currency="UYU"))
    await db_session.flush()
    message = await _incoming(db_session, conv, "Dale, el de las 9")
    tomorrow = (datetime.now(UTC).astimezone(ZoneInfo("America/Montevideo")) + timedelta(days=1)).date()
    nine = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 9, 0, tzinfo=ZoneInfo("America/Montevideo"))

    model.replies = [
        _call("book_appointment", {"starts_at": nine.isoformat(), "product": "entrevista"}),
        {"content": "Te agendé mañana a las 9."},
    ]
    reply = await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)

    assert reply is not None and reply.status == STATUS_ANSWERED
    booked = (await db_session.exec(select(Appointment).where(Appointment.contact_id == conv.contact_id))).one()
    assert booked.title == "Entrevista"
    assert booked.starts_at == nine
    assert booked.ends_at == nine + timedelta(hours=1)
    activities = [m.content for m in await _messages(db_session, conv) if m.message_type == MESSAGE_TYPE_ACTIVITY]
    assert any((a or "").startswith("La IA hizo: Cita «Entrevista»") for a in activities)

    # One upcoming appointment per customer.
    message2 = await _incoming(db_session, conv, "¿Y otra el jueves?")
    model.replies = [_call("book_appointment", {"starts_at": (nine + timedelta(hours=2)).isoformat()}), {"content": "Te paso."}]
    await ai.answer(db_session, conversation_id=conv.id, message_id=message2.id)
    assert "Ya tiene una cita" in model.calls[-1][-1]["content"]

    # Another customer: that time is no longer free.
    conv_b = await _conversation(db_session, owner, _inbox)
    message3 = await _incoming(db_session, conv_b, "Quiero el de las 9")
    model.replies = [_call("book_appointment", {"starts_at": nine.isoformat()}), {"content": "Ese no."}]
    await ai.answer(db_session, conversation_id=conv_b.id, message_id=message3.id)
    assert "no está libre" in model.calls[-1][-1]["content"]


async def test_shadow_proposes_the_booking_without_doing_it(db_session, queued, model):
    from app.domains.appointments.models import Appointment

    _owner, _inbox, _bot, conv = await _agenda_inbox(db_session, "book-shadow", mode="shadow")
    message = await _incoming(db_session, conv, "El de las 9")
    tomorrow = (datetime.now(UTC).astimezone(ZoneInfo("America/Montevideo")) + timedelta(days=1)).date()
    nine = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 9, 0, tzinfo=ZoneInfo("America/Montevideo"))

    model.replies = [_call("book_appointment", {"starts_at": nine.isoformat()}), {"content": "Te agendé a las 9."}]
    reply = await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)

    assert reply is not None and reply.status == STATUS_SUGGESTED
    assert (await db_session.exec(select(Appointment).where(Appointment.contact_id == conv.contact_id))).first() is None
    shown = ai.present_suggestion(reply)
    assert shown["actions"] == [f"Cita «Cita» el {nine:%Y-%m-%d %H:%M}"]


async def test_crm_tools_fill_only_what_is_missing(db_session, queued, model):
    from app.domains.crm.models import CrmOpportunity
    from app.domains.labels.models import Label

    owner, _h, _inbox, _bot, conv = await _held(db_session, "crm", can_update_crm=True)
    contact = await db_session.get(Contact, conv.contact_id)
    contact.email = None
    db_session.add(contact)
    db_session.add(Label(account_id=owner.account.id, title="interesado"))
    await db_session.flush()
    message = await _incoming(db_session, conv, "Soy Ana Pérez, ana@example.com, quiero el curso de Excel")

    model.replies = [
        _call("save_contact_details", {"name": "Ana Pérez", "email": "ANA@example.com"}),
        _call("add_label", {"label": "Interesado"}),
        _call("add_label", {"label": "vip"}),
        _call("create_opportunity", {"title": "Curso de Excel", "value": 1500}),
        {"content": "¡Perfecto, Ana!"},
    ]
    reply = await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)

    assert reply is not None and reply.status == STATUS_ANSWERED
    await db_session.refresh(contact)
    # The name was set ("Ana" stays: it wasn't missing); the email was.
    assert contact.name == "Ana"
    assert contact.email == "ana@example.com"
    await db_session.refresh(conv)
    assert "interesado" in (conv.cached_label_list or "")
    assert "No existe esa etiqueta" in model.calls[3][-1]["content"]
    opportunity = (
        await db_session.exec(select(CrmOpportunity).where(CrmOpportunity.contact_id == conv.contact_id))
    ).one()
    assert opportunity.title == "Curso de Excel"
    assert opportunity.conversation_id == conv.id
    assert [s.get("action") for s in reply.steps if s.get("action")] == [
        "Datos del contacto: email: ana@example.com",
        "Etiqueta: interesado",
        "Oportunidad «Curso de Excel»",
    ]


async def test_a_taken_email_is_refused(db_session, queued, model):
    owner, _h, _inbox, _bot, conv = await _held(db_session, "crm-email", can_update_crm=True)
    db_session.add(Contact(account_id=owner.account.id, name="Otra", email="dup@example.com"))
    await db_session.flush()
    message = await _incoming(db_session, conv, "mi mail es dup@example.com")

    model.replies = [_call("save_contact_details", {"email": "dup@example.com"}), {"content": "Te paso con alguien."}]
    await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)

    assert "ya es de otro contacto" in model.calls[1][-1]["content"]
    contact = await db_session.get(Contact, conv.contact_id)
    assert contact.email != "dup@example.com"


async def test_a_dropped_run_undoes_its_writes_but_keeps_the_cost(db_session, queued, model):
    from app.domains.appointments.models import Appointment
    from app.domains.usage.models import UsageRecord

    owner, _inbox, _bot, conv = await _agenda_inbox(db_session, "undo")
    message = await _incoming(db_session, conv, "El de las 9")
    tomorrow = (datetime.now(UTC).astimezone(ZoneInfo("America/Montevideo")) + timedelta(days=1)).date()
    nine = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 9, 0, tzinfo=ZoneInfo("America/Montevideo"))
    contact_id = conv.contact_id
    account_id = owner.account.id

    async def spend_then_fail() -> dict[str, Any]:
        db_session.add(UsageRecord(account_id=account_id, kind="ai", occurred_at=datetime.now(UTC), category="ai_agent", model="m"))
        raise llm.LlmError("down")

    model.replies = [_call("book_appointment", {"starts_at": nine.isoformat()}), spend_then_fail]
    reply = await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)

    assert reply is not None and reply.status == STATUS_FAILED
    booked = (await db_session.exec(select(Appointment.id).where(Appointment.contact_id == contact_id))).first()
    assert booked is None
    spent = (await db_session.exec(select(UsageRecord.id).where(UsageRecord.account_id == account_id))).all()
    assert len(spent) == 1


async def test_booking_needs_the_inbox_hours_and_a_near_date(db_session, queued, model):
    _owner, inbox, _bot, conv = await _agenda_inbox(db_session, "hours-off")
    message = await _incoming(db_session, conv, "¿Hay turno?")
    far = datetime.now(UTC) + timedelta(days=40)
    model.replies = [_call("book_appointment", {"starts_at": far.isoformat()}), {"content": "No."}]
    await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)
    assert "días adelante" in model.calls[-1][-1]["content"]

    inbox.working_hours_enabled = False
    db_session.add(inbox)
    await db_session.flush()
    message2 = await _incoming(db_session, conv, "¿Y mañana?")
    model.replies = [_call("list_free_times", {}), {"content": "Te paso."}]
    await ai.answer(db_session, conversation_id=conv.id, message_id=message2.id)
    assert "no cargó su horario" in model.calls[-1][-1]["content"]


async def test_stage_moves_live_and_only_proposes_in_shadow(db_session, queued, model):
    from app.domains.lifecycle.models import ContactLifecycle, LifecycleSettings

    owner, _h, _ib, _bot, conv = await _held(db_session, "stage", can_update_crm=True)
    db_session.add(LifecycleSettings(account_id=owner.account.id, enabled=True))
    await db_session.flush()
    message = await _incoming(db_session, conv, "Quiero pagar")
    model.replies = [_call("set_contact_stage", {"stage": "nada"}), _call("set_contact_stage", {"stage": "payment"}), {"content": "Genial."}]
    reply = await ai.answer(db_session, conversation_id=conv.id, message_id=message.id)

    assert "No existe esa etapa" in model.calls[1][-1]["content"]
    row = await db_session.get(ContactLifecycle, conv.contact_id)
    assert row is not None and row.stage_key == "payment"
    assert next(s["action"] for s in reply.steps if s.get("action")).startswith("Etapa:")

    owner2, _h2 = await _seed_user(db_session, "stage-sh")
    inbox2 = await _inbox(db_session, owner2, auto_assign=False)
    await _ai_bot(db_session, owner2, inbox2, can_update_crm=True, mode="shadow")
    db_session.add(LifecycleSettings(account_id=owner2.account.id, enabled=True))
    await db_session.flush()
    conv2 = await _conversation(db_session, owner2, inbox2)
    message2 = await _incoming(db_session, conv2, "Quiero pagar")
    model.replies = [_call("set_contact_stage", {"stage": "payment"}), {"content": "Genial."}]
    shadow = await ai.answer(db_session, conversation_id=conv2.id, message_id=message2.id)
    assert shadow is not None and shadow.status == STATUS_SUGGESTED
    # Still where the first message put it.
    row2 = await db_session.get(ContactLifecycle, conv2.contact_id)
    assert row2 is None or row2.stage_key != "payment"
    assert ai.present_suggestion(shadow)["actions"][0].startswith("Etapa:")
