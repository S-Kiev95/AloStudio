"""F5 + F11 — products from the Meta catalogue on WhatsApp: sending one or
several in a chat, a contact's order coming back (and opening an
opportunity), and the number's commerce settings. Graph mocked with respx."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import MESSAGE_TYPE_INCOMING, Message
from app.domains.conversations.service import ConversationBuilderParams, create_conversation
from app.domains.crm.models import CrmOpportunity
from app.domains.inboxes.models import WHATSAPP_PROVIDER_CLOUD, WhatsappChannel
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.integrations.models import IntegrationsHook
from app.domains.products.models import Product
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.whatsapp.incoming_cloud import process_cloud_webhook
from app.main import app

pytestmark = pytest.mark.integration

SEND_URL = "https://graph.facebook.com/v13.0/PNCAT/messages"
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


async def _seed(db_session, suffix: str, *, last_incoming_hours: float = 1):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@wacat.example.com",
            account_name=f"WACAT{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    account_id = owner.account.id
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WA",
            channel_type="whatsapp",
            channel_params={
                "phone_number": f"+5986{abs(hash(suffix)) % 10**7:07d}",
                "provider": WHATSAPP_PROVIDER_CLOUD,
                "provider_config": {
                    "api_key": "tok",
                    "phone_number_id": "PNCAT",
                    "business_account_id": "WABA-CAT",
                },
            },
        ),
    ).perform()
    db_session.add(
        IntegrationsHook(
            account_id=account_id,
            app_id="meta_catalog",
            hook_type=0,
            status=1,
            settings={"catalog_id": "777"},
            reference_id="777",
            access_token="cat-token",
        )
    )
    now = datetime.now(UTC)
    products = []
    for i, (name, price) in enumerate((("Excel", "1200"), ("Inglés", "900"), ("Borrador", "1"))):
        p = Product(
            account_id=account_id,
            name=name,
            description="Curso",
            price=Decimal(price),
            currency="UYU",
            url="https://ctc.example/c",
            image_url="https://ctc.example/c.png",
            meta_retailer_id=f"alo-{suffix}-{i}" if name != "Borrador" else None,
            meta_synced_at=now if name != "Borrador" else None,
        )
        db_session.add(p)
        products.append(p)
    contact = Contact(account_id=account_id, name="Ana Pérez", phone_number="+59899123456")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session, contact=contact, inbox=result.inbox, source_id="+59899123456"
    ).perform()
    conv = await create_conversation(
        db_session, contact_inbox=ci, params=ConversationBuilderParams()
    )
    db_session.add(
        Message(
            account_id=account_id,
            inbox_id=result.inbox.id,
            conversation_id=conv.id,
            message_type=MESSAGE_TYPE_INCOMING,
            content="hola",
            created_at=now - timedelta(hours=last_incoming_hours),
        )
    )
    await db_session.flush()
    headers, new_tokens = create_new_auth_token(user_tokens=owner.user.tokens, uid=owner.user.uid)
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    channel = result.channel
    assert isinstance(channel, WhatsappChannel)
    return owner, result.inbox, channel, conv, products, headers.as_response_headers()


def _send_url(owner, conv) -> str:
    return f"/api/v1/accounts/{owner.account.id}/conversations/{conv.display_id}/whatsapp/products"


async def test_lists_only_products_meta_accepted(client, db_session):
    owner, _, _, _, _, headers = await _seed(db_session, "-list")
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/whatsapp/catalog/products", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["catalog_id"] == "777"
    assert [p["name"] for p in body["products"]] == ["Excel", "Inglés"]


async def test_sends_one_product_or_a_list(client, db_session):
    owner, _, _, conv, products, headers = await _seed(db_session, "-send")
    excel, ingles, _ = products
    with respx.mock(assert_all_called=False) as mock:
        sent_ids = iter(["wamid.p1", "wamid.p2"])
        route = mock.post(SEND_URL).mock(
            side_effect=lambda _r: httpx.Response(
                200, json={"messages": [{"id": next(sent_ids)}]}
            )
        )
        one = await client.post(
            _send_url(owner, conv),
            json={"product_ids": [excel.id], "body": "Este te puede servir"},
            headers=headers,
        )
        assert one.status_code == 200, one.text
        sent = json.loads(route.calls.last.request.content)
        assert sent["type"] == "interactive"
        assert sent["interactive"] == {
            "type": "product",
            "action": {"catalog_id": "777", "product_retailer_id": excel.meta_retailer_id},
            "body": {"text": "Este te puede servir"},
        }

        many = await client.post(
            _send_url(owner, conv),
            json={"product_ids": [excel.id, ingles.id], "header": "Cursos de marzo"},
            headers=headers,
        )
        assert many.status_code == 200, many.text
        sent = json.loads(route.calls.last.request.content)["interactive"]
        assert sent["type"] == "product_list"
        assert sent["header"] == {"type": "text", "text": "Cursos de marzo"}
        assert [i["product_retailer_id"] for i in sent["action"]["sections"][0]["product_items"]] == [
            excel.meta_retailer_id,
            ingles.meta_retailer_id,
        ]
    msg = await db_session.get(Message, many.json()["id"])
    assert msg is not None
    assert "Excel — UYU 1.200" in (msg.content or "")
    assert msg.source_id == "wamid.p2"


async def test_refuses_unsynced_products_and_closed_window(client, db_session):
    owner, _, _, conv, products, headers = await _seed(db_session, "-refuse")
    draft = products[2]
    resp = await client.post(_send_url(owner, conv), json={"product_ids": [draft.id]}, headers=headers)
    assert resp.status_code == 422
    assert "catálogo" in resp.json()["message"]

    owner2, _, _, conv2, products2, headers2 = await _seed(
        db_session, "-closed", last_incoming_hours=30
    )
    resp = await client.post(
        _send_url(owner2, conv2), json={"product_ids": [products2[0].id]}, headers=headers2
    )
    assert resp.status_code == 422
    assert "24 h" in resp.json()["message"]


async def test_order_is_stored_and_opens_an_opportunity(db_session):
    _owner, inbox, channel, conv, products, _ = await _seed(db_session, "-order")
    excel = products[0]
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-CAT",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "PNCAT"},
                            "contacts": [{"profile": {"name": "Ana Pérez"}, "wa_id": "59899123456"}],
                            "messages": [
                                {
                                    "from": "59899123456",
                                    "id": "wamid.order1",
                                    "timestamp": "1763050000",
                                    "type": "order",
                                    "order": {
                                        "catalog_id": "777",
                                        "text": "¿Hay cupo?",
                                        "product_items": [
                                            {
                                                "product_retailer_id": excel.meta_retailer_id,
                                                "quantity": 2,
                                                "item_price": 1200,
                                                "currency": "UYU",
                                            }
                                        ],
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    await process_cloud_webhook(db_session, channel=channel, inbox=inbox, payload=payload)
    msg = (
        await db_session.exec(select(Message).where(Message.source_id == "wamid.order1"))
    ).first()
    assert msg is not None
    order = msg.content_attributes["whatsapp_order"]
    assert order["total"] == 2400
    assert order["items"][0]["product_id"] == excel.id
    assert "2 x Excel" in msg.content
    assert "¿Hay cupo?" in msg.content
    opportunity = await db_session.get(CrmOpportunity, order["opportunity_id"])
    assert opportunity is not None
    assert opportunity.product_id == excel.id
    assert float(opportunity.value or 0) == 2400
    assert opportunity.conversation_id == conv.id


async def test_commerce_settings_and_linking(client, db_session):
    owner, inbox, _, _, _, headers = await _seed(db_session, "-commerce")
    base = f"/api/v1/accounts/{owner.account.id}/inboxes/{inbox.id}/whatsapp/commerce"
    linked: list[dict[str, str]] = []
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{GRAPH}/PNCAT/whatsapp_commerce_settings").mock(
            return_value=httpx.Response(
                200, json={"data": [{"is_cart_enabled": True, "is_catalog_visible": False}]}
            )
        )
        mock.get(f"{GRAPH}/WABA-CAT/product_catalogs").mock(
            side_effect=lambda _r: httpx.Response(200, json={"data": linked})
        )
        update = mock.post(f"{GRAPH}/PNCAT/whatsapp_commerce_settings").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        def _link(request: httpx.Request) -> httpx.Response:
            linked.append({"id": json.loads(request.content)["catalog_id"]})
            return httpx.Response(200, json={"success": True})

        mock.post(f"{GRAPH}/WABA-CAT/product_catalogs").mock(side_effect=_link)

        status = (await client.get(base, headers=headers)).json()
        assert status["catalog_linked"] is False
        assert status["is_cart_enabled"] is True
        assert status["products_ready"] == 2

        resp = await client.post(f"{base}/link", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["catalog_linked"] is True

        resp = await client.post(base, json={"is_catalog_visible": True}, headers=headers)
        assert resp.status_code == 200
        assert update.calls.last.request.url.params["is_catalog_visible"] == "true"
