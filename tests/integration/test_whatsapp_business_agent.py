"""Integration tests for the Meta Business Agent handoff on WhatsApp.

Walks the three doors that move a conversation between Meta's AI and the
team: the ``messaging_handovers`` webhook, the
``POST /conversations/:id/thread_control`` endpoint (Meta's Thread
Control API mocked with respx), and resolving a conversation the team
owned. Plus the silent owner stamp on inbound messages and the takeover
recorded when an agent replies.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.conversations.models import (
    CONVERSATION_STATUS_OPEN,
    CONVERSATION_STATUS_RESOLVED,
    MESSAGE_TYPE_ACTIVITY,
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
)
from app.domains.conversations.service import toggle_status
from app.domains.inboxes.models import WHATSAPP_PROVIDER_CLOUD, WhatsappChannel
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams

# Resolve mappers (Conversation.team forward-ref) before first DB op.
from app.domains.teams import models as _teams  # noqa: F401
from app.domains.whatsapp import business_agent as ba
from app.domains.whatsapp.incoming_cloud import process_cloud_webhook
from app.main import app

pytestmark = pytest.mark.integration

_THREAD_CONTROL = (
    "https://api.facebook.com/business/whatsapp/phone_numbers/p1/thread_control"
)
_CUSTOMER = "59899123456"


@pytest.fixture(autouse=True)
def _our_app(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(
        ba, "get_settings", lambda: SimpleNamespace(meta_app_id="111")
    )


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


async def _seed(db_session, *, business_agent: bool = True):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@mba.example.com",
            account_name="MBA",
            user_full_name="Agente Uno",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    config: dict[str, Any] = {
        "api_key": "EAAxxxx",
        "phone_number_id": "p1",
        "business_account_id": "b1",
    }
    if business_agent:
        config[ba.FLAG_ENABLED] = True
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WA Instituto",
            channel_type="whatsapp",
            channel_params={
                "phone_number": "+59847325025",
                "provider": WHATSAPP_PROVIDER_CLOUD,
                "provider_config": config,
            },
        ),
    ).perform()
    assert isinstance(result.channel, WhatsappChannel)
    return owner, result.channel, result.inbox


async def _headers(db_session, user) -> dict[str, str]:
    headers, new_tokens = create_new_auth_token(
        user_tokens=user.tokens, uid=user.uid
    )
    user.tokens = new_tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


def _message_payload(wamid: str = "wamid.1") -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "b1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "contacts": [
                                {"profile": {"name": "Lucía"}, "wa_id": _CUSTOMER}
                            ],
                            "messages": [
                                {
                                    "from": _CUSTOMER,
                                    "id": wamid,
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": "Hola, quiero inscribirme"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _handover_change(new_owner_app_id: str, metadata: str = "") -> dict[str, Any]:
    control: dict[str, Any] = {
        "previous_owner_app_id": "222",
        "new_owner_app_id": new_owner_app_id,
    }
    if metadata:
        control["metadata"] = metadata
    return {
        "field": "messaging_handovers",
        "value": {
            "messaging_product": "whatsapp",
            "from": _CUSTOMER,
            "pass_thread_control": control,
        },
    }


def _handover_payload(new_owner_app_id: str, metadata: str = "") -> dict[str, Any]:
    control: dict[str, Any] = {
        "previous_owner_app_id": "222",
        "new_owner_app_id": new_owner_app_id,
    }
    if metadata:
        control["metadata"] = metadata
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "b1",
                "changes": [
                    {
                        "field": "messaging_handovers",
                        "value": {
                            "messaging_product": "whatsapp",
                            "from": _CUSTOMER,
                            "pass_thread_control": control,
                        },
                    }
                ],
            }
        ],
    }


async def _only_conversation(db_session, inbox) -> Conversation:
    rows = (
        await db_session.exec(
            select(Conversation).where(Conversation.inbox_id == inbox.id)
        )
    ).all()
    assert len(rows) == 1
    return rows[0]


async def _activities(db_session, conversation) -> list[str]:
    rows = (
        await db_session.exec(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.message_type == MESSAGE_TYPE_ACTIVITY,
            )
            .order_by(Message.id)
        )
    ).all()
    return [m.content or "" for m in rows]


# ---------------------------------------------------------------------------
# Inbound messages
# ---------------------------------------------------------------------------
async def test_inbound_message_on_business_agent_number_is_owned_by_the_ai(
    db_session,
):
    _, channel, inbox = await _seed(db_session)
    await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=_message_payload()
    )
    conversation = await _only_conversation(db_session, inbox)
    assert ba.thread_owner(conversation) == ba.OWNER_AI_AGENT
    # Nothing changed hands: no activity row.
    assert await _activities(db_session, conversation) == []


def _standby_payload(standby: dict[str, Any]) -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "b1",
                "changes": [
                    {
                        "field": "standby",
                        "value": {"messaging_product": "whatsapp", "standby": standby},
                    }
                ],
            }
        ],
    }


async def test_standby_shows_the_thread_the_ai_owns_without_answering(db_session):
    _, channel, inbox = await _seed(db_session)
    customer = _standby_payload(
        {
            "contacts": [{"profile": {"name": "Lucía"}, "wa_id": _CUSTOMER}],
            "messages": [
                {
                    "from": _CUSTOMER,
                    "id": "wamid.in",
                    "timestamp": "1700000000",
                    "type": "text",
                    "text": {"body": "Hola, quiero inscribirme"},
                }
            ],
        }
    )
    echo = _standby_payload(
        {
            "message_echoes": [
                {
                    "id": "wamid.out",
                    "timestamp": "1700000001",
                    "message": {
                        "messaging_product": "whatsapp",
                        "to": _CUSTOMER,
                        "type": "text",
                        "text": {"body": "¡Hola! ¿Qué curso te interesa?"},
                    },
                }
            ]
        }
    )
    with respx.mock(assert_all_called=False) as mock:
        graph = mock.route(host="graph.facebook.com")
        for payload in (customer, echo, echo):  # Meta can deliver twice.
            await process_cloud_webhook(
                db_session, channel=channel, inbox=inbox, payload=payload
            )

    conversation = await _only_conversation(db_session, inbox)
    assert ba.thread_owner(conversation) == ba.OWNER_AI_AGENT
    rows = (
        await db_session.exec(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.source_id.is_not(None),
            )
            .order_by(Message.id)
        )
    ).all()
    assert [(m.source_id, m.content) for m in rows] == [
        ("wamid.in", "Hola, quiero inscribirme"),
        ("wamid.out", "¡Hola! ¿Qué curso te interesa?"),
    ]
    assert rows[1].message_type == MESSAGE_TYPE_OUTGOING
    # The bot already answered: nothing goes out to Meta.
    assert graph.call_count == 0


async def test_standby_on_a_conversation_we_held_gives_it_back_to_the_ai(db_session):
    _, channel, inbox = await _seed(db_session)
    await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=_message_payload("wamid.a")
    )
    conversation = await _only_conversation(db_session, inbox)
    await ba._set_owner(
        db_session, conversation=conversation, owner=ba.OWNER_APP, activity=None
    )
    await process_cloud_webhook(
        db_session,
        channel=channel,
        inbox=inbox,
        payload=_standby_payload(
            {
                "contacts": [{"profile": {"name": "Lucía"}, "wa_id": _CUSTOMER}],
                "messages": [
                    {
                        "from": _CUSTOMER,
                        "id": "wamid.b",
                        "timestamp": "1700000000",
                        "type": "text",
                        "text": {"body": "Hola otra vez"},
                    }
                ],
            }
        ),
    )
    await db_session.refresh(conversation)
    assert ba.thread_owner(conversation) == ba.OWNER_AI_AGENT


@respx.mock
async def test_thread_control_retries_when_meta_fails_for_a_moment(db_session, monkeypatch):
    monkeypatch.setattr(ba, "_THREAD_CONTROL_RETRY_SECONDS", (0, 0))
    _, channel, _inbox = await _seed(db_session)
    route = respx.post(url__regex=r".*/thread_control").mock(
        side_effect=[
            httpx.Response(500, json={"error": {"message": "An unknown error has occurred."}}),
            httpx.Response(200, json={"messaging_product": "whatsapp"}),
        ]
    )
    assert await ba.request_thread_control(channel, to_phone=_CUSTOMER, action="release") is None
    assert route.call_count == 2


async def test_inbound_message_without_business_agent_has_no_owner(db_session):
    _, channel, inbox = await _seed(db_session, business_agent=False)
    await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=_message_payload()
    )
    conversation = await _only_conversation(db_session, inbox)
    assert ba.thread_owner(conversation) is None


# ---------------------------------------------------------------------------
# messaging_handovers webhook
# ---------------------------------------------------------------------------
async def test_handoff_to_our_app_moves_the_conversation_to_the_team(db_session):
    _, channel, inbox = await _seed(db_session, business_agent=False)
    await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=_message_payload()
    )
    conversation = await _only_conversation(db_session, inbox)
    await toggle_status(db_session, conversation=conversation, status="resolved")

    await process_cloud_webhook(
        db_session,
        channel=channel,
        inbox=inbox,
        payload=_handover_payload("111", metadata="Consulta por pagos"),
    )
    await db_session.refresh(conversation)
    assert ba.thread_owner(conversation) == ba.OWNER_APP
    # A handoff is a request for a person: it reopens the conversation.
    assert conversation.status == CONVERSATION_STATUS_OPEN
    # ...and runs the bot handoff: the customer is waiting for the team.
    assert conversation.waiting_since is not None
    assert any(
        "handed the conversation off to the team: Consulta por pagos" in a
        for a in await _activities(db_session, conversation)
    )
    # The first handover turns the Business Agent mode on for the number.
    await db_session.refresh(channel)
    assert ba.business_agent_enabled(channel)


def _role_handover_payload(event: str, new_owner_role: str) -> dict[str, Any]:
    """The documented WhatsApp shape of ``messaging_handovers``."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "b1",
                "changes": [
                    {
                        "field": "messaging_handovers",
                        "value": {
                            "messaging_product": "whatsapp",
                            "sender": {"phone_number": _CUSTOMER},
                            "recipient": {
                                "phone_number_id": "p1",
                                "display_phone_number": "59811111111",
                            },
                            "type": event,
                            "timestamp": "1794000000",
                            event: {
                                "previous_owner_role": "ai_agent",
                                "new_owner_role": new_owner_role,
                                "conversation_context": {
                                    "type": "summary",
                                    "summary": {"text": "Quiere hablar con una persona"},
                                },
                            },
                        },
                    }
                ],
            }
        ],
    }


async def test_documented_handoff_shape_moves_the_conversation_to_the_team(db_session):
    _, channel, inbox = await _seed(db_session)
    await process_cloud_webhook(
        db_session,
        channel=channel,
        inbox=inbox,
        payload=_role_handover_payload("control_passed", "escalation"),
    )
    conversation = await _only_conversation(db_session, inbox)
    assert ba.thread_owner(conversation) == ba.OWNER_APP
    assert any(
        "handed the conversation off to the team: Quiere hablar con una persona" in a
        for a in await _activities(db_session, conversation)
    )

    await process_cloud_webhook(
        db_session,
        channel=channel,
        inbox=inbox,
        payload=_role_handover_payload("control_passed", "ai_agent"),
    )
    await db_session.refresh(conversation)
    assert ba.thread_owner(conversation) == ba.OWNER_AI_AGENT


async def test_documented_handoff_for_another_number_is_skipped(db_session):
    _, channel, inbox = await _seed(db_session)
    payload = _role_handover_payload("control_passed", "escalation")
    payload["entry"][0]["changes"][0]["value"]["recipient"]["phone_number_id"] = "other"
    await process_cloud_webhook(db_session, channel=channel, inbox=inbox, payload=payload)
    rows = (
        await db_session.exec(select(Conversation).where(Conversation.inbox_id == inbox.id))
    ).all()
    assert rows == []


async def test_handoff_back_to_the_ai(db_session):
    _, channel, inbox = await _seed(db_session)
    await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=_handover_payload("111")
    )
    await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=_handover_payload("222")
    )
    conversation = await _only_conversation(db_session, inbox)
    assert ba.thread_owner(conversation) == ba.OWNER_AI_AGENT
    assert any(
        "answering the conversation again" in a
        for a in await _activities(db_session, conversation)
    )


async def test_unparseable_handover_is_dropped(db_session):
    _, channel, inbox = await _seed(db_session)
    payload = _handover_payload("111")
    payload["entry"][0]["changes"][0]["value"] = {"messaging_product": "whatsapp"}
    out = await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=payload
    )
    assert out == []
    rows = (
        await db_session.exec(
            select(Conversation).where(Conversation.inbox_id == inbox.id)
        )
    ).all()
    assert rows == []


# ---------------------------------------------------------------------------
# POST /conversations/:id/thread_control
# ---------------------------------------------------------------------------
@respx.mock
async def test_take_and_release_through_the_endpoint(client, db_session):
    owner, channel, inbox = await _seed(db_session)
    await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=_message_payload()
    )
    conversation = await _only_conversation(db_session, inbox)
    headers = await _headers(db_session, owner.user)
    route = respx.post(_THREAD_CONTROL).mock(
        return_value=httpx.Response(200, json={"messaging_product": "whatsapp"})
    )
    url = (
        f"/api/v1/accounts/{owner.account.id}/conversations/"
        f"{conversation.display_id}/thread_control"
    )

    resp = await client.post(url, json={"action": "take"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["additional_attributes"]["thread_control"]["owner"] == "app"

    resp = await client.post(url, json={"action": "release"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert (
        resp.json()["additional_attributes"]["thread_control"]["owner"]
        == "ai_agent"
    )
    assert b'"action":"take"' in route.calls[0].request.content.replace(b" ", b"")
    activities = await _activities(db_session, conversation)
    assert any("took over the conversation" in a for a in activities)
    assert any("returned the conversation" in a for a in activities)


@respx.mock
async def test_meta_refusal_keeps_the_owner(client, db_session):
    owner, channel, inbox = await _seed(db_session)
    await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=_message_payload()
    )
    conversation = await _only_conversation(db_session, inbox)
    headers = await _headers(db_session, owner.user)
    respx.post(_THREAD_CONTROL).mock(
        return_value=httpx.Response(
            403, json={"error": {"message": "Not the escalation partner"}}
        )
    )
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/conversations/"
        f"{conversation.display_id}/thread_control",
        json={"action": "take"},
        headers=headers,
    )
    assert resp.status_code == 502
    assert "Not the escalation partner" in resp.text
    await db_session.refresh(conversation)
    assert ba.thread_owner(conversation) == ba.OWNER_AI_AGENT


# ---------------------------------------------------------------------------
# Resolve and reply
# ---------------------------------------------------------------------------
async def test_resolve_queues_the_release_without_calling_meta(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    _, channel, inbox = await _seed(db_session)
    await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=_handover_payload("111")
    )
    conversation = await _only_conversation(db_session, inbox)
    queued: list[int] = []

    async def _capture(*, conversation_id: int) -> None:
        queued.append(conversation_id)

    import app.workers.business_agent as worker

    monkeypatch.setattr(worker, "enqueue_release_to_ai", _capture)
    with respx.mock(assert_all_called=False) as meta:
        route = meta.post(_THREAD_CONTROL)
        await toggle_status(db_session, conversation=conversation, status="resolved")
        assert not route.called
    assert queued == [conversation.id]


@respx.mock
async def test_release_job_returns_a_resolved_conversation_to_the_ai(db_session):
    _, channel, inbox = await _seed(db_session)
    await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=_handover_payload("111")
    )
    conversation = await _only_conversation(db_session, inbox)
    conversation.status = CONVERSATION_STATUS_RESOLVED
    db_session.add(conversation)
    await db_session.flush()
    route = respx.post(_THREAD_CONTROL).mock(
        return_value=httpx.Response(200, json={"messaging_product": "whatsapp"})
    )
    outcome = await ba.release_resolved_conversation(
        db_session, conversation_id=conversation.id
    )
    assert outcome == "released"
    assert route.called
    assert ba.thread_owner(conversation) == ba.OWNER_AI_AGENT


async def test_release_job_skips_reopened_and_opted_out_conversations(db_session):
    _, channel, inbox = await _seed(db_session)
    await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=_handover_payload("111")
    )
    conversation = await _only_conversation(db_session, inbox)
    # Reopened before the job ran.
    assert (
        await ba.release_resolved_conversation(
            db_session, conversation_id=conversation.id
        )
        == "not_resolved"
    )
    conversation.status = CONVERSATION_STATUS_RESOLVED
    db_session.add(conversation)
    channel.provider_config = {
        **channel.provider_config,
        ba.FLAG_RETURN_ON_RESOLVE: False,
    }
    db_session.add(channel)
    await db_session.flush()
    assert (
        await ba.release_resolved_conversation(
            db_session, conversation_id=conversation.id
        )
        == "return_on_resolve_off"
    )
    assert ba.thread_owner(conversation) == ba.OWNER_APP


@respx.mock
async def test_agent_reply_takes_the_conversation_before_sending(db_session):
    _, channel, inbox = await _seed(db_session)
    await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=_message_payload()
    )
    conversation = await _only_conversation(db_session, inbox)
    route = respx.post(_THREAD_CONTROL).mock(
        return_value=httpx.Response(200, json={"messaging_product": "whatsapp"})
    )
    await ba.take_over_before_reply(
        db_session,
        conversation=conversation,
        channel=channel,
        to_phone=_CUSTOMER,
        user_name="Agente Uno",
    )
    assert route.called
    assert ba.thread_owner(conversation) == ba.OWNER_APP
    assert any(
        "Agente Uno took over the conversation from Meta Business Agent by replying"
        in a
        for a in await _activities(db_session, conversation)
    )


@respx.mock
async def test_refused_take_before_reply_is_recorded(db_session):
    _, channel, inbox = await _seed(db_session)
    await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=_message_payload()
    )
    conversation = await _only_conversation(db_session, inbox)
    respx.post(_THREAD_CONTROL).mock(
        return_value=httpx.Response(
            403, json={"error": {"message": "Thread control is off"}}
        )
    )
    await ba.take_over_before_reply(
        db_session,
        conversation=conversation,
        channel=channel,
        to_phone=_CUSTOMER,
        user_name="Agente Uno",
    )
    assert ba.thread_owner(conversation) == ba.OWNER_AI_AGENT
    assert any(
        "Could not take the conversation from Meta Business Agent: Thread control is off"
        in a
        for a in await _activities(db_session, conversation)
    )


# ---------------------------------------------------------------------------
# Batched payloads
# ---------------------------------------------------------------------------
async def test_batch_skips_other_fields_and_other_numbers(db_session):
    _, channel, inbox = await _seed(db_session)
    message_change = _message_payload()["entry"][0]["changes"][0]
    other_number = _message_payload("wamid.other")["entry"][0]["changes"][0]
    other_number["value"]["metadata"] = {"phone_number_id": "someone-else"}
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "b1",
                "changes": [
                    {"field": "message_template_status_update", "value": {"event": "APPROVED"}},
                    other_number,
                    message_change,
                    _handover_change("111"),
                ],
            }
        ],
    }
    out = await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=payload
    )
    assert [m.source_id for m in out] == ["wamid.1"]
    conversation = await _only_conversation(db_session, inbox)
    assert ba.thread_owner(conversation) == ba.OWNER_APP


async def test_a_failing_change_does_not_sink_the_batch(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    _, channel, inbox = await _seed(db_session)

    async def _boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("handover exploded")

    monkeypatch.setattr(ba, "process_handover_value", _boom)
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "b1",
                "changes": [
                    _handover_change("111"),
                    _message_payload()["entry"][0]["changes"][0],
                ],
            }
        ],
    }
    out = await process_cloud_webhook(
        db_session, channel=channel, inbox=inbox, payload=payload
    )
    assert [m.source_id for m in out] == ["wamid.1"]
