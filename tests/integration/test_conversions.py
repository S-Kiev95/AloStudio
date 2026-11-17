"""Conversions API (F17): ad conversations that became leads or sales,
reported to Meta. Meta's Graph API is mocked with respx."""

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
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.closing import service as closing
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.service import ConversationBuilderParams, create_conversation
from app.domains.conversions import service as conversions
from app.domains.conversions.models import MAX_ATTEMPTS, ConversionEvent
from app.domains.crm import service as crm
from app.domains.inboxes.models import WHATSAPP_PROVIDER_CLOUD
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.main import app

pytestmark = pytest.mark.integration

GRAPH = r"https://graph\.facebook\.com/v[\d.]+/"


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


async def _conversation(db_session, account, inbox, name: str, wa_id: str, click: str | None):
    contact = Contact(account_id=account.id, name=name, phone_number=f"+{wa_id}")
    db_session.add(contact)
    await db_session.flush()
    contact_inbox = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox, source_id=wa_id
    ).perform()
    await db_session.refresh(contact_inbox, ["inbox"])
    conversation = await create_conversation(
        db_session, contact_inbox=contact_inbox, params=ConversationBuilderParams()
    )
    conversation.ad_click_id = click
    conversation.ad_source = "ad" if click else None
    db_session.add(conversation)
    await db_session.flush()
    return contact, conversation


@pytest.fixture
async def seeded(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@capi.example.com",
            account_name="Instituto",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
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
    contact, from_ad = await _conversation(
        db_session, owner.account, result.inbox, "Lucía Pereira", "59891234567", "ctwa.CLICK1"
    )
    _, organic = await _conversation(
        db_session, owner.account, result.inbox, "Pedro Gómez", "59891111111", None
    )
    return {
        "account": owner.account,
        "admin": owner.user,
        "inbox": result.inbox,
        "contact": contact,
        "from_ad": from_ad,
        "organic": organic,
        "base": f"/api/v1/accounts/{owner.account.id}/conversions",
    }


async def _turn_on(db_session, seeded, **rules) -> None:
    await conversions.save_settings(
        db_session,
        account_id=seeded["account"].id,
        enabled=True,
        currency="UYU",
        rules={**conversions.DEFAULT_RULES, **rules},
    )


async def _events(db_session, conversation_id: int) -> list[ConversionEvent]:
    rows = (
        await db_session.exec(
            select(ConversionEvent)
            .where(ConversionEvent.conversation_id == conversation_id)
            .order_by(ConversionEvent.id)  # type: ignore[arg-type]
        )
    ).all()
    return list(rows)


def _mock_meta(events_status: int = 200) -> respx.Route:
    respx.post(url__regex=GRAPH + r"b1/dataset(\?|$)").mock(
        return_value=httpx.Response(200, json={"id": "DS1"})
    )
    body = (
        {"events_received": 1}
        if events_status == 200
        else {"error": {"message": "Missing permission whatsapp_business_manage_events"}}
    )
    return respx.post(url__regex=GRAPH + r"DS1/events(\?|$)").mock(
        return_value=httpx.Response(events_status, json=body)
    )


async def test_settings_start_off_and_hold_up(client, db_session, seeded):
    admin_h = await _headers(db_session, seeded["admin"])
    shown = (await client.get(f"{seeded['base']}/settings", headers=admin_h)).json()
    assert shown["enabled"] is False
    assert shown["currency"] == "USD"
    assert shown["rules"]["opportunity_won"] == "Purchase"
    assert shown["inboxes"] == [
        {"inbox_id": seeded["inbox"].id, "name": "WhatsApp CTC", "dataset_id": None}
    ]

    url = f"{seeded['base']}/settings"
    bad_event = await client.put(
        url, json={"enabled": True, "rules": {"opportunity_won": "Sale"}}, headers=admin_h
    )
    assert bad_event.json()["code"] == "conversions.event"
    bad_currency = await client.put(url, json={"enabled": True, "currency": "pesos"}, headers=admin_h)
    assert bad_currency.json()["code"] == "conversions.currency"
    saved = await client.put(
        url,
        json={
            "enabled": True,
            "currency": "uyu",
            "rules": {
                "opportunity_created": None,
                "closing": {"Se inscribió": {"event": "Purchase", "value": 4500}},
            },
        },
        headers=admin_h,
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["currency"] == "UYU"
    assert body["rules"]["opportunity_created"] is None
    assert body["rules"]["closing"] == {"Se inscribió": {"event": "Purchase", "value": 4500.0}}


@respx.mock
async def test_connecting_a_number_keeps_its_dataset_or_says_why_not(client, db_session, seeded):
    respx.route(host="test").pass_through()
    admin_h = await _headers(db_session, seeded["admin"])
    url = f"{seeded['base']}/inboxes/{seeded['inbox'].id}/dataset"

    respx.post(url__regex=GRAPH + r"b1/dataset(\?|$)").mock(
        return_value=httpx.Response(
            400, json={"error": {"message": "Missing permission", "code": 200}}
        )
    )
    refused = await client.post(url, headers=admin_h)
    assert refused.status_code == 502
    assert refused.json()["code"] == "conversions.refused"
    assert refused.json()["message"] == "Missing permission"

    respx.post(url__regex=GRAPH + r"b1/dataset(\?|$)").mock(
        return_value=httpx.Response(200, json={"id": "DS1"})
    )
    connected = await client.post(url, headers=admin_h)
    assert connected.status_code == 200, connected.text
    assert connected.json()["inboxes"][0]["dataset_id"] == "DS1"


@respx.mock
async def test_a_mapped_closing_reason_is_sent_to_meta_once(db_session, seeded):
    sent = _mock_meta()
    await _turn_on(db_session, seeded, closing={"Se inscribió": {"event": "Purchase", "value": 4500}})
    await closing.save_settings(
        db_session,
        account_id=seeded["account"].id,
        enabled=True,
        required=False,
        categories=["Se inscribió", "Consulta respondida"],
    )
    for conversation in (seeded["from_ad"], seeded["organic"]):
        await closing.close(
            db_session,
            conversation=conversation,
            user_id=seeded["admin"].id,
            category="Se inscribió",
            note=None,
        )

    queued = await _events(db_session, seeded["from_ad"].id)
    assert [(e.event_name, e.value, e.currency, e.status) for e in queued] == [
        ("Purchase", Decimal("4500.00"), "UYU", "pending")
    ]
    assert await _events(db_session, seeded["organic"].id) == [], "not from an ad"

    assert await conversions.send_pending(db_session) == 1
    request = json.loads(sent.calls.last.request.content)
    assert request["partner_agent"] == "alostudio"
    (event,) = request["data"]
    assert event["event_name"] == "Purchase"
    assert event["action_source"] == "business_messaging"
    assert event["messaging_channel"] == "whatsapp"
    assert event["user_data"] == {"whatsapp_business_account_id": "b1", "ctwa_clid": "ctwa.CLICK1"}
    assert event["custom_data"] == {"currency": "UYU", "value": 4500.0}
    assert sent.calls.last.request.headers["Authorization"] == "Bearer EAAtoken"
    await db_session.refresh(queued[0])
    assert queued[0].status == "sent"

    # The same reason again: Meta does not deduplicate, so neither twice.
    assert (
        await conversions.record(
            db_session,
            conversation=seeded["from_ad"],
            event_name="Purchase",
            trigger="closing",
            detail="Se inscribió",
        )
        is None
    )
    assert len(await _events(db_session, seeded["from_ad"].id)) == 1


async def test_the_crm_reports_leads_qualified_and_won(db_session, seeded):
    await _turn_on(db_session, seeded)
    account_id = seeded["account"].id
    pipeline = (await crm.list_pipelines(db_session, account_id=account_id))[0]
    stages = {s.code: s for s in await crm.stages_for(db_session, [pipeline.id])}

    opportunity = await crm.save_opportunity(
        db_session,
        account_id=account_id,
        opportunity=None,
        payload={
            "title": "Curso de inglés",
            "contact_id": seeded["contact"].id,
            "value": 4500,
            "currency": "UYU",
        },
    )
    for code in ("qualified", "won"):
        await crm.save_opportunity(
            db_session,
            account_id=account_id,
            opportunity=opportunity,
            payload={"stage_id": stages[code].id},
        )

    queued = await _events(db_session, seeded["from_ad"].id)
    assert [(e.event_name, e.trigger, e.value, e.detail) for e in queued] == [
        ("LeadSubmitted", "opportunity_created", None, "Curso de inglés"),
        ("QualifiedLead", "opportunity_qualified", None, "Curso de inglés"),
        ("Purchase", "opportunity_won", Decimal("4500.00"), "Curso de inglés"),
    ]


@respx.mock
async def test_a_refusal_is_retried_and_then_given_up(db_session, seeded):
    _mock_meta(events_status=400)
    await _turn_on(db_session, seeded)
    event = await conversions.record(
        db_session,
        conversation=seeded["from_ad"],
        event_name="LeadSubmitted",
        trigger="opportunity_created",
        detail="Curso",
    )
    assert event is not None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        assert await conversions.send_pending(db_session) == 0
        await db_session.refresh(event)
        assert event.attempts == attempt
    assert event.status == "failed"
    assert event.error == "Missing permission whatsapp_business_manage_events"


async def test_off_queues_nothing_and_holds_what_was_queued(db_session, seeded):
    assert (
        await conversions.record(
            db_session,
            conversation=seeded["from_ad"],
            event_name="LeadSubmitted",
            trigger="opportunity_created",
            detail=None,
        )
        is None
    )
    await _turn_on(db_session, seeded)
    event = await conversions.record(
        db_session,
        conversation=seeded["from_ad"],
        event_name="LeadSubmitted",
        trigger="opportunity_created",
        detail=None,
    )
    await conversions.save_settings(
        db_session, account_id=seeded["account"].id, enabled=False, currency="UYU", rules=None
    )
    assert await conversions.send_pending(db_session) == 0
    await db_session.refresh(event)
    assert (event.status, event.attempts) == ("pending", 0)


async def test_the_log_lists_the_latest_events(client, db_session, seeded):
    await _turn_on(db_session, seeded)
    await conversions.record(
        db_session,
        conversation=seeded["from_ad"],
        event_name="Purchase",
        trigger="opportunity_won",
        detail="Curso de inglés",
        value=Decimal("4500"),
        currency="UYU",
    )
    admin_h = await _headers(db_session, seeded["admin"])
    listed = (await client.get(f"{seeded['base']}/events", headers=admin_h)).json()["payload"]
    assert [
        (e["conversation_id"], e["event_name"], e["value"], e["currency"], e["status"])
        for e in listed
    ] == [(seeded["from_ad"].display_id, "Purchase", 4500.0, "UYU", "pending")]
