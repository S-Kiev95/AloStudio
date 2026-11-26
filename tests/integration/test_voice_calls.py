"""The voice AI that answers WhatsApp calls (F7 paso 3): who answers, how the
call reaches the voice process and Meta, the handoff to a person and what
the call leaves behind. The voice process and Meta are mocked with respx."""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
import respx
from sqlmodel import select

from app.core.config import get_settings
from app.core.i18n import DEFAULT_LOCALE, t
from app.domains.calls import voice
from app.domains.calls.models import AI_MODE_ALWAYS, AI_MODE_NO_ANSWER, Call, CallInboxSettings
from app.domains.conversations.models import MESSAGE_TYPE_OUTGOING, Conversation, Message
from app.domains.usage.models import UsageRecord
from tests.integration import test_whatsapp_calls as calls_tests
from tests.integration.test_whatsapp_calls import (
    ANSWER,
    _headers,
    _meta_settings_mocks,
    _mock_meta_calls,
    _ring,
    _terminate,
)

pytestmark = pytest.mark.integration

# The calls tests' fixtures: an account with a WhatsApp inbox and its agent.
broadcasts = calls_tests.broadcasts
client = calls_tests.client
seeded = calls_tests.seeded

VOICE_URL = "http://voice.test"


@pytest.fixture
def voice_ready(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "gm-test")
    monkeypatch.setattr(settings, "voice_service_url", VOICE_URL)
    monkeypatch.setattr(settings, "voice_service_token", "vt-test")
    return settings


@pytest.fixture
def queued(monkeypatch) -> list[tuple[int, timedelta]]:
    """The AI's answers that would go to the worker."""
    sent: list[tuple[int, timedelta]] = []

    async def enqueue(*, call_id: int, delay: timedelta) -> None:
        sent.append((call_id, delay))

    monkeypatch.setattr(voice, "enqueue_answer", enqueue)
    return sent


async def _mode(db_session, seeded, mode: str, **extra: Any) -> CallInboxSettings:
    row = await db_session.get(CallInboxSettings, seeded["inbox"].id)
    row.ai_mode = mode
    for key, value in extra.items():
        setattr(row, key, value)
    db_session.add(row)
    await db_session.flush()
    return row


def _mock_voice(status: int = 200) -> respx.Route:
    return respx.post(f"{VOICE_URL}/calls").mock(
        return_value=httpx.Response(status, json={"sdp_answer": ANSWER} if status == 200 else {})
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@respx.mock
async def test_the_ai_needs_the_installation_set_up(client, db_session, seeded):
    respx.route(host="test").pass_through()
    _meta_settings_mocks()
    admin_h = await _headers(db_session, seeded["admin"])
    url = f"{seeded['base']}/settings/{seeded['inbox'].id}"

    shown = (await client.get(url, headers=admin_h)).json()
    assert shown["ai_available"] is False
    assert shown["ai_mode"] == "off"

    resp = await client.put(url, json={"enabled": True, "ai_mode": "always"}, headers=admin_h)
    assert resp.status_code == 422
    assert resp.json()["code"] == "calls.ai_unavailable"


@respx.mock
async def test_an_admin_gives_the_calls_to_the_ai(client, db_session, seeded, voice_ready):
    respx.route(host="test").pass_through()
    _meta_settings_mocks()
    admin_h = await _headers(db_session, seeded["admin"])
    url = f"{seeded['base']}/settings/{seeded['inbox'].id}"

    resp = await client.put(
        url,
        json={
            "enabled": True,
            "ai_mode": "no_answer",
            "ai_greeting": "Hola, CTC Salto.",
            "ai_instructions": "Las inscripciones abren en marzo.",
            "ai_voice": "Kore",
        },
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ai_available"] is True
    assert (body["ai_mode"], body["ai_greeting"], body["ai_voice"]) == (
        "no_answer",
        "Hola, CTC Salto.",
        "Kore",
    )
    bad = await client.put(url, json={"enabled": True, "ai_voice": "Nadie"}, headers=admin_h)
    assert bad.status_code == 422
    assert bad.json()["code"] == "calls.ai_voice"

    agent_h = await _headers(db_session, seeded["agent"])
    denied = await client.put(url, json={"enabled": True, "ai_mode": "off"}, headers=agent_h)
    assert denied.status_code == 401


# ---------------------------------------------------------------------------
# Who answers
# ---------------------------------------------------------------------------
async def test_with_the_ai_always_the_call_never_rings(db_session, seeded, voice_ready, queued):
    await _mode(db_session, seeded, AI_MODE_ALWAYS)
    call = await _ring(db_session, seeded)
    assert call.status == "connecting"
    assert call.ai_answered and call.answered_by_id is None
    assert queued == [(call.id, timedelta(seconds=1))]
    message = await db_session.get(Message, call.message_id)
    assert message.content_attributes["data"]["ai"] is True


async def test_without_the_ai_set_up_the_call_rings(db_session, seeded, queued):
    await _mode(db_session, seeded, AI_MODE_ALWAYS)
    call = await _ring(db_session, seeded)
    assert call.status == "ringing" and not call.ai_answered
    assert queued == []


async def test_a_conversation_in_a_persons_hands_rings_for_people_first(
    db_session, seeded, voice_ready, queued
):
    await _mode(db_session, seeded, AI_MODE_ALWAYS)
    first = await _ring(db_session, seeded, "wacid.ONE")
    conversation = await db_session.get(Conversation, first.conversation_id)
    conversation.status = 0
    db_session.add(conversation)
    # Sofía wrote to the customer a while ago.
    db_session.add(
        Message(
            account_id=conversation.account_id,
            inbox_id=conversation.inbox_id,
            conversation_id=conversation.id,
            message_type=MESSAGE_TYPE_OUTGOING,
            content="Te llamo en un rato.",
            sender_type="User",
            sender_id=seeded["agent"].id,
        )
    )
    await db_session.flush()
    queued.clear()

    second = await _ring(db_session, seeded, "wacid.TWO")
    assert second.status == "ringing" and not second.ai_answered
    # Nobody of the team picks up in 20 s: the AI answers (owner, 2026-11-26).
    assert queued == [(second.id, timedelta(seconds=20))]
    with respx.mock:
        _mock_voice()
        _mock_meta_calls()
        assert await voice.answer_with_ai(db_session, call_id=second.id) == "answered"


async def test_the_ai_takes_a_call_nobody_answered(db_session, seeded, voice_ready, queued):
    await _mode(db_session, seeded, AI_MODE_NO_ANSWER)
    call = await _ring(db_session, seeded)
    assert call.status == "ringing"
    assert queued == [(call.id, timedelta(seconds=20))]

    with respx.mock:
        _mock_voice()
        _mock_meta_calls()
        assert await voice.answer_with_ai(db_session, call_id=call.id) == "answered"
    await db_session.refresh(call)
    assert call.status == "in_progress" and call.ai_answered


async def test_a_call_an_agent_took_in_the_wait_stays_theirs(
    db_session, seeded, voice_ready, queued
):
    from app.domains.calls import service as calls_service

    await _mode(db_session, seeded, AI_MODE_NO_ANSWER)
    call = await _ring(db_session, seeded)
    assert await calls_service.claim(db_session, call=call, user_id=seeded["agent"].id)
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(f"{VOICE_URL}/calls")
        assert await voice.answer_with_ai(db_session, call_id=call.id) == "taken"
        assert not route.called


# ---------------------------------------------------------------------------
# Answering
# ---------------------------------------------------------------------------
async def test_the_voice_process_answers_and_meta_gets_its_sdp(
    db_session, seeded, voice_ready, queued
):
    await _mode(
        db_session,
        seeded,
        AI_MODE_ALWAYS,
        ai_greeting="Hola, CTC Salto.",
        ai_instructions="Las inscripciones abren en marzo.",
    )
    call = await _ring(db_session, seeded)
    with respx.mock:
        service = _mock_voice()
        meta = _mock_meta_calls()
        assert await voice.answer_with_ai(db_session, call_id=call.id) == "answered"

    sent = json.loads(service.calls.last.request.content)
    assert service.calls.last.request.headers["Authorization"] == "Bearer vt-test"
    assert sent["provider_call_id"] == "wacid.ABC"
    assert sent["sdp_offer"].startswith("v=0")
    assert sent["model"] == "gemini-3.8-live"
    disclaimer = t(DEFAULT_LOCALE, "calls.ai.disclaimer")
    assert sent["opening"] == f"Hola, CTC Salto. {disclaimer}"
    assert sent["opening_delay"] == 0
    instructions = sent["instructions"]
    # Always says it is an AI and that it is not binding, after the greeting.
    assert f"«Hola, CTC Salto. {t(DEFAULT_LOCALE, 'calls.ai.disclaimer')}»" in instructions
    assert "Las inscripciones abren en marzo." in instructions
    assert "Lucía Pereira" in instructions
    actions = [json.loads(c.request.content)["action"] for c in meta.calls]
    assert actions == ["pre_accept", "accept"]
    assert json.loads(meta.calls.last.request.content)["session"]["sdp"] == ANSWER
    await db_session.refresh(call)
    assert call.status == "in_progress"


async def test_when_the_voice_process_fails_the_call_rings_for_people(
    db_session, seeded, voice_ready, queued
):
    await _mode(db_session, seeded, AI_MODE_ALWAYS)
    call = await _ring(db_session, seeded)
    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{VOICE_URL}/calls").mock(return_value=httpx.Response(503))
        meta = _mock_meta_calls()
        assert await voice.answer_with_ai(db_session, call_id=call.id) == "service_failed"
        assert not meta.called
    await db_session.refresh(call)
    assert call.status == "ringing" and not call.ai_answered


async def test_when_meta_refuses_the_ai_the_call_rings_for_people(
    db_session, seeded, voice_ready, queued
):
    await _mode(db_session, seeded, AI_MODE_ALWAYS)
    call = await _ring(db_session, seeded)
    with respx.mock:
        _mock_voice()
        ended = respx.post(f"{VOICE_URL}/calls/wacid.ABC/end").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        _mock_meta_calls(400, {"error": {"message": "Invalid SDP", "code": 138000}})
        assert await voice.answer_with_ai(db_session, call_id=call.id) == "pre_accept_failed"
        assert ended.called
    await db_session.refresh(call)
    assert call.status == "ringing" and not call.ai_answered


# ---------------------------------------------------------------------------
# During and after the call
# ---------------------------------------------------------------------------
async def _answered(db_session, seeded, call_id: str = "wacid.ABC") -> Call:
    await _mode(db_session, seeded, AI_MODE_ALWAYS)
    call = await _ring(db_session, seeded, call_id)
    with respx.mock:
        _mock_voice()
        _mock_meta_calls()
        assert await voice.answer_with_ai(db_session, call_id=call.id) == "answered"
    await db_session.refresh(call)
    return call


async def test_asking_for_a_person_hands_the_conversation_over(
    db_session, seeded, voice_ready, queued
):
    inbox = seeded["inbox"]
    inbox.handoff_assignee_id = seeded["agent"].id
    db_session.add(inbox)
    await db_session.flush()
    call = await _answered(db_session, seeded)

    assert await voice.ai_handoff(
        db_session,
        provider_call_id="wacid.ABC",
        reason="Quiere hablar con alguien de cobranzas",
        summary="Pregunta por una cuota atrasada.",
    )
    conversation = await db_session.get(Conversation, call.conversation_id)
    assert conversation.assignee_id == seeded["agent"].id
    assert t(DEFAULT_LOCALE, "calls.ai.label") in (conversation.cached_label_list or "")
    note = (
        await db_session.exec(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.private == True,  # noqa: E712
            )
        )
    ).first()
    assert note is not None and "cuota atrasada" in note.content

    # The next call from this customer rings for the people first.
    queued.clear()
    again = await _ring(db_session, seeded, "wacid.NEXT")
    assert again.status == "ringing" and not again.ai_answered
    assert queued == [(again.id, timedelta(seconds=20))]


async def test_resolving_gives_the_conversation_back_to_the_ai(
    db_session, seeded, voice_ready, queued
):
    from app.domains.conversations.service import toggle_status

    await _answered(db_session, seeded)
    assert await voice.ai_handoff(
        db_session, provider_call_id="wacid.ABC", reason="Quiere una persona", summary="-"
    )
    call = await voice.calls.by_provider_id(db_session, "wacid.ABC")
    conversation = await db_session.get(Conversation, call.conversation_id)
    await toggle_status(db_session, conversation=conversation, status="resolved")
    await db_session.refresh(conversation)
    assert t(DEFAULT_LOCALE, "calls.ai.label") not in (conversation.cached_label_list or "")

    # The next call reopens it, and the AI takes it at once.
    queued.clear()
    again = await _ring(db_session, seeded, "wacid.AFTER")
    assert again.status == "connecting" and again.ai_answered


async def test_the_ai_hangs_up_and_meta_closes_the_call(db_session, seeded, voice_ready, queued):
    call = await _answered(db_session, seeded)
    with respx.mock:
        meta = _mock_meta_calls()
        assert await voice.ai_hangup(db_session, provider_call_id="wacid.ABC")
        assert json.loads(meta.calls.last.request.content)["action"] == "terminate"
    await db_session.refresh(call)
    assert call.status == "completed"


async def test_metas_end_drops_the_call_in_the_voice_process(
    db_session, seeded, voice_ready, queued
):
    from app.domains.whatsapp.incoming_cloud import process_cloud_webhook

    call = await _answered(db_session, seeded)
    with respx.mock:
        ended = respx.post(f"{VOICE_URL}/calls/wacid.ABC/end").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await process_cloud_webhook(
            db_session,
            channel=seeded["channel"],
            inbox=seeded["inbox"],
            payload=_terminate(duration=42, start_time="1763140010"),
        )
        assert ended.called
    await db_session.refresh(call)
    assert (call.status, call.duration_seconds) == ("completed", 42)


async def test_the_call_keeps_what_was_said_and_what_it_cost(
    db_session, seeded, voice_ready, queued
):
    call = await _answered(db_session, seeded)
    await voice.ai_call_over(
        db_session,
        provider_call_id="wacid.ABC",
        model="gemini-3.8-live",
        usage={
            "input_tokens": 1_600,
            "output_tokens": 1_200,
            "cached_tokens": 0,
            "input_audio_tokens": 1_500,
            "output_audio_tokens": 1_000,
        },
        segments=[
            {"speaker": "business", "text": "Hola, CTC Salto. Soy un asistente de IA."},
            {"speaker": "customer", "text": "¿Cuándo abren las inscripciones?"},
        ],
    )
    record = (
        await db_session.exec(
            select(UsageRecord).where(
                UsageRecord.account_id == seeded["account"].id,
                UsageRecord.category == "voice_call",
            )
        )
    ).one()
    # 100 text in, 1500 audio in, 200 text out, 1000 audio out.
    expected = (
        100 * Decimal("0.75") + 1500 * Decimal("3") + 200 * Decimal("4.5") + 1000 * Decimal("12")
    ) / Decimal(1_000_000)
    assert record.cost == expected.quantize(Decimal("0.000001"))
    await db_session.refresh(call)
    assert [s["speaker"] for s in call.transcript] == ["business", "customer"]
    message = await db_session.get(Message, call.message_id)
    assert "inscripciones" in message.content


# ---------------------------------------------------------------------------
# Sobre el negocio, said once for every AI of the account
# ---------------------------------------------------------------------------
async def test_admins_write_what_the_business_is_and_everybody_reads_it(
    client, db_session, seeded
):
    url = f"/api/v1/accounts/{seeded['account'].id}/business_profile"
    admin_h = await _headers(db_session, seeded["admin"])
    agent_h = await _headers(db_session, seeded["agent"])

    assert (await client.get(url, headers=agent_h)).json()["text"] == ""
    denied = await client.put(url, json={"text": "Instituto"}, headers=agent_h)
    assert denied.status_code == 401
    saved = await client.put(
        url, json={"text": "  CTC Salto: cursos de inglés y Excel.  "}, headers=admin_h
    )
    assert saved.status_code == 200, saved.text
    assert (await client.get(url, headers=agent_h)).json()["text"] == (
        "CTC Salto: cursos de inglés y Excel."
    )
    too_long = await client.put(url, json={"text": "x" * 8001}, headers=admin_h)
    assert too_long.status_code == 422


async def test_the_voice_ai_reads_the_business_and_waits_for_metas_notice(
    db_session, seeded, voice_ready, queued, monkeypatch
):
    from app.domains.accounts.service import set_business_profile

    account = seeded["account"]
    set_business_profile(account, "CTC Salto: cursos de inglés y Excel.")
    db_session.add(account)
    monkeypatch.setattr(get_settings(), "call_recording_allowed", True)
    await _mode(db_session, seeded, AI_MODE_ALWAYS, transcribe=True, purpose="seguimiento")
    call = await _ring(db_session, seeded)
    with respx.mock:
        service = _mock_voice()
        _mock_meta_calls()
        assert await voice.answer_with_ai(db_session, call_id=call.id) == "answered"
    sent = json.loads(service.calls.last.request.content)
    assert "Sobre el negocio:\nCTC Salto: cursos de inglés y Excel." in sent["instructions"]
    # Meta reads its transcription notice first: the AI greets after it.
    assert sent["opening_delay"] == voice.NOTICE_WAIT_SECONDS
