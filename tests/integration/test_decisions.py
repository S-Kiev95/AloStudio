"""Decisions in shadow mode (F10). The decisions service (Jev) is mocked."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from decimal import Decimal

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_conversation,
    create_message,
)
from app.domains.decisions import service as decisions
from app.domains.decisions.models import ConversationDecision, HumanDecision
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams.models import Team
from app.domains.usage.models import UsageRecord
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app

pytestmark = pytest.mark.integration

JEV = "https://api.typesafe.ai/v1/systemone"


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


@pytest.fixture
def jev_key(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "decisions_api_key", "ts-test")
    monkeypatch.setattr(settings, "decisions_api_url", "https://api.typesafe.ai")
    monkeypatch.setattr(settings, "decisions_model", "jev-latest")


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
            email="admin@decide.example.com",
            account_name="Instituto",
            user_full_name="Sofía Costa",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
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
    contact = Contact(
        account_id=owner.account.id,
        name="Lucía Pereira",
        phone_number="+59891234567",
        email="lucia@example.com",
    )
    db_session.add(contact)
    await db_session.flush()
    contact_inbox = await ContactInboxBuilder(session=db_session, contact=contact, inbox=inbox).perform()
    await db_session.refresh(contact_inbox, ["inbox"])
    conversation = await create_conversation(
        db_session, contact_inbox=contact_inbox, params=ConversationBuilderParams()
    )
    for content, kind in (
        ("Hola, soy Lucía Pereira, mi cel es 099 123 456. ¿Cuánto sale el curso de inglés?", "incoming"),
        ("Hola Lucía, sale 4500 por mes. ¿Querés que te anote?", "outgoing"),
        ("Sí, quiero anotarme ya, escribime a lucia@example.com", "incoming"),
    ):
        await create_message(
            db_session,
            conversation=conversation,
            params=MessageBuilderParams(content=content, message_type=kind),
            user_id=owner.user.id if kind == "outgoing" else None,
        )
    return {
        "owner": owner,
        "conversation": conversation,
        "headers": await _headers(db_session, owner.user),
        "base": f"/api/v1/accounts/{owner.account.id}/decisions",
    }


def _jev_answers(**choices: str) -> dict:
    return {
        "model": "jev-1.14.0",
        "answers": {
            key: {"type": "choice", "choice": value, "confidence": 0.9, "probabilities": {value: 0.95}}
            for key, value in choices.items()
        },
        "usage": {"input_tokens": 500, "output_tokens": 40},
    }


async def test_settings_start_off_with_institute_questions(client, seeded):
    resp = await client.get(f"{seeded['base']}/settings", headers=seeded["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is False
    assert body["configured"] is False
    assert [q["key"] for q in body["questions"]] == ["intent", "sentiment", "urgency", "team"]
    intent = body["questions"][0]
    assert [o["key"] for o in intent["options"]][:2] == ["inscripcion", "precios"]


async def test_admins_turn_it_on_and_shape_the_questions(client, db_session, seeded):
    db_session.add(Team(account_id=seeded["owner"].account.id, name="Ventas"))
    await db_session.flush()
    resp = await client.put(
        f"{seeded['base']}/settings",
        json={
            "enabled": True,
            "questions": [
                {
                    "key": "intent",
                    "enabled": True,
                    "instructions": "¿Qué quiere?",
                    "options": [{"description": "Inscribirse"}, {"description": "Precios y cuotas"}],
                },
                {"key": "team", "enabled": True, "instructions": "¿Qué equipo?", "options": []},
            ],
        },
        headers=seeded["headers"],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is True
    intent, team = body["questions"]
    assert [o["key"] for o in intent["options"]] == ["inscribirse", "precios_y_cuotas"]
    assert [o["description"] for o in team["options"]] == ["Ventas", "Ningún equipo en particular"]

    bad = await client.put(
        f"{seeded['base']}/settings",
        json={"enabled": True, "questions": [{"key": "x", "instructions": "?", "options": [{"description": "a"}]}]},
        headers=seeded["headers"],
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "decisions.option_count"


async def test_agents_cannot_see_it(client, db_session, seeded):
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent@decide.example.com",
            account_name="Otra",
            user_full_name="Beto",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(account_id=seeded["owner"].account.id, user_id=agent.user.id, role=ACCOUNT_USER_ROLE_AGENT)
    )
    await db_session.flush()
    resp = await client.get(f"{seeded['base']}/settings", headers=await _headers(db_session, agent.user))
    assert resp.status_code == 401


@respx.mock
async def test_a_conversation_is_decided_without_identifying_anyone(db_session, seeded, jev_key):
    jev = respx.post(JEV).mock(
        return_value=httpx.Response(200, json=_jev_answers(intent="inscripcion", sentiment="positivo", urgency="media"))
    )
    await decisions.save_settings(db_session, account_id=seeded["owner"].account.id, enabled=True, questions=None)

    stored = await decisions.decide(db_session, seeded["conversation"])

    sent = json.loads(jev.calls.last.request.content)
    assert jev.calls.last.request.headers["Authorization"] == "Bearer ts-test"
    assert sent["model"] == "jev-latest"
    assert set(sent["questions"]) == {"intent", "sentiment", "urgency"}  # no teams yet
    state = sent["state"]
    assert state.startswith("Cliente: Hola, soy [nombre] [nombre]")
    for secret in ("Lucía", "Pereira", "099 123 456", "lucia@example.com", "Sofía"):
        assert secret not in state
    assert "4500" in state and "Agente:" in state
    assert {(d.question, d.answer) for d in stored} == {
        ("intent", "inscripcion"),
        ("sentiment", "positivo"),
        ("urgency", "media"),
    }
    usage = (
        await db_session.exec(
            select(UsageRecord).where(
                UsageRecord.account_id == seeded["owner"].account.id, UsageRecord.category == "decisions"
            )
        )
    ).all()
    assert len(usage) == 1
    assert usage[0].input_tokens == 500
    assert usage[0].cost == Decimal("0.000021")


@respx.mock
async def test_nothing_is_sent_while_it_is_off(db_session, seeded, jev_key):
    jev = respx.post(JEV).mock(return_value=httpx.Response(200, json=_jev_answers()))
    assert await decisions.decide(db_session, seeded["conversation"]) == []
    assert jev.call_count == 0


async def test_a_customer_message_schedules_a_decision_only_when_on(db_session, seeded, jev_key, monkeypatch):
    scheduled: list[int] = []

    async def fake_enqueue(conversation_id: int) -> None:
        scheduled.append(conversation_id)

    monkeypatch.setattr(decisions, "enqueue_decide", fake_enqueue)
    conversation = seeded["conversation"]

    async def customer_writes(text: str) -> None:
        await create_message(
            db_session,
            conversation=conversation,
            params=MessageBuilderParams(content=text, message_type="incoming"),
            user_id=None,
        )

    await customer_writes("¿Y los horarios?")
    assert scheduled == []
    await decisions.save_settings(db_session, account_id=seeded["owner"].account.id, enabled=True, questions=None)
    await customer_writes("¿Y los horarios?")
    assert scheduled == [conversation.id]


@respx.mock
async def test_people_label_blind_and_the_report_compares(client, db_session, seeded, jev_key):
    respx.route(host="test").pass_through()
    respx.post(JEV).mock(
        return_value=httpx.Response(200, json=_jev_answers(intent="precios", sentiment="neutral", urgency="alta"))
    )
    account_id = seeded["owner"].account.id
    await decisions.save_settings(db_session, account_id=account_id, enabled=True, questions=None)
    await decisions.decide(db_session, seeded["conversation"])

    nxt = (await client.get(f"{seeded['base']}/labeling/next", headers=seeded["headers"])).json()["payload"]
    assert nxt["conversation_id"] == seeded["conversation"].display_id
    assert "Lucía Pereira" in nxt["text"]  # people read it as written
    assert "precios" not in json.dumps(nxt["answered"])  # never the service's answer
    assert "choice" not in json.dumps(nxt)

    resp = await client.post(
        f"{seeded['base']}/labels",
        json={
            "conversation_id": seeded["conversation"].display_id,
            "answers": {"intent": "inscripcion", "sentiment": "neutral", "urgency": "alta"},
        },
        headers=seeded["headers"],
    )
    assert resp.status_code == 200, resp.text
    bad = await client.post(
        f"{seeded['base']}/labels",
        json={"conversation_id": seeded["conversation"].display_id, "answers": {"intent": "nada"}},
        headers=seeded["headers"],
    )
    assert bad.json()["code"] == "decisions.option"
    labels = (await db_session.exec(select(HumanDecision))).all()
    assert {(h.question, h.answer) for h in labels} == {
        ("intent", "inscripcion"),
        ("sentiment", "neutral"),
        ("urgency", "alta"),
    }
    assert (await client.get(f"{seeded['base']}/labeling/next", headers=seeded["headers"])).json()["payload"] is None

    report = (await client.get(f"{seeded['base']}/report", headers=seeded["headers"])).json()
    by_key = {q["key"]: q for q in report["questions"]}
    assert by_key["intent"]["decided"] == 1
    assert by_key["intent"]["agreement"] == 0.0  # said precios, a person said inscripcion
    assert by_key["sentiment"]["agreement"] == 1.0
    assert by_key["urgency"]["answers"] == {"alta": 1}
    assert report["labeled_conversations"] == 1
    assert report["month"]["calls"] == 1
    assert report["month"]["cost_usd"] == pytest.approx(0.000021)


@respx.mock
async def test_the_team_an_agent_assigned_counts_as_the_human_answer(db_session, seeded, jev_key):
    account_id = seeded["owner"].account.id
    team = Team(account_id=account_id, name="Ventas")
    db_session.add(team)
    await db_session.flush()
    respx.post(JEV).mock(return_value=httpx.Response(200, json=_jev_answers(team=f"team_{team.id}")))
    await decisions.save_settings(db_session, account_id=account_id, enabled=True, questions=None)
    await decisions.decide(db_session, seeded["conversation"])
    conversation = seeded["conversation"]
    conversation.team_id = team.id
    db_session.add(conversation)
    await db_session.flush()

    report = await decisions.report(db_session, account_id=account_id)
    team_q = next(q for q in report["questions"] if q["key"] == "team")
    assert team_q["compared"] == 1
    assert team_q["agreement"] == 1.0
    stored = (await db_session.exec(select(ConversationDecision).where(ConversationDecision.question == "team"))).all()
    assert stored[0].answer == f"team_{team.id}"
