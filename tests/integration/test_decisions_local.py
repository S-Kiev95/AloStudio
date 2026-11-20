"""Decisions by the local model (Qwen) and the priority they set (F10).

* With ``provider: local`` the conversation is decided by llama-server (mocked
  with respx): in its own slot, with the business's context and today's date,
  anonymized, at no cost; refused at once on a one-slot server, and one at a
  time (the next one is ``busy`` and the worker retries it).
* With ``apply_priority`` the urgency becomes the priority, with a line and
  the model's (anonymized) reason, while the priority is the AI's: once a
  person, a rule or a tool changes or clears it, the AI leaves it.
* A priority a person sets on their own is their urgency label; changing the
  AI's is a correction, counted apart.
* The worker reads, lets the session go while the model answers, stores, and
  decides again if the customer wrote meanwhile.
* The help assistant keeps its own slot.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core import local_llm
from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.current import current_user_ctx
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    MESSAGE_TYPE_ACTIVITY,
    Message,
    conversation_priority_to_str,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
    toggle_priority,
)
from app.domains.decisions import local
from app.domains.decisions import service as decisions
from app.domains.decisions.client import DecisionsError
from app.domains.decisions.models import (
    OWNER_AI,
    OWNER_OTHER,
    ConversationDecision,
    HumanDecision,
    PriorityOwner,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.usage.models import UsageRecord
from app.main import app

pytestmark = pytest.mark.integration

LLM_URL = "http://llm.test:8092"
LLM = f"{LLM_URL}/v1/chat/completions"
PROPS = f"{LLM_URL}/props"


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
def qwen(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "local_llm_url", LLM_URL)
    monkeypatch.setattr(settings, "local_llm_model", "qwen3-4b")
    # No decisions service: the local model is enough.
    monkeypatch.setattr(settings, "decisions_api_url", "")
    monkeypatch.setattr(settings, "decisions_api_key", "")
    monkeypatch.setattr(local_llm, "_slots_seen", None)


@pytest.fixture
async def seeded(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@decide-local.example.com",
            account_name="Instituto",
            user_full_name="Sofía Costa",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, tokens = create_new_auth_token(user_tokens=owner.user.tokens, uid=owner.user.uid)
    owner.user.tokens = tokens
    db_session.add(owner.user)
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
    contact = Contact(account_id=owner.account.id, name="Lucía Pereira", phone_number="+59891234567")
    db_session.add(contact)
    await db_session.flush()
    contact_inbox = await ContactInboxBuilder(session=db_session, contact=contact, inbox=inbox).perform()
    await db_session.refresh(contact_inbox, ["inbox"])
    conversation = await create_conversation(
        db_session, contact_inbox=contact_inbox, params=ConversationBuilderParams()
    )
    await create_message(
        db_session,
        conversation=conversation,
        params=MessageBuilderParams(
            content="Hola, soy Lucía Pereira. ¿Todavía hay cupo para anotarme en 2027?",
            message_type="incoming",
        ),
        user_id=None,
    )
    return {
        "owner": owner,
        "conversation": conversation,
        "headers": headers.as_response_headers(),
        "base": f"/api/v1/accounts/{owner.account.id}/decisions",
    }


def _qwen_says(**answers: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": json.dumps(answers, ensure_ascii=False)}}],
            "timings": {"prompt_n": 300, "cache_n": 500, "predicted_n": 25},
        },
    )


def _answers(urgency: str, reason: str = "Quiere anotarse para 2027") -> dict[str, str]:
    return {"intent": "inscripcion", "sentiment": "neutral", "urgency": urgency, "Motivo": reason}


def _two_slots() -> None:
    respx.get(PROPS).mock(return_value=httpx.Response(200, json={"total_slots": 2}))


async def _turn_on(db_session, seeded, *, apply_priority: bool = False) -> None:
    await decisions.save_settings(
        db_session,
        account_id=seeded["owner"].account.id,
        enabled=True,
        questions=None,
        provider="local",
        context="En noviembre y diciembre las inscripciones para el año siguiente son urgentes.",
        apply_priority=apply_priority,
    )


async def _by_person(db_session, user, conversation, priority: str | None) -> None:
    """What the panel does: a signed-in person changes the priority."""
    token = current_user_ctx.set(user)
    try:
        await toggle_priority(db_session, conversation=conversation, priority=priority)
    finally:
        current_user_ctx.reset(token)


async def _priority(db_session, conversation) -> str | None:
    await db_session.refresh(conversation)
    return conversation_priority_to_str(conversation.priority)


async def _activities(db_session, conversation) -> list[str]:
    rows = (
        await db_session.exec(
            select(Message.content).where(
                Message.conversation_id == conversation.id,
                Message.message_type == MESSAGE_TYPE_ACTIVITY,
            )
        )
    ).all()
    return [r or "" for r in rows]


# ---------------------------------------------------------------------------
# The local model
# ---------------------------------------------------------------------------
@respx.mock
async def test_the_local_model_decides_in_its_slot_with_the_business_context(db_session, seeded, qwen):
    await _turn_on(db_session, seeded)
    _two_slots()
    route = respx.post(LLM).mock(return_value=_qwen_says(**_answers("urgente")))
    conversation = seeded["conversation"]

    stored = await decisions.decide(db_session, conversation)

    assert {d.question: d.answer for d in stored} == {
        "intent": "inscripcion",
        "sentiment": "neutral",
        "urgency": "urgente",
    }
    assert all(d.model == "qwen3-4b" and d.confidence is None for d in stored)
    sent = json.loads(route.calls[0].request.content)
    # Its own slot: the help assistant keeps slot 0.
    assert sent["id_slot"] == 1
    # No sampling: the same conversation gets the same pick.
    assert sent["temperature"] == 0
    system, user = sent["messages"][0]["content"], sent["messages"][1]["content"]
    assert "las inscripciones para el año siguiente son urgentes" in system
    # The urgency from the most to the least urgent.
    assert system.index("- urgente:") < system.index("- alta:") < system.index("- media:") < system.index("- baja:")
    assert user.startswith("Hoy es ")
    # Anonymized, like for the decisions service.
    assert "Lucía" not in user and "Cliente:" in user
    schema = sent["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["urgency"]["enum"] == ["baja", "media", "alta", "urgente"]
    # The reason first: the model says what the customer wants, then picks.
    assert next(iter(schema["properties"])) == "Motivo" and schema["required"][0] == "Motivo"
    usage = (
        await db_session.exec(
            select(UsageRecord).where(UsageRecord.account_id == seeded["owner"].account.id)
        )
    ).one()
    assert usage.cost == Decimal("0") and usage.input_tokens == 800 and usage.output_tokens == 25


@respx.mock
async def test_a_question_called_motivo_still_gets_its_answer(db_session, seeded, qwen):
    questions = await decisions.questions_for(db_session, seeded["owner"].account.id)
    questions.append(
        {
            "key": "motivo",
            "enabled": True,
            "instructions": "¿Por qué escribe?",
            "options": [
                {"key": "consulta", "description": "Consulta"},
                {"key": "queja", "description": "Queja"},
            ],
        }
    )
    await decisions.save_settings(
        db_session,
        account_id=seeded["owner"].account.id,
        enabled=True,
        questions=questions,
        provider="local",
    )
    _two_slots()
    route = respx.post(LLM).mock(return_value=_qwen_says(**_answers("baja"), motivo="consulta"))

    stored = await decisions.decide(db_session, seeded["conversation"])

    schema = json.loads(route.calls[0].request.content)["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["motivo"]["enum"] == ["consulta", "queja"]
    assert {d.question: d.answer for d in stored}["motivo"] == "consulta"


@respx.mock
async def test_a_reason_cut_by_the_grammar_ends_at_a_whole_word(db_session, seeded, qwen):
    await _turn_on(db_session, seeded, apply_priority=True)
    _two_slots()
    # Stopped at the limit in the middle of a word, with a stray character.
    cut = ("Quiere anotarse el año que viene y pregunta por cupos " * 3)[: local.REASON_MAX - 1] + "亟"
    respx.post(LLM).mock(return_value=_qwen_says(**_answers("urgente", cut)))
    conversation = seeded["conversation"]

    await decisions.decide(db_session, conversation)

    line = next(x for x in await _activities(db_session, conversation) if x.startswith("La IA"))
    reason = line.split(": ", 1)[1]
    assert reason.endswith("cupos Quiere…") and "亟" not in reason
    assert cut.startswith(reason[:-1])


@respx.mock
async def test_a_one_slot_server_is_refused_without_waiting(db_session, seeded, qwen):
    await _turn_on(db_session, seeded)
    respx.get(PROPS).mock(return_value=httpx.Response(200, json={"total_slots": 1}))
    chat = respx.post(LLM).mock(return_value=_qwen_says(**_answers("baja")))

    with pytest.raises(DecisionsError) as raised:
        await decisions.decide(db_session, seeded["conversation"])

    assert raised.value.code == "one_slot"
    assert chat.call_count == 0


@respx.mock
async def test_one_conversation_at_a_time(db_session, seeded, qwen):
    await _turn_on(db_session, seeded)
    _two_slots()
    respx.post(LLM).mock(return_value=_qwen_says(**_answers("baja")))

    async with local._deciding:
        with pytest.raises(DecisionsError) as raised:
            await decisions.decide(db_session, seeded["conversation"])
    assert raised.value.code == "busy"


@respx.mock
async def test_a_down_model_is_a_decisions_error(db_session, seeded, qwen):
    await _turn_on(db_session, seeded)
    _two_slots()
    respx.post(LLM).mock(side_effect=httpx.ConnectError("down"))

    with pytest.raises(DecisionsError) as raised:
        await decisions.decide(db_session, seeded["conversation"])
    assert raised.value.code == "unreachable"
    assert (await db_session.exec(select(ConversationDecision))).first() is None


# ---------------------------------------------------------------------------
# The priority
# ---------------------------------------------------------------------------
@respx.mock
async def test_without_apply_priority_nothing_changes(db_session, seeded, qwen):
    await _turn_on(db_session, seeded)
    _two_slots()
    respx.post(LLM).mock(return_value=_qwen_says(**_answers("urgente")))
    conversation = seeded["conversation"]

    await decisions.decide(db_session, conversation)

    assert await _priority(db_session, conversation) is None


@respx.mock
async def test_the_urgency_sets_the_priority_and_follows_itself(db_session, seeded, qwen):
    await _turn_on(db_session, seeded, apply_priority=True)
    _two_slots()
    route = respx.post(LLM).mock(
        return_value=_qwen_says(**_answers("urgente", "Lucía Pereira quiere anotarse para 2027"))
    )
    conversation = seeded["conversation"]

    await decisions.decide(db_session, conversation)

    assert await _priority(db_session, conversation) == "urgent"
    owner = await db_session.get(PriorityOwner, conversation.id)
    assert (owner.owner, owner.ai_level) == (OWNER_AI, "urgent")
    lines = await _activities(db_session, conversation)
    # The reason goes through the anonymizer too.
    assert any(
        line.startswith("La IA (qwen3-4b) puso la prioridad Urgente:") and "Lucía" not in line
        for line in lines
    )
    # Nothing of it in the conversation's attributes (they reach webhooks).
    assert "ai_priority" not in (conversation.additional_attributes or {})

    # Its own earlier pick it may change.
    route.mock(return_value=_qwen_says(**_answers("alta", "Pregunta por fechas")))
    await decisions.decide(db_session, conversation)
    assert await _priority(db_session, conversation) == "high"


@respx.mock
async def test_once_someone_changes_it_the_ai_leaves_it(db_session, seeded, qwen):
    await _turn_on(db_session, seeded, apply_priority=True)
    _two_slots()
    route = respx.post(LLM).mock(return_value=_qwen_says(**_answers("urgente")))
    conversation = seeded["conversation"]
    user = seeded["owner"].user
    await decisions.decide(db_session, conversation)

    # The director lowers it, then puts back the AI's value: it is theirs now.
    await _by_person(db_session, user, conversation, "medium")
    await _by_person(db_session, user, conversation, "urgent")
    route.mock(return_value=_qwen_says(**_answers("baja")))
    await decisions.decide(db_session, conversation)
    assert await _priority(db_session, conversation) == "urgent"

    owner = await db_session.get(PriorityOwner, conversation.id)
    assert (owner.owner, owner.corrected, owner.corrected_level) == (OWNER_OTHER, True, "medium")
    # Changing the AI's pick is a correction, not a blind label.
    assert (await db_session.exec(select(HumanDecision))).first() is None


@respx.mock
async def test_cleared_before_the_first_decision_stays_cleared(db_session, seeded, qwen):
    await _turn_on(db_session, seeded, apply_priority=True)
    _two_slots()
    respx.post(LLM).mock(return_value=_qwen_says(**_answers("urgente")))
    conversation = seeded["conversation"]
    user = seeded["owner"].user

    await _by_person(db_session, user, conversation, "high")
    await _by_person(db_session, user, conversation, None)
    await decisions.decide(db_session, conversation)

    assert await _priority(db_session, conversation) is None


@respx.mock
async def test_a_rule_or_a_priority_from_before_is_never_touched(db_session, seeded, qwen):
    conversation = seeded["conversation"]
    # Set before the feature was on (no owner row).
    await toggle_priority(db_session, conversation=conversation, priority="urgent")
    await _turn_on(db_session, seeded, apply_priority=True)
    _two_slots()
    respx.post(LLM).mock(return_value=_qwen_says(**_answers("baja")))

    await decisions.decide(db_session, conversation)

    assert await _priority(db_session, conversation) == "urgent"


@respx.mock
async def test_a_person_setting_it_on_their_own_is_the_label(db_session, seeded, qwen):
    await _turn_on(db_session, seeded, apply_priority=False)
    _two_slots()
    respx.post(LLM).mock(return_value=_qwen_says(**_answers("urgente")))
    conversation = seeded["conversation"]
    account_id = seeded["owner"].account.id
    await decisions.decide(db_session, conversation)

    await _by_person(db_session, seeded["owner"].user, conversation, "high")

    label = (await db_session.exec(select(HumanDecision))).one()
    assert (label.question, label.answer, label.user_id) == ("urgency", "alta", seeded["owner"].user.id)
    report = await decisions.report(db_session, account_id=account_id)
    urgency = next(q for q in report["questions"] if q["key"] == "urgency")
    assert (urgency["compared"], urgency["agreed"]) == (1, 0)
    item = await decisions.next_to_label(db_session, account_id=account_id)
    assert item is not None and item["answered"] == {"urgency": "alta"}


@respx.mock
async def test_a_rule_changing_it_is_no_label(db_session, seeded, qwen):
    await _turn_on(db_session, seeded)
    conversation = seeded["conversation"]

    # No signed-in person: an automation rule, a tool.
    await toggle_priority(db_session, conversation=conversation, priority="high")

    owner = await db_session.get(PriorityOwner, conversation.id)
    assert owner is not None and owner.owner == OWNER_OTHER
    assert (await db_session.exec(select(HumanDecision))).first() is None


@respx.mock
async def test_the_report_counts_how_often_its_priority_was_changed(db_session, seeded, qwen):
    await _turn_on(db_session, seeded, apply_priority=True)
    _two_slots()
    respx.post(LLM).mock(return_value=_qwen_says(**_answers("urgente")))
    conversation = seeded["conversation"]
    await decisions.decide(db_session, conversation)
    await _by_person(db_session, seeded["owner"].user, conversation, "low")

    report = await decisions.report(db_session, account_id=seeded["owner"].account.id)

    assert report["priority"] == {"set_by_ai": 1, "changed_by_others": 1}


# ---------------------------------------------------------------------------
# The worker
# ---------------------------------------------------------------------------
class _SameSession:
    """The task's session factory, giving the test's session."""

    def __init__(self, session) -> None:
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc: object) -> bool:
        return False


@respx.mock
async def test_the_worker_retries_while_another_is_being_decided(db_session, seeded, qwen, monkeypatch):
    from arq.worker import Retry

    from app.workers import decisions as task

    await _turn_on(db_session, seeded)
    _two_slots()
    monkeypatch.setattr(task, "_session_factory", lambda ctx: _SameSession(db_session))

    async with local._deciding:
        with pytest.raises(Retry):
            await task.decide_conversation_task({}, seeded["conversation"].id)


@respx.mock
async def test_the_worker_decides_again_when_the_customer_wrote_meanwhile(db_session, seeded, qwen, monkeypatch):
    from arq.worker import Retry

    from app.workers import decisions as task

    await _turn_on(db_session, seeded)
    _two_slots()
    conversation = seeded["conversation"]
    monkeypatch.setattr(task, "_session_factory", lambda ctx: _SameSession(db_session))

    def customer_writes_meanwhile(request: httpx.Request) -> httpx.Response:
        return _qwen_says(**_answers("baja"))

    respx.post(LLM).mock(side_effect=customer_writes_meanwhile)
    real_ask = decisions.ask

    async def ask_while_writing(prepared):
        result = await real_ask(prepared)
        await create_message(
            db_session,
            conversation=conversation,
            params=MessageBuilderParams(content="¡Vence hoy!", message_type="incoming"),
            user_id=None,
        )
        return result

    monkeypatch.setattr(decisions, "ask", ask_while_writing)

    with pytest.raises(Retry):
        await task.decide_conversation_task({}, conversation.id)
    # What it decided is kept; the retry decides again with the new message.
    assert (await db_session.exec(select(ConversationDecision))).first() is not None


@respx.mock
async def test_the_worker_decides(db_session, seeded, qwen, monkeypatch):
    from app.workers import decisions as task

    await _turn_on(db_session, seeded)
    _two_slots()
    respx.post(LLM).mock(return_value=_qwen_says(**_answers("media")))
    monkeypatch.setattr(task, "_session_factory", lambda ctx: _SameSession(db_session))

    result = await task.decide_conversation_task({}, seeded["conversation"].id)

    assert result == {"ok": True, "decided": 3}


# ---------------------------------------------------------------------------
# Settings and the help assistant
# ---------------------------------------------------------------------------
async def test_settings_choose_who_decides(client, db_session, seeded, qwen):
    base, headers = seeded["base"], seeded["headers"]

    shown = (await client.get(f"{base}/settings", headers=headers)).json()
    assert shown["provider"] == "api"
    assert shown["providers"] == {"api": False, "local": True}
    assert shown["models"]["local"] == "qwen3-4b"
    assert shown["configured"] is False and shown["apply_priority"] is False

    resp = await client.put(
        f"{base}/settings",
        headers=headers,
        json={
            "enabled": True,
            "provider": "local",
            "context": "  En enero cerramos.  ",
            "apply_priority": True,
        },
    )
    assert resp.status_code == 200, resp.text
    saved = resp.json()
    assert saved["provider"] == "local" and saved["configured"] is True
    assert saved["model"] == "qwen3-4b"
    assert saved["context"] == "En enero cerramos."
    assert saved["apply_priority"] is True
    assert await decisions.is_on(db_session, seeded["owner"].account.id)
    assert await decisions.decide_delay(db_session, seeded["owner"].account.id) == decisions.LOCAL_DECIDE_DELAY_SECONDS

    bad = await client.put(f"{base}/settings", headers=headers, json={"enabled": True, "provider": "gpt"})
    assert bad.status_code == 422 and bad.json()["code"] == "decisions.provider"
    long = await client.put(f"{base}/settings", headers=headers, json={"enabled": True, "context": "x" * 2001})
    assert long.status_code == 422 and long.json()["code"] == "decisions.context"


@respx.mock
async def test_the_help_assistant_keeps_its_own_slot(qwen):
    from app.domains.help_assistant import service as help_assistant

    seen: list[dict[str, Any]] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({"sabe": False})}}], "timings": {}},
        )

    respx.post(LLM).mock(side_effect=answer)
    await help_assistant.ask("¿Cómo agendo?")
    await help_assistant.warm()
    assert [s["id_slot"] for s in seen] == [0, 0]
