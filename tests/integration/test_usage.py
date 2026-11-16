"""F6 — spend per account: AI calls priced from their tokens, WhatsApp
pricing kept per message from the status webhook, Meta's own cost pulled
from pricing_analytics, and the month's summary (also per campaign)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core import llm
from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.campaigns.models import CAMPAIGN_TYPE_ONE_OFF, Campaign
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import MESSAGE_TYPE_OUTGOING, Message
from app.domains.conversations.service import ConversationBuilderParams, create_conversation
from app.domains.inboxes.models import WHATSAPP_PROVIDER_CLOUD, WhatsappChannel
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.usage.ai import ai_usage, cost_of
from app.domains.usage.models import KIND_AI, KIND_WHATSAPP, UsageRecord
from app.domains.whatsapp.incoming_cloud import process_cloud_webhook
from app.main import app

pytestmark = pytest.mark.integration

GRAPH = "https://graph.facebook.com/v23.0"


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


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@usage.example.com",
            account_name=f"USAGE{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WA Ventas",
            channel_type="whatsapp",
            channel_params={
                "phone_number": "+59899000111",
                "provider": WHATSAPP_PROVIDER_CLOUD,
                "provider_config": {
                    "api_key": "tok",
                    "phone_number_id": "PNUSE",
                    "business_account_id": "WABA-USE",
                },
            },
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(user_tokens=owner.user.tokens, uid=owner.user.uid)
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    channel = result.channel
    assert isinstance(channel, WhatsappChannel)
    return owner, result.inbox, channel, headers.as_response_headers()


def test_ai_cost_from_tokens():
    # 800 fresh + 200 cached input, 500 output on gpt-5.4-mini.
    assert cost_of("gpt-5.4-mini", input_tokens=1000, cached_tokens=200, output_tokens=500) == (
        Decimal("0.002865")
    )
    assert cost_of("gpt-4o-2024-08-06", input_tokens=1_000_000, cached_tokens=0, output_tokens=0) == (
        Decimal("2.500000")
    )
    assert cost_of("modelo-raro", input_tokens=10, cached_tokens=0, output_tokens=10) is None


async def test_ai_calls_are_recorded_inside_a_scope_only(db_session):
    owner, _, _, _ = await _seed(db_session, "-ai")
    body = {
        "model": "gpt-5.4-mini",
        "choices": [{"message": {"role": "assistant", "content": "hola"}}],
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 200},
        },
    }
    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json=body)
        )
        await llm.chat_completion(messages=[{"role": "user", "content": "x"}])
        with ai_usage(db_session, owner.account.id, "agent"):
            await llm.chat_completion(messages=[{"role": "user", "content": "x"}])
    await db_session.flush()
    rows = (
        await db_session.exec(
            select(UsageRecord).where(
                UsageRecord.account_id == owner.account.id, UsageRecord.kind == KIND_AI
            )
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].category == "agent"
    assert rows[0].cost == Decimal("0.002865")


async def test_status_pricing_is_kept_once_per_message(db_session):
    owner, inbox, channel, _ = await _seed(db_session, "-status")
    contact = Contact(account_id=owner.account.id, name="Ana", phone_number="+59899123000")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox, source_id="+59899123000"
    ).perform()
    conv = await create_conversation(db_session, contact_inbox=ci, params=ConversationBuilderParams())
    campaign = Campaign(
        display_id=1,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        title="Marzo",
        message="Hola",
        campaign_type=CAMPAIGN_TYPE_ONE_OFF,
    )
    db_session.add(campaign)
    await db_session.flush()
    db_session.add(
        Message(
            account_id=owner.account.id,
            inbox_id=inbox.id,
            conversation_id=conv.id,
            message_type=MESSAGE_TYPE_OUTGOING,
            content="Hola",
            source_id="wamid.cost1",
            additional_attributes={"campaign_id": campaign.id},
        )
    )
    await db_session.flush()

    def payload(status: str) -> dict:
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WABA-USE",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "PNUSE"},
                                "statuses": [
                                    {
                                        "id": "wamid.cost1",
                                        "status": status,
                                        "timestamp": "1763100000",
                                        "recipient_id": "59899123000",
                                        "pricing": {
                                            "billable": True,
                                            "pricing_model": "PMP",
                                            "category": "marketing",
                                            "type": "regular",
                                        },
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }

    await process_cloud_webhook(db_session, channel=channel, inbox=inbox, payload=payload("sent"))
    await process_cloud_webhook(db_session, channel=channel, inbox=inbox, payload=payload("delivered"))
    rows = (
        await db_session.exec(
            select(UsageRecord).where(
                UsageRecord.account_id == owner.account.id, UsageRecord.kind == KIND_WHATSAPP
            )
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].category == "marketing"
    assert rows[0].billable is True
    assert rows[0].campaign_id == campaign.id
    assert rows[0].inbox_id == inbox.id


async def test_month_summary_with_meta_costs_and_campaigns(client, db_session):
    owner, inbox, _, headers = await _seed(db_session, "-summary")
    campaign = Campaign(
        display_id=7,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        title="Inscripciones",
        message="Hola",
        campaign_type=CAMPAIGN_TYPE_ONE_OFF,
    )
    db_session.add(campaign)
    await db_session.flush()
    from datetime import UTC, datetime

    for i in range(3):
        db_session.add(
            UsageRecord(
                account_id=owner.account.id,
                kind=KIND_WHATSAPP,
                occurred_at=datetime(2026, 11, 5, tzinfo=UTC),
                inbox_id=inbox.id,
                campaign_id=campaign.id,
                category="marketing",
                pricing_type="regular",
                billable=True,
                source_id=f"wamid.sum{i}",
            )
        )
    with ai_usage(db_session, owner.account.id, "help_center"):
        from app.domains.usage.ai import record_ai_call

        record_ai_call("text-embedding-3-small", {"prompt_tokens": 1_000_000})
    await db_session.flush()

    analytics = {
        "currency": "USD",
        "pricing_analytics": {
            "data": [
                {
                    "data_points": [
                        {
                            "start": 1793836800,  # 2026-11-05 UTC
                            "end": 1793923200,
                            "country": "UY",
                            "pricing_type": "REGULAR",
                            "pricing_category": "MARKETING",
                            "volume": 10,
                            "cost": 0.8,
                        },
                        {
                            "start": 1793836800,
                            "end": 1793923200,
                            "country": "UY",
                            "pricing_type": "FREE_CUSTOMER_SERVICE",
                            "pricing_category": "SERVICE",
                            "volume": 40,
                            "cost": 0,
                        },
                    ]
                }
            ]
        },
    }
    base = f"/api/v1/accounts/{owner.account.id}/usage"
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(f"{GRAPH}/WABA-USE").mock(return_value=httpx.Response(200, json=analytics))
        resp = await client.post(f"{base}/whatsapp/sync", params={"month": "2026-11"}, headers=headers)
        assert resp.status_code == 200, resp.text
        fields = route.calls.last.request.url.params["fields"]
        assert "pricing_analytics" in fields and "59899000111" in fields
        # Syncing again doesn't double the figures.
        await client.post(f"{base}/whatsapp/sync", params={"month": "2026-11"}, headers=headers)

    body = (await client.get(base, params={"month": "2026-11"}, headers=headers)).json()
    wa = body["whatsapp"]
    assert wa["currency"] == "USD"
    assert wa["total_cost"] == 0.8
    assert wa["messages"] == 50
    assert wa["billable_messages"] == 10
    assert wa["by_inbox"][0]["name"] == "WA Ventas"
    assert wa["by_category"][0] == {"category": "MARKETING", "volume": 10, "cost": 0.8}
    # 3 marketing messages at 0.08 each (Meta's average for the month).
    assert body["campaigns"] == [
        {
            "campaign_id": 7,
            "title": "Inscripciones",
            "inbox_id": inbox.id,
            "messages": 3,
            "billable_messages": 3,
            "estimated_cost": 0.24,
            "complete": True,
        }
    ]
    assert body["ai"]["total_cost"] == 0.02
    assert body["ai"]["items"][0]["purpose"] == "help_center"

    bad = await client.get(base, params={"month": "noviembre"}, headers=headers)
    assert bad.status_code == 422


async def _spend_whatsapp(db_session, owner, inbox, cost: str) -> None:
    from datetime import UTC, datetime

    from app.domains.usage.models import WhatsappCostDay

    db_session.add(
        WhatsappCostDay(
            account_id=owner.account.id,
            inbox_id=inbox.id,
            day=datetime.now(UTC).date(),
            pricing_category="MARKETING",
            pricing_type="REGULAR",
            country="UY",
            volume=100,
            cost=Decimal(cost),
            currency="USD",
            synced_at=datetime.now(UTC),
        )
    )
    await db_session.flush()


async def test_limits_endpoint_and_template_stops_at_the_cap(client, db_session):
    owner, inbox, channel, headers = await _seed(db_session, "-cap")
    base = f"/api/v1/accounts/{owner.account.id}/usage/limits"
    await _spend_whatsapp(db_session, owner, inbox, "9.50")

    resp = await client.put(f"{base}/whatsapp", json={"monthly_limit": 10}, headers=headers)
    assert resp.status_code == 200, resp.text
    wa = next(x for x in resp.json()["limits"] if x["kind"] == "whatsapp")
    assert wa == {
        "kind": "whatsapp",
        "monthly_limit": 10.0,
        "spent": 9.5,
        "percent": 95.0,
        "reached": False,
    }
    assert (await client.put(f"{base}/sms", json={"monthly_limit": 1}, headers=headers)).status_code == 404
    assert (await client.put(f"{base}/ai", json={"monthly_limit": -1}, headers=headers)).status_code == 422

    # Lower the cap under what was spent: the next template doesn't go out.
    await client.put(f"{base}/whatsapp", json={"monthly_limit": 5}, headers=headers)
    channel.message_templates = [
        {
            "name": "promo",
            "language": "es",
            "status": "APPROVED",
            "category": "MARKETING",
            "components": [{"type": "BODY", "text": "Hola"}],
        }
    ]
    db_session.add(channel)
    contact = Contact(account_id=owner.account.id, name="Ana", phone_number="+59899555000")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=inbox, source_id="+59899555000"
    ).perform()
    conv = await create_conversation(db_session, contact_inbox=ci, params=ConversationBuilderParams())
    from app.domains.conversations.models import MESSAGE_STATUS_FAILED
    from app.domains.conversations.service import MessageBuilderParams, create_message

    with respx.mock(assert_all_called=False) as mock:
        send = mock.post(url__regex=r"https://graph\.facebook\.com/.*/messages").mock(
            return_value=httpx.Response(200, json={"messages": [{"id": "wamid.x"}]})
        )
        msg = await create_message(
            db_session,
            conversation=conv,
            params=MessageBuilderParams(
                content="Hola",
                message_type="outgoing",
                template_params={"name": "promo", "language": "es", "processed_params": {}},
            ),
            user_id=owner.user.id,
        )
    assert not send.called
    assert msg.status == MESSAGE_STATUS_FAILED
    assert "tope mensual" in msg.content_attributes["external_error"]


async def test_ai_stops_at_the_cap(db_session):
    from app.domains.usage.ai import record_ai_call
    from app.domains.usage.limits import set_limit

    owner, _, _, _ = await _seed(db_session, "-aicap")
    with ai_usage(db_session, owner.account.id, "agent"):
        record_ai_call("gpt-4o", {"prompt_tokens": 1_000_000})  # USD 2.50
    await db_session.flush()
    await set_limit(db_session, owner.account.id, "ai", 2)
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post("https://api.openai.com/v1/chat/completions")
        with ai_usage(db_session, owner.account.id, "agent"), pytest.raises(llm.LlmError):
            await llm.chat_completion(messages=[{"role": "user", "content": "x"}])
        assert not route.called


async def test_admins_are_told_once_per_level(db_session):
    from app.domains.notifications.models import NOTIFICATION_TYPE_USAGE_LIMIT, Notification
    from app.domains.usage.limits import notify_limits, set_limit

    owner, inbox, _, _ = await _seed(db_session, "-alert")
    await set_limit(db_session, owner.account.id, "whatsapp", 10)
    await _spend_whatsapp(db_session, owner, inbox, "8.20")
    first = await notify_limits(db_session)
    again = await notify_limits(db_session)
    rows = (
        await db_session.exec(
            select(Notification).where(
                Notification.account_id == owner.account.id,
                Notification.notification_type == NOTIFICATION_TYPE_USAGE_LIMIT,
            )
        )
    ).all()
    assert len(first) == 1
    assert again == []
    assert rows[0].meta["level"] == 80
