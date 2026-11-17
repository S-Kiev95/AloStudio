"""WhatsApp calls (F7): Meta's ``calls`` webhook, answering from the panel,
and the number's call settings. Meta's Graph API is mocked with respx."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import delete, select

from app.core import realtime
from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.core.i18n import DEFAULT_LOCALE, t
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.calls import service as calls_service
from app.domains.calls.models import Call, CallInboxSettings
from app.domains.calls.whatsapp import retry_pending_media
from app.domains.contacts.models import Contact
from app.domains.conversations.models import (
    CONTENT_TYPE_VOICE_CALL,
    FILE_TYPE_AUDIO,
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Attachment,
    Conversation,
    Message,
)
from app.domains.inboxes.models import WHATSAPP_PROVIDER_CLOUD, InboxMember
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.domains.whatsapp.incoming_cloud import process_cloud_webhook
from app.domains.working_hours.models import WorkingHour
from app.main import app

pytestmark = pytest.mark.integration

GRAPH = r"https://graph\.facebook\.com/v[\d.]+/"
OFFER = "v=0\r\no=- 4611 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
ANSWER = "v=0\r\no=- 9 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\na=answer\r\n"


class _Recorder(realtime.RealtimeBroadcaster):
    """Keeps what would go to Redis."""

    def __init__(self) -> None:
        self.sent: list[tuple[set[str], str, dict[str, Any]]] = []

    async def publish(self, channels, event, data):  # type: ignore[override]
        self.sent.append((set(channels), event, data))
        return len(set(channels))

    async def close(self) -> None:
        return None


@pytest.fixture
def broadcasts() -> _Recorder:
    recorder = _Recorder()
    realtime.set_broadcaster(recorder)
    return recorder


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
            email="admin@calls.example.com",
            account_name="Instituto",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="sofia@calls.example.com",
            account_name="Otra",
            user_full_name="Sofía",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    outsider = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="otro@calls.example.com",
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
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WhatsApp CTC",
            channel_type="whatsapp",
            channel_params={
                "phone_number": "+59899000111",
                "provider": WHATSAPP_PROVIDER_CLOUD,
                "provider_config": {
                    "api_key": "EAAtoken",
                    "phone_number_id": "p1",
                    "business_account_id": "b1",
                },
            },
        ),
    ).perform()
    db_session.add(InboxMember(inbox_id=result.inbox.id, user_id=agent.user.id))
    # An unanswered call texts the customer "we call you back"; here only the
    # tests about it turn that on, with Meta mocked.
    db_session.add(
        CallInboxSettings(
            inbox_id=result.inbox.id, account_id=owner.account.id, missed_call_reply=False
        )
    )
    await db_session.flush()
    return {
        "account": owner.account,
        "channel": result.channel,
        "inbox": result.inbox,
        "admin": owner.user,
        "agent": agent.user,
        "outsider": outsider.user,
        "base": f"/api/v1/accounts/{owner.account.id}/calls",
    }


def _calls_payload(item: dict[str, Any], **value: Any) -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "b1",
                "changes": [
                    {
                        "field": "calls",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "59899000111", "phone_number_id": "p1"},
                            "contacts": [{"profile": {"name": "Lucía Pereira"}, "wa_id": "59891234567"}],
                            "calls": [item],
                            **value,
                        },
                    }
                ],
            }
        ],
    }


def _connect(call_id: str = "wacid.ABC") -> dict[str, Any]:
    return _calls_payload(
        {
            "id": call_id,
            "to": "59899000111",
            "from": "59891234567",
            "event": "connect",
            "timestamp": "1763140000",
            "direction": "USER_INITIATED",
            "session": {"sdp_type": "offer", "sdp": OFFER},
        }
    )


def _terminate(call_id: str = "wacid.ABC", **extra: Any) -> dict[str, Any]:
    return _calls_payload(
        {
            "id": call_id,
            "to": "59899000111",
            "from": "59891234567",
            "event": "terminate",
            "direction": "USER_INITIATED",
            "timestamp": "1763140200",
            "status": "COMPLETED",
            **extra,
        }
    )


async def _ring(db_session, seeded, call_id: str = "wacid.ABC") -> Call:
    await process_cloud_webhook(
        db_session, channel=seeded["channel"], inbox=seeded["inbox"], payload=_connect(call_id)
    )
    call = await calls_service.by_provider_id(db_session, call_id)
    assert call is not None
    return call


def _mock_meta_calls(status: int = 200, body: dict[str, Any] | None = None) -> respx.Route:
    return respx.post(url__regex=GRAPH + r"p1/calls(\?|$)").mock(
        return_value=httpx.Response(status, json=body or {"messaging_product": "whatsapp", "success": True})
    )


# ---------------------------------------------------------------------------
# Ringing
# ---------------------------------------------------------------------------
async def test_a_call_rings_in_the_conversation(db_session, seeded, broadcasts):
    call = await _ring(db_session, seeded)

    assert call.status == "ringing"
    assert call.sdp_offer == OFFER
    assert call.from_number == "+59891234567"
    contact = await db_session.get(Contact, call.contact_id)
    assert contact.name == "Lucía Pereira"
    message = await db_session.get(Message, call.message_id)
    assert message.content_type == CONTENT_TYPE_VOICE_CALL
    assert message.conversation_id == call.conversation_id
    assert message.source_id == "wacid.ABC"
    data = message.content_attributes["data"]
    assert data["status"] == "ringing"
    assert data["call_sid"] == "wacid.ABC"
    assert data["call_direction"] == "inbound"

    events = [(tokens, data) for tokens, event, data in broadcasts.sent if event == "call.updated"]
    assert events, "the inbox's agents hear the call"
    tokens, payload = events[-1]
    assert seeded["agent"].pubsub_token in tokens
    assert seeded["admin"].pubsub_token in tokens
    assert seeded["outsider"].pubsub_token not in tokens
    assert payload["call"]["status"] == "ringing"
    assert payload["call"]["can_answer"] is True
    assert "sdp_offer" not in payload["call"]


async def test_meta_repeating_the_call_does_not_duplicate_it(db_session, seeded):
    await _ring(db_session, seeded)
    await _ring(db_session, seeded)
    rows = (await db_session.exec(select(Call).where(Call.provider_call_id == "wacid.ABC"))).all()
    assert len(rows) == 1


async def test_only_the_inbox_agents_see_the_call(client, db_session, seeded):
    call = await _ring(db_session, seeded)
    agent_h = await _headers(db_session, seeded["agent"])
    outsider_h = await _headers(db_session, seeded["outsider"])

    seen = (await client.get(f"{seeded['base']}/active", headers=agent_h)).json()["payload"]
    assert [c["id"] for c in seen] == [call.id]
    assert seen[0]["contact"]["name"] == "Lucía Pereira"
    assert (await client.get(f"{seeded['base']}/active", headers=outsider_h)).json()["payload"] == []
    assert (await client.get(f"{seeded['base']}/{call.id}", headers=outsider_h)).status_code == 404
    detail = (await client.get(f"{seeded['base']}/{call.id}", headers=agent_h)).json()
    assert detail["sdp_offer"] == OFFER


# ---------------------------------------------------------------------------
# Answering
# ---------------------------------------------------------------------------
@respx.mock
async def test_one_agent_takes_the_call_and_meta_gets_the_answer(client, db_session, seeded):
    respx.route(host="test").pass_through()
    meta = _mock_meta_calls()
    call = await _ring(db_session, seeded)
    agent_h = await _headers(db_session, seeded["agent"])
    admin_h = await _headers(db_session, seeded["admin"])

    resp = await client.post(
        f"{seeded['base']}/{call.id}/pre_accept", json={"sdp": ANSWER}, headers=agent_h
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "connecting"
    sent = json.loads(meta.calls.last.request.content)
    assert sent == {
        "messaging_product": "whatsapp",
        "call_id": "wacid.ABC",
        "action": "pre_accept",
        "session": {"sdp_type": "answer", "sdp": ANSWER},
    }
    assert meta.calls.last.request.headers["Authorization"] == "Bearer EAAtoken"

    late = await client.post(
        f"{seeded['base']}/{call.id}/pre_accept", json={"sdp": ANSWER}, headers=admin_h
    )
    assert late.status_code == 409
    assert late.json()["code"] == "calls.taken"

    resp = await client.post(
        f"{seeded['base']}/{call.id}/accept", json={"sdp": ANSWER}, headers=agent_h
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["answered_by"]["name"] == "Sofía"
    assert json.loads(meta.calls.last.request.content)["action"] == "accept"
    message = await db_session.get(Message, call.message_id)
    assert message.content_attributes["data"]["status"] == "in-progress"
    assert message.content_attributes["data"]["answered_by"]["name"] == "Sofía"


@respx.mock
async def test_when_meta_refuses_the_answer_the_call_is_free_again(client, db_session, seeded):
    respx.route(host="test").pass_through()
    _mock_meta_calls(400, {"error": {"message": "Invalid SDP", "code": 138000}})
    call = await _ring(db_session, seeded)
    agent_h = await _headers(db_session, seeded["agent"])

    resp = await client.post(
        f"{seeded['base']}/{call.id}/pre_accept", json={"sdp": ANSWER}, headers=agent_h
    )
    assert resp.status_code == 502
    assert resp.json()["code"] == "calls.refused"
    assert resp.json()["message"] == "Invalid SDP"
    await db_session.refresh(call)
    assert call.status == "ringing"
    assert call.answered_by_id is None


@respx.mock
async def test_only_who_took_the_call_can_confirm_it(client, db_session, seeded):
    respx.route(host="test").pass_through()
    _mock_meta_calls()
    call = await _ring(db_session, seeded)
    agent_h = await _headers(db_session, seeded["agent"])
    admin_h = await _headers(db_session, seeded["admin"])
    await client.post(f"{seeded['base']}/{call.id}/pre_accept", json={"sdp": ANSWER}, headers=agent_h)

    resp = await client.post(f"{seeded['base']}/{call.id}/accept", json={"sdp": ANSWER}, headers=admin_h)
    assert resp.status_code == 409
    assert resp.json()["code"] == "calls.not_yours"


# ---------------------------------------------------------------------------
# Ending
# ---------------------------------------------------------------------------
@respx.mock
async def test_meta_end_event_records_the_length(client, db_session, seeded):
    respx.route(host="test").pass_through()
    _mock_meta_calls()
    call = await _ring(db_session, seeded)
    agent_h = await _headers(db_session, seeded["agent"])
    await client.post(f"{seeded['base']}/{call.id}/pre_accept", json={"sdp": ANSWER}, headers=agent_h)
    await client.post(f"{seeded['base']}/{call.id}/accept", json={"sdp": ANSWER}, headers=agent_h)

    await process_cloud_webhook(
        db_session,
        channel=seeded["channel"],
        inbox=seeded["inbox"],
        payload=_terminate(start_time="1763140010", end_time="1763140135", duration=125),
    )
    await db_session.refresh(call)
    assert call.status == "completed"
    assert call.duration_seconds == 125
    assert call.ended_at == datetime.fromtimestamp(1763140135, tz=UTC)
    assert call.sdp_offer is None
    message = await db_session.get(Message, call.message_id)
    assert message.content_attributes["data"]["status"] == "completed"
    assert message.content_attributes["data"]["duration"] == 125


async def test_a_call_nobody_answered_is_missed(db_session, seeded):
    call = await _ring(db_session, seeded)
    await process_cloud_webhook(
        db_session, channel=seeded["channel"], inbox=seeded["inbox"], payload=_terminate()
    )
    await db_session.refresh(call)
    assert call.status == "missed"
    message = await db_session.get(Message, call.message_id)
    assert message.content_attributes["data"]["status"] == "no-answer"


async def test_a_failed_call_keeps_metas_reason(db_session, seeded):
    call = await _ring(db_session, seeded)
    payload = _terminate(status="FAILED")
    payload["entry"][0]["changes"][0]["value"]["errors"] = [
        {"code": 138001, "message": "Receiver unavailable"}
    ]
    await process_cloud_webhook(
        db_session, channel=seeded["channel"], inbox=seeded["inbox"], payload=payload
    )
    await db_session.refresh(call)
    assert call.status == "failed"
    assert call.end_reason == "138001: Receiver unavailable"


@respx.mock
async def test_hanging_up_ends_the_call_on_meta(client, db_session, seeded):
    respx.route(host="test").pass_through()
    meta = _mock_meta_calls()
    call = await _ring(db_session, seeded)
    agent_h = await _headers(db_session, seeded["agent"])
    await client.post(f"{seeded['base']}/{call.id}/pre_accept", json={"sdp": ANSWER}, headers=agent_h)
    await client.post(f"{seeded['base']}/{call.id}/accept", json={"sdp": ANSWER}, headers=agent_h)

    resp = await client.post(f"{seeded['base']}/{call.id}/hangup", headers=agent_h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "completed"
    assert json.loads(meta.calls.last.request.content)["action"] == "terminate"


async def test_metas_end_is_not_undone_by_a_late_confirmation(db_session, seeded):
    """The customer hung up while the agent's answer was being confirmed."""
    call = await _ring(db_session, seeded)
    assert await calls_service.claim(db_session, call=call, user_id=seeded["agent"].id)
    await process_cloud_webhook(
        db_session, channel=seeded["channel"], inbox=seeded["inbox"], payload=_terminate()
    )
    await calls_service.mark_in_progress(db_session, call=call)
    await db_session.refresh(call)
    assert call.status == "missed"


async def test_hanging_up_after_metas_end_keeps_metas_length(db_session, seeded):
    call = await _ring(db_session, seeded)
    assert await calls_service.claim(db_session, call=call, user_id=seeded["agent"].id)
    await calls_service.mark_in_progress(db_session, call=call)
    await process_cloud_webhook(
        db_session,
        channel=seeded["channel"],
        inbox=seeded["inbox"],
        payload=_terminate(start_time="1763140010", end_time="1763140108", duration=98),
    )
    await calls_service.finish(db_session, call=call, status="completed")  # the agent's hang-up
    await db_session.refresh(call)
    message = await db_session.get(Message, call.message_id)
    assert call.duration_seconds == 98
    assert message.content_attributes["data"]["duration"] == 98


async def test_calls_whose_end_never_came_are_closed(db_session, seeded):
    call = await _ring(db_session, seeded)
    call.created_at = datetime.now(UTC) - timedelta(minutes=10)
    db_session.add(call)
    await db_session.flush()

    assert await calls_service.expire_stale(db_session) >= 1
    await db_session.refresh(call)
    assert call.status == "missed"


async def test_a_call_being_answered_outlives_the_ringing_time(db_session, seeded):
    """Answering can take longer than the ringing window; the call must stay
    on the agent's screen and must not be closed under them."""
    call = await _ring(db_session, seeded)
    assert await calls_service.claim(db_session, call=call, user_id=seeded["agent"].id)
    call.created_at = datetime.now(UTC) - timedelta(minutes=10)
    db_session.add(call)
    await db_session.flush()

    active = await calls_service.active_calls(
        db_session, account_id=seeded["account"].id, user_id=seeded["agent"].id
    )
    assert [c.id for c in active] == [call.id]
    await calls_service.expire_stale(db_session)
    await db_session.refresh(call)
    assert call.status == "connecting"


# ---------------------------------------------------------------------------
# The number's settings
# ---------------------------------------------------------------------------
@respx.mock
async def test_turning_calls_on_with_the_inbox_hours(client, db_session, seeded):
    respx.route(host="test").pass_through()
    inbox = seeded["inbox"]
    inbox.timezone = "America/Montevideo"
    db_session.add(inbox)
    await db_session.exec(delete(WorkingHour).where(WorkingHour.inbox_id == inbox.id))  # type: ignore[call-overload]
    for day in range(7):
        weekend = day in (0, 6)
        db_session.add(
            WorkingHour(
                inbox_id=inbox.id,
                account_id=seeded["account"].id,
                day_of_week=day,
                closed_all_day=weekend,
                open_all_day=False,
                open_hour=None if weekend else 9,
                open_minutes=None if weekend else 0,
                close_hour=None if weekend else 18,
                close_minutes=None if weekend else 30,
            )
        )
    await db_session.flush()
    saved = respx.post(url__regex=GRAPH + r"p1/settings(\?|$)").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    respx.get(url__regex=GRAPH + r"p1/settings(\?|$)").mock(
        return_value=httpx.Response(
            200,
            json={
                "calling": {
                    "status": "ENABLED",
                    "call_icon_visibility": "DEFAULT",
                    "callback_permission_status": "ENABLED",
                    "call_hours": {"status": "ENABLED"},
                }
            },
        )
    )
    admin_h = await _headers(db_session, seeded["admin"])

    resp = await client.put(
        f"{seeded['base']}/settings/{inbox.id}",
        json={"enabled": True, "call_icon_visible": True, "callback_requests": True, "business_hours": True},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {k: body[k] for k in ("enabled", "call_icon_visible", "callback_requests", "business_hours", "restrictions")} == {
        "enabled": True,
        "call_icon_visible": True,
        "callback_requests": True,
        "business_hours": True,
        "restrictions": None,
    }
    calling = json.loads(saved.calls.last.request.content)["calling"]
    assert calling["status"] == "ENABLED"
    assert calling["callback_permission_status"] == "ENABLED"
    hours = calling["call_hours"]
    assert hours["status"] == "ENABLED"
    assert hours["timezone_id"] == "America/Montevideo"
    assert hours["weekly_operating_hours"][0] == {
        "day_of_week": "MONDAY",
        "open_time": "0900",
        "close_time": "1830",
    }
    assert [h["day_of_week"] for h in hours["weekly_operating_hours"]] == [
        "MONDAY",
        "TUESDAY",
        "WEDNESDAY",
        "THURSDAY",
        "FRIDAY",
    ]


async def test_agents_cannot_change_the_call_settings(client, db_session, seeded):
    agent_h = await _headers(db_session, seeded["agent"])
    resp = await client.put(
        f"{seeded['base']}/settings/{seeded['inbox'].id}",
        json={"enabled": True},
        headers=agent_h,
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Recording and transcription
# ---------------------------------------------------------------------------
def _meta_settings_mocks() -> None:
    respx.post(url__regex=GRAPH + r"p1/settings(\?|$)").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    respx.get(url__regex=GRAPH + r"p1/settings(\?|$)").mock(
        return_value=httpx.Response(200, json={"calling": {"status": "ENABLED"}})
    )


def _media_payload(event: str, media_id: str) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": "wacid.ABC",
        "from": "59891234567",
        "event": event,
        "timestamp": "1763140300",
    }
    if event == "call_recording_available":
        item["call_recording"] = {"type": "audio", "audio": {"id": media_id}}
    else:
        item["call_transcript"] = {"document": {"id": media_id}}
    return _calls_payload(item)


@respx.mock
async def test_recording_needs_the_operators_switch(client, db_session, seeded, monkeypatch):
    respx.route(host="test").pass_through()
    _meta_settings_mocks()
    monkeypatch.setattr(calls_service, "recording_allowed", lambda: False)
    admin_h = await _headers(db_session, seeded["admin"])

    shown = await client.get(f"{seeded['base']}/settings/{seeded['inbox'].id}", headers=admin_h)
    assert shown.json()["recording_allowed"] is False
    resp = await client.put(
        f"{seeded['base']}/settings/{seeded['inbox'].id}",
        json={"enabled": True, "record": True},
        headers=admin_h,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "calls.recording_not_allowed"


@respx.mock
async def test_an_inbox_that_records_gets_the_audio_and_the_transcript(
    client, db_session, seeded, monkeypatch
):
    respx.route(host="test").pass_through()
    _meta_settings_mocks()
    meta = _mock_meta_calls()
    monkeypatch.setattr(calls_service, "recording_allowed", lambda: True)
    stored: list[str] = []

    async def fake_store(channel, *, account_id, media_id):
        stored.append(media_id)
        return {"external_url": f"https://files.example.com/{media_id}.ogg", "extension": "ogg"}

    async def fake_download(channel, media_id):
        document = {
            "transcript": {
                "language": "es",
                "segments": [
                    {"speaker": "Business", "channel": 0, "text": "Hola, Instituto CTC."},
                    {"speaker": "Customer", "channel": 1, "text": "Quería anotarme al curso de inglés."},
                ],
            }
        }
        return json.dumps(document).encode(), "application/json"

    monkeypatch.setattr("app.domains.calls.whatsapp.download_and_store_media", fake_store)
    monkeypatch.setattr("app.domains.calls.whatsapp._download_cloud_media", fake_download)
    admin_h = await _headers(db_session, seeded["admin"])
    agent_h = await _headers(db_session, seeded["agent"])

    saved = await client.put(
        f"{seeded['base']}/settings/{seeded['inbox'].id}",
        json={
            "enabled": True,
            "record": True,
            "transcribe": True,
            "purpose": "seguimiento de tu inscripción",
        },
        headers=admin_h,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["record"] is True
    assert saved.json()["purpose"] == "seguimiento de tu inscripción"

    call = await _ring(db_session, seeded)
    await client.post(f"{seeded['base']}/{call.id}/pre_accept", json={"sdp": ANSWER}, headers=agent_h)
    await client.post(f"{seeded['base']}/{call.id}/accept", json={"sdp": ANSWER}, headers=agent_h)
    accepted = json.loads(meta.calls.last.request.content)
    notice = {
        "status": "ENABLED",
        "purpose": "seguimiento de tu inscripción",
        "announcement_language": "es",
    }
    assert accepted["recording"] == notice
    assert accepted["transcription"] == notice
    await db_session.refresh(call)
    assert call.recording_requested and call.transcription_requested

    await process_cloud_webhook(
        db_session, channel=seeded["channel"], inbox=seeded["inbox"], payload=_terminate(duration=40)
    )
    message = await db_session.get(Message, call.message_id)
    assert message.content_attributes["data"]["recording"] == "pending"

    for event, media_id in (
        ("call_recording_available", "rec-1"),
        ("call_transcription_available", "doc-1"),
    ):
        await process_cloud_webhook(
            db_session,
            channel=seeded["channel"],
            inbox=seeded["inbox"],
            payload=_media_payload(event, media_id),
        )
    await db_session.refresh(call)
    assert stored == ["rec-1"]
    assert call.recording_attachment_id is not None
    assert call.recording_media_id is None
    assert [seg["speaker"] for seg in call.transcript] == ["business", "customer"]

    attachments = (
        await db_session.exec(select(Attachment).where(Attachment.message_id == call.message_id))
    ).all()
    assert [a.external_url for a in attachments] == ["https://files.example.com/rec-1.ogg"]
    assert attachments[0].file_type == FILE_TYPE_AUDIO
    await db_session.refresh(message)
    data = message.content_attributes["data"]
    assert data["recording"] == "ready"
    assert data["transcription"] == "ready"
    assert data["transcript"][1]["text"] == "Quería anotarme al curso de inglés."
    assert "Cliente: Quería anotarme al curso de inglés." in message.content


async def test_a_copy_that_failed_is_retried_later(db_session, seeded, monkeypatch):
    call = await _ring(db_session, seeded)
    attempts: list[str] = []

    async def failing(channel, *, account_id, media_id):
        attempts.append(media_id)
        return None

    monkeypatch.setattr("app.domains.calls.whatsapp.download_and_store_media", failing)
    await process_cloud_webhook(
        db_session,
        channel=seeded["channel"],
        inbox=seeded["inbox"],
        payload=_media_payload("call_recording_available", "rec-9"),
    )
    await db_session.refresh(call)
    assert call.recording_media_id == "rec-9"
    assert call.recording_attachment_id is None

    async def working(channel, *, account_id, media_id):
        attempts.append(media_id)
        return {"external_url": "https://files.example.com/rec-9.ogg", "extension": "ogg"}

    monkeypatch.setattr("app.domains.calls.whatsapp.download_and_store_media", working)
    assert await retry_pending_media(db_session) >= 1
    await db_session.refresh(call)
    assert attempts == ["rec-9", "rec-9"]
    assert call.recording_attachment_id is not None
    assert call.recording_media_id is None


# ---------------------------------------------------------------------------
# Calling a customer
# ---------------------------------------------------------------------------
async def _conversation(db_session, seeded) -> Conversation:
    """A conversation with the customer, made by a call that went unanswered."""
    call = await _ring(db_session, seeded, call_id="wacid.IN1")
    await process_cloud_webhook(
        db_session, channel=seeded["channel"], inbox=seeded["inbox"], payload=_terminate("wacid.IN1")
    )
    conversation = await db_session.get(Conversation, call.conversation_id)
    assert conversation is not None
    return conversation


def _status_payload(call_id: str, status: str) -> dict[str, Any]:
    payload = _calls_payload({})
    value = payload["entry"][0]["changes"][0]["value"]
    value.pop("calls")
    value["statuses"] = [
        {
            "id": call_id,
            "timestamp": "1763140400",
            "type": "call",
            "status": status,
            "recipient_id": "59891234567",
        }
    ]
    return payload


@respx.mock
async def test_whether_the_customer_lets_us_call_comes_from_meta(client, db_session, seeded):
    respx.route(host="test").pass_through()
    asked = respx.get(url__regex=GRAPH + r"p1/call_permissions").mock(
        return_value=httpx.Response(
            200,
            json={
                "messaging_product": "whatsapp",
                "permission": {"status": "temporary", "expiration_time": 1763740000},
                "actions": [
                    {"action_name": "send_call_permission_request", "can_perform_action": False},
                    {"action_name": "start_call", "can_perform_action": True},
                ],
            },
        )
    )
    conversation = await _conversation(db_session, seeded)
    agent_h = await _headers(db_session, seeded["agent"])

    resp = await client.get(
        f"{seeded['base']}/permission", params={"conversation_id": conversation.display_id}, headers=agent_h
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "status": "temporary",
        "expires_at": 1763740000,
        "can_call": True,
        "can_request": False,
    }
    assert asked.calls.last.request.url.params["user_wa_id"] == "59891234567"


@respx.mock
async def test_asking_permission_goes_through_meta_and_shows_in_the_chat(client, db_session, seeded):
    respx.route(host="test").pass_through()
    sent = respx.post(url__regex=GRAPH + r"p1/messages(\?|$)").mock(
        return_value=httpx.Response(
            200, json={"messaging_product": "whatsapp", "messages": [{"id": "wamid.PERM1"}]}
        )
    )
    conversation = await _conversation(db_session, seeded)
    agent_h = await _headers(db_session, seeded["agent"])

    resp = await client.post(
        f"{seeded['base']}/permission_request",
        json={"conversation_id": conversation.display_id},
        headers=agent_h,
    )
    assert resp.status_code == 200, resp.text
    assert sent.call_count == 1, "sent once: the reply cascade must not send it again"
    body = json.loads(sent.calls.last.request.content)
    assert body["to"] == "59891234567"
    assert body["interactive"]["type"] == "call_permission_request"
    assert body["interactive"]["action"] == {"name": "call_permission_request"}
    assert body["interactive"]["body"]["text"].startswith("¿Te podemos llamar")
    message = await db_session.get(Message, resp.json()["message_id"])
    assert message.message_type == MESSAGE_TYPE_OUTGOING
    assert message.source_id == "wamid.PERM1"
    assert message.content_attributes["call_permission_request"] is True


async def test_the_customers_answer_becomes_a_message(db_session, seeded):
    conversation = await _conversation(db_session, seeded)
    payload = _calls_payload({})
    change = payload["entry"][0]["changes"][0]
    change["field"] = "messages"
    change["value"].pop("calls")
    change["value"]["messages"] = [
        {
            "from": "59891234567",
            "id": "wamid.REPLY1",
            "timestamp": "1763140500",
            "type": "interactive",
            "context": {"id": "wamid.PERM1"},
            "interactive": {
                "type": "call_permission_reply",
                "call_permission_reply": {
                    "response": "accept",
                    "is_permanent": False,
                    "expiration_timestamp": "1763745300",
                    "response_source": "user_action",
                },
            },
        }
    ]
    await process_cloud_webhook(
        db_session, channel=seeded["channel"], inbox=seeded["inbox"], payload=payload
    )
    message = (
        await db_session.exec(select(Message).where(Message.source_id == "wamid.REPLY1"))
    ).first()
    assert message is not None
    assert message.conversation_id == conversation.id
    assert message.message_type == MESSAGE_TYPE_INCOMING
    assert message.content == "Aceptó que lo llamen por WhatsApp (por 7 días)"
    assert message.content_attributes["call_permission"] == {
        "response": "accept",
        "permanent": False,
        "automatic": False,
        "expires_at": 1763745300,
    }


@respx.mock
async def test_calling_a_customer_from_the_panel(client, db_session, seeded):
    respx.route(host="test").pass_through()
    meta = respx.post(url__regex=GRAPH + r"p1/calls(\?|$)").mock(
        return_value=httpx.Response(
            200, json={"messaging_product": "whatsapp", "calls": [{"id": "wacid.OUT1"}]}
        )
    )
    texted = respx.post(url__regex=GRAPH + r"p1/messages(\?|$)").mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "wamid.X"}]})
    )
    conversation = await _conversation(db_session, seeded)
    agent_h = await _headers(db_session, seeded["agent"])
    admin_h = await _headers(db_session, seeded["admin"])

    resp = await client.post(
        seeded["base"], json={"conversation_id": conversation.display_id, "sdp": OFFER}, headers=agent_h
    )
    assert resp.status_code == 201, resp.text
    placed = resp.json()
    assert placed["direction"] == "outbound"
    assert placed["status"] == "ringing"
    assert placed["answered_by"]["name"] == "Sofía"
    assert placed["can_answer"] is False
    asked = json.loads(meta.calls.last.request.content)
    assert asked == {
        "messaging_product": "whatsapp",
        "to": "59891234567",
        "action": "connect",
        "session": {"sdp_type": "offer", "sdp": OFFER},
    }
    assert texted.call_count == 0, "the call bubble must not be texted to the customer"
    call = await calls_service.by_provider_id(db_session, "wacid.OUT1")
    bubble = await db_session.get(Message, call.message_id)
    assert bubble.message_type == MESSAGE_TYPE_OUTGOING
    assert bubble.content_attributes["data"]["call_direction"] == "outbound"

    # Nobody else can "take" a call an agent is placing.
    taken = await client.post(f"{seeded['base']}/{call.id}/pre_accept", json={"sdp": ANSWER}, headers=admin_h)
    assert taken.status_code == 409

    connect = _calls_payload(
        {
            "id": "wacid.OUT1",
            "to": "59891234567",
            "from": "59899000111",
            "event": "connect",
            "timestamp": "1763140600",
            "direction": "BUSINESS_INITIATED",
            "session": {"sdp_type": "answer", "sdp": ANSWER},
        }
    )
    await process_cloud_webhook(db_session, channel=seeded["channel"], inbox=seeded["inbox"], payload=connect)
    mine = (await client.get(f"{seeded['base']}/{call.id}", headers=agent_h)).json()
    assert mine["sdp_answer"] == ANSWER
    theirs = (await client.get(f"{seeded['base']}/{call.id}", headers=admin_h)).json()
    assert "sdp_answer" not in theirs

    await process_cloud_webhook(
        db_session, channel=seeded["channel"], inbox=seeded["inbox"], payload=_status_payload("wacid.OUT1", "ACCEPTED")
    )
    await db_session.refresh(call)
    assert call.status == "in_progress"
    assert call.answered_at is not None

    await process_cloud_webhook(
        db_session,
        channel=seeded["channel"],
        inbox=seeded["inbox"],
        payload=_terminate("wacid.OUT1", direction="BUSINESS_INITIATED", duration=30, start_time="1763140610"),
    )
    await db_session.refresh(call)
    assert call.status == "completed"
    assert call.duration_seconds == 30


@respx.mock
async def test_a_call_the_customer_rejects_is_missed(client, db_session, seeded):
    respx.route(host="test").pass_through()
    respx.post(url__regex=GRAPH + r"p1/calls(\?|$)").mock(
        return_value=httpx.Response(200, json={"calls": [{"id": "wacid.OUT2"}]})
    )
    conversation = await _conversation(db_session, seeded)
    agent_h = await _headers(db_session, seeded["agent"])
    await client.post(
        seeded["base"], json={"conversation_id": conversation.display_id, "sdp": OFFER}, headers=agent_h
    )
    await process_cloud_webhook(
        db_session, channel=seeded["channel"], inbox=seeded["inbox"], payload=_status_payload("wacid.OUT2", "REJECTED")
    )
    call = await calls_service.by_provider_id(db_session, "wacid.OUT2")
    assert call.status == "missed"
    assert call.end_reason == "rejected"


@respx.mock
async def test_calling_without_permission_says_so(client, db_session, seeded):
    respx.route(host="test").pass_through()
    respx.post(url__regex=GRAPH + r"p1/calls(\?|$)").mock(
        return_value=httpx.Response(
            400, json={"error": {"code": 138006, "message": "No approved call permission"}}
        )
    )
    conversation = await _conversation(db_session, seeded)
    agent_h = await _headers(db_session, seeded["agent"])
    resp = await client.post(
        seeded["base"], json={"conversation_id": conversation.display_id, "sdp": OFFER}, headers=agent_h
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "calls.no_permission"
    assert await calls_service.by_provider_id(db_session, "wacid.OUT3") is None


# ---------------------------------------------------------------------------
# Several calls at once
# ---------------------------------------------------------------------------
def _ring_ids(broadcasts: _Recorder, call_id: int) -> list[int]:
    """Who the latest event about this call rings for."""
    events = [
        data["call"]
        for _, event, data in broadcasts.sent
        if event == "call.updated" and data["call"]["id"] == call_id
    ]
    return events[-1]["ring_user_ids"]


async def test_a_call_rings_for_who_is_free_and_for_all_when_nobody_is(
    db_session, seeded, broadcasts
):
    admin, agent = seeded["admin"].id, seeded["agent"].id
    first = await _ring(db_session, seeded, "wacid.A")
    second = await _ring(db_session, seeded, "wacid.B")
    assert _ring_ids(broadcasts, second.id) == sorted([admin, agent])

    # Sofía takes the first: the second stops ringing for her.
    assert await calls_service.claim(db_session, call=first, user_id=agent)
    assert _ring_ids(broadcasts, second.id) == [admin]

    # The admin takes the second: nobody is free, so a third rings for both.
    assert await calls_service.claim(db_session, call=second, user_id=admin)
    third = await _ring(db_session, seeded, "wacid.C")
    assert _ring_ids(broadcasts, third.id) == sorted([admin, agent])

    # Sofía hangs up: the third rings for her alone.
    await calls_service.mark_in_progress(db_session, call=first)
    await calls_service.finish(db_session, call=first, status="completed")
    assert _ring_ids(broadcasts, third.id) == [agent]


async def test_the_panel_lists_who_hears_each_call(client, db_session, seeded):
    call = await _ring(db_session, seeded)
    agent_h = await _headers(db_session, seeded["agent"])
    listed = (await client.get(f"{seeded['base']}/active", headers=agent_h)).json()["payload"]
    assert listed[0]["id"] == call.id
    assert listed[0]["ring_user_ids"] == sorted([seeded["admin"].id, seeded["agent"].id])


# ---------------------------------------------------------------------------
# A call nobody answered
# ---------------------------------------------------------------------------
def _mock_meta_text() -> respx.Route:
    return respx.post(url__regex=GRAPH + r"p1/messages(\?|$)").mock(
        return_value=httpx.Response(
            200, json={"messaging_product": "whatsapp", "messages": [{"id": "wamid.BACK1"}]}
        )
    )


async def _replies(db_session, conversation_id: int) -> list[Message]:
    rows = (
        await db_session.exec(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.message_type == MESSAGE_TYPE_OUTGOING,
            )
            .order_by(Message.id)  # type: ignore[arg-type]
        )
    ).all()
    return [m for m in rows if (m.content_attributes or {}).get("missed_call_reply")]


async def _reply_to_missed_calls(db_session, seeded) -> None:
    row = await db_session.get(CallInboxSettings, seeded["inbox"].id)
    row.missed_call_reply = True
    db_session.add(row)
    await db_session.flush()


async def _miss(db_session, seeded, call_id: str) -> Call:
    call = await _ring(db_session, seeded, call_id)
    await process_cloud_webhook(
        db_session, channel=seeded["channel"], inbox=seeded["inbox"], payload=_terminate(call_id)
    )
    await db_session.refresh(call)
    assert call.status == "missed"
    return call


@respx.mock
async def test_a_missed_call_says_we_call_back_and_goes_to_the_owner(db_session, seeded):
    texted = _mock_meta_text()
    await _reply_to_missed_calls(db_session, seeded)
    inbox = seeded["inbox"]
    call = await _ring(db_session, seeded, "wacid.A")
    conversation = await db_session.get(Conversation, call.conversation_id)
    # Nobody owns it yet; the inbox's default assignee is Sofía.
    conversation.assignee_id = None
    inbox.enable_auto_assignment = True
    inbox.handoff_assignee_id = seeded["agent"].id
    db_session.add(conversation)
    db_session.add(inbox)
    await db_session.flush()

    await process_cloud_webhook(
        db_session, channel=seeded["channel"], inbox=inbox, payload=_terminate("wacid.A")
    )

    replies = await _replies(db_session, conversation.id)
    assert [m.content for m in replies] == [t(DEFAULT_LOCALE, "calls.missed.reply")]
    assert json.loads(texted.calls.last.request.content)["text"]["body"] == replies[0].content
    await db_session.refresh(conversation)
    assert "llamada-perdida" in (conversation.cached_label_list or "")
    assert conversation.assignee_id == seeded["agent"].id

    # Trying again within the hour: no second message.
    await _miss(db_session, seeded, "wacid.B")
    assert len(await _replies(db_session, conversation.id)) == 1

    # The next call is answered: nobody needs to call back any more.
    third = await _ring(db_session, seeded, "wacid.C")
    assert await calls_service.claim(db_session, call=third, user_id=seeded["agent"].id)
    await calls_service.mark_in_progress(db_session, call=third)
    await db_session.refresh(conversation)
    assert "llamada-perdida" not in (conversation.cached_label_list or "")


async def test_calling_back_clears_the_mark(db_session, seeded):
    missed = await _miss(db_session, seeded, "wacid.A")
    conversation = await db_session.get(Conversation, missed.conversation_id)
    contact = await db_session.get(Contact, missed.contact_id)
    back = await calls_service.start_outbound(
        db_session,
        conversation=conversation,
        contact=contact,
        agent_id=seeded["agent"].id,
        provider="whatsapp",
        provider_call_id="wacid.OUT",
        from_number="+59899000111",
        to_number="+59891234567",
    )
    await calls_service.customer_answered(db_session, call=back)
    await db_session.refresh(conversation)
    assert "llamada-perdida" not in (conversation.cached_label_list or "")


@respx.mock
async def test_an_inbox_changes_or_turns_off_the_missed_call_message(client, db_session, seeded):
    respx.route(host="test").pass_through()
    _meta_settings_mocks()
    texted = _mock_meta_text()
    # An inbox nobody configured yet: on, with our text.
    await db_session.delete(await db_session.get(CallInboxSettings, seeded["inbox"].id))
    await db_session.flush()
    admin_h = await _headers(db_session, seeded["admin"])
    url = f"{seeded['base']}/settings/{seeded['inbox'].id}"

    shown = (await client.get(url, headers=admin_h)).json()
    assert shown["missed_call_reply"] is True
    assert shown["missed_call_text"] == t(DEFAULT_LOCALE, "calls.missed.reply")

    too_long = await client.put(
        url, json={"enabled": True, "missed_call_text": "x" * 1025}, headers=admin_h
    )
    assert too_long.status_code == 422
    assert too_long.json()["code"] == "calls.missed_text"

    # Off: the conversation is still marked, the customer is not written to.
    off = await client.put(url, json={"enabled": True, "missed_call_reply": False}, headers=admin_h)
    assert off.status_code == 200, off.text
    assert off.json()["missed_call_reply"] is False
    first = await _miss(db_session, seeded, "wacid.A")
    assert await _replies(db_session, first.conversation_id) == []
    conversation = await db_session.get(Conversation, first.conversation_id)
    assert "llamada-perdida" in (conversation.cached_label_list or "")
    assert not texted.called

    # On again, in the inbox's own words.
    own = "Ya te llamamos, gracias por esperar."
    on = await client.put(
        url,
        json={"enabled": True, "missed_call_reply": True, "missed_call_text": own},
        headers=admin_h,
    )
    assert on.json()["missed_call_text"] == own
    await _miss(db_session, seeded, "wacid.B")
    assert [m.content for m in await _replies(db_session, first.conversation_id)] == [own]
