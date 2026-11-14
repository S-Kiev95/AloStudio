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
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.calls import service as calls_service
from app.domains.calls.models import Call
from app.domains.contacts.models import Contact
from app.domains.conversations.models import CONTENT_TYPE_VOICE_CALL, Message
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
    assert resp.json() == {
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
