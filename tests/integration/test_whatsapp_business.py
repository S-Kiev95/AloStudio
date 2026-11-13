"""F5 — the WhatsApp number on Meta: its state, the business profile and
QR codes (Graph mocked with respx), and who may change them."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.models import WHATSAPP_PROVIDER_CLOUD
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
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


async def _headers(db_session, user) -> dict[str, str]:
    headers, new_tokens = create_new_auth_token(user_tokens=user.tokens, uid=user.uid)
    user.tokens = new_tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@wabiz.example.com",
            account_name=f"WABIZ{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WA",
            channel_type="whatsapp",
            channel_params={
                "phone_number": f"+5985{abs(hash(suffix)) % 10**7:07d}",
                "provider": WHATSAPP_PROVIDER_CLOUD,
                "provider_config": {
                    "api_key": "tok",
                    "phone_number_id": "PN1",
                    "business_account_id": "WABA-1",
                },
            },
        ),
    ).perform()
    base = f"/api/v1/accounts/{owner.account.id}/inboxes/{result.inbox.id}/whatsapp"
    return owner, base


async def test_phone_status(client, db_session):
    owner, base = await _seed(db_session, "-phone")
    headers = await _headers(db_session, owner.user)
    with respx.mock(assert_all_called=False) as mock:

        def answer(request: httpx.Request) -> httpx.Response:
            fields = request.url.params["fields"]
            if fields == "messaging_limit_tier":
                return httpx.Response(200, json={"messaging_limit_tier": "TIER_1K"})
            if fields.startswith("whatsapp_business_manager"):
                return httpx.Response(400, json={"error": {"message": "unknown field"}})
            return httpx.Response(
                200,
                json={
                    "display_phone_number": "+598 99 000 000",
                    "verified_name": "CTC Salto",
                    "quality_rating": "GREEN",
                    "name_status": "APPROVED",
                    "status": "CONNECTED",
                    "throughput": {"level": "STANDARD"},
                },
            )

        mock.get(f"{GRAPH}/PN1").mock(side_effect=answer)
        resp = await client.get(f"{base}/phone", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verified_name"] == "CTC Salto"
    assert body["quality_rating"] == "GREEN"
    assert body["messaging_limit"] == "TIER_1K"
    assert body["throughput"] == "STANDARD"


async def test_profile_read_and_update(client, db_session):
    owner, base = await _seed(db_session, "-profile")
    headers = await _headers(db_session, owner.user)
    profile = {
        "about": "Cursos",
        "description": "Centro de formación",
        "websites": ["https://ctc.edu.uy"],
        "vertical": "EDU",
    }
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{GRAPH}/PN1/whatsapp_business_profile").mock(
            return_value=httpx.Response(200, json={"data": [profile]})
        )
        update = mock.post(f"{GRAPH}/PN1/whatsapp_business_profile").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        got = await client.get(f"{base}/profile", headers=headers)
        assert got.json()["about"] == "Cursos"

        resp = await client.post(
            f"{base}/profile",
            json={"about": "Cursos y talleres", "websites": ["https://ctc.edu.uy"]},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        sent = json.loads(update.calls.last.request.content)
        assert sent == {
            "messaging_product": "whatsapp",
            "about": "Cursos y talleres",
            "websites": ["https://ctc.edu.uy"],
        }

        too_long = await client.post(f"{base}/profile", json={"about": "x" * 200}, headers=headers)
        bad_site = await client.post(
            f"{base}/profile", json={"websites": ["ctc.edu.uy"]}, headers=headers
        )
    assert too_long.status_code == 422
    assert bad_site.status_code == 422


async def test_qr_codes(client, db_session):
    owner, base = await _seed(db_session, "-qr")
    headers = await _headers(db_session, owner.user)
    qr = {
        "code": "ABC",
        "prefilled_message": "Hola, quiero info",
        "deep_link_url": "https://wa.me/message/ABC",
        "qr_image_url": "https://scontent.example/qr.png",
    }
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{GRAPH}/PN1/message_qrdls").mock(
            return_value=httpx.Response(200, json={"data": [qr]})
        )
        create = mock.post(f"{GRAPH}/PN1/message_qrdls").mock(
            return_value=httpx.Response(200, json={"code": "ABC"})
        )
        delete = mock.delete(f"{GRAPH}/PN1/message_qrdls/ABC").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        resp = await client.post(
            f"{base}/qr", json={"prefilled_message": "Hola, quiero info"}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["qr_codes"][0]["deep_link_url"] == "https://wa.me/message/ABC"
        params = create.calls.last.request.url.params
        assert params["prefilled_message"] == "Hola, quiero info"
        assert params["generate_qr_image"] == "PNG"

        empty = await client.post(f"{base}/qr", json={"prefilled_message": " "}, headers=headers)
        assert empty.status_code == 422

        resp = await client.delete(f"{base}/qr/ABC", headers=headers)
        assert resp.status_code == 200
        assert delete.called


async def test_agents_read_but_do_not_change(client, db_session):
    owner, base = await _seed(db_session, "-agent")
    agent = (
        await AccountBuilder(
            db_session,
            AccountBuilderParams(
                email="agente-biz@wabiz.example.com",
                account_name="Otra",
                user_full_name="Agente",
                user_password="Password123!",
                confirmed=True,
            ),
        ).perform()
    ).user
    db_session.add(AccountUser(account_id=owner.account.id, user_id=agent.id, role=ACCOUNT_USER_ROLE_AGENT))
    await db_session.flush()
    headers = await _headers(db_session, agent)
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{GRAPH}/PN1/message_qrdls").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        assert (await client.get(f"{base}/qr", headers=headers)).status_code == 200
        resp = await client.post(f"{base}/qr", json={"prefilled_message": "hola"}, headers=headers)
    assert resp.status_code in (401, 403)
