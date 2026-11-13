"""F5 — managing WhatsApp templates: list with state, create, edit and
delete on Meta (mocked with respx), the status webhook, and who may do it."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.models import WHATSAPP_PROVIDER_CLOUD, WhatsappChannel
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.domains.whatsapp.incoming_cloud import process_cloud_webhook
from app.main import app

pytestmark = pytest.mark.integration

GRAPH = "https://graph.facebook.com"
APPROVED = {
    "id": "111",
    "name": "recordatorio",
    "language": "es",
    "status": "APPROVED",
    "category": "UTILITY",
    "components": [{"type": "BODY", "text": "Hola {{1}}, tu turno es el {{2}}."}],
}
REJECTED = {
    "id": "222",
    "name": "promo",
    "language": "es",
    "status": "REJECTED",
    "category": "MARKETING",
    "rejected_reason": "INVALID_FORMAT",
    "components": [{"type": "BODY", "text": "¡Oferta!"}],
}


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
            email=f"admin{suffix}@watpl.example.com",
            account_name=f"WATPL{suffix}",
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
                "phone_number": f"+5984{abs(hash(suffix)) % 10**7:07d}",
                "provider": WHATSAPP_PROVIDER_CLOUD,
                "provider_config": {
                    "api_key": "tok",
                    "phone_number_id": f"pn{suffix}",
                    "business_account_id": "WABA-1",
                },
            },
        ),
    ).perform()
    channel = result.channel
    assert isinstance(channel, WhatsappChannel)
    channel.message_templates = [dict(APPROVED), dict(REJECTED)]
    db_session.add(channel)
    await db_session.flush()
    return owner, result.inbox, channel


def _url(owner, inbox) -> str:
    return f"/api/v1/accounts/{owner.account.id}/inboxes/{inbox.id}/whatsapp/templates"


def _sync_route(mock: respx.MockRouter, templates: list[dict[str, Any]]) -> respx.Route:
    return mock.get(f"{GRAPH}/v14.0/WABA-1/message_templates").mock(
        return_value=httpx.Response(200, json={"data": templates})
    )


async def test_list_all_shows_state_and_reason(client, db_session):
    owner, inbox, _ = await _seed(db_session, "-list")
    headers = await _headers(db_session, owner.user)

    approved_only = (await client.get(_url(owner, inbox), headers=headers)).json()
    assert [t["name"] for t in approved_only["templates"]] == ["recordatorio"]

    every = (
        await client.get(_url(owner, inbox), params={"status": "all"}, headers=headers)
    ).json()["templates"]
    promo = next(t for t in every if t["name"] == "promo")
    assert promo["status"] == "REJECTED"
    assert promo["rejected_reason"] == "INVALID_FORMAT"
    assert promo["id"] == "222"


async def test_create_submits_to_meta_and_resyncs(client, db_session):
    owner, inbox, _ = await _seed(db_session, "-create")
    headers = await _headers(db_session, owner.user)
    new = {
        "name": "bienvenida",
        "category": "UTILITY",
        "language": "es",
        "components": [{"type": "BODY", "text": "Hola {{1}}", "example": {"body_text": [["Ana"]]}}],
    }
    with respx.mock(assert_all_called=False) as mock:
        create = mock.post(f"{GRAPH}/v23.0/WABA-1/message_templates").mock(
            return_value=httpx.Response(200, json={"id": "333", "status": "PENDING", "category": "UTILITY"})
        )
        _sync_route(mock, [APPROVED, REJECTED, {**new, "id": "333", "status": "PENDING"}])
        resp = await client.post(_url(owner, inbox), json=new, headers=headers)
    assert resp.status_code == 200, resp.text
    sent = json.loads(create.calls.last.request.content)
    assert sent["name"] == "bienvenida" and sent["category"] == "UTILITY"
    assert create.calls.last.request.headers["Authorization"] == "Bearer tok"
    names = {t["name"]: t["status"] for t in resp.json()["templates"]}
    assert names["bienvenida"] == "PENDING"


async def test_create_validates_before_calling_meta(client, db_session):
    owner, inbox, _ = await _seed(db_session, "-valid")
    headers = await _headers(db_session, owner.user)
    body = {"category": "UTILITY", "language": "es", "components": [{"type": "BODY", "text": "x"}]}
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(f"{GRAPH}/v23.0/WABA-1/message_templates")
        bad_name = await client.post(_url(owner, inbox), json={**body, "name": "Con Espacios"}, headers=headers)
        no_body = await client.post(
            _url(owner, inbox),
            json={**body, "name": "ok", "components": [{"type": "FOOTER", "text": "x"}]},
            headers=headers,
        )
        assert not route.called
    assert bad_name.status_code == 422
    assert no_body.status_code == 422


async def test_meta_rejection_message_reaches_the_user(client, db_session):
    owner, inbox, _ = await _seed(db_session, "-metaerr")
    headers = await _headers(db_session, owner.user)
    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{GRAPH}/v23.0/WABA-1/message_templates").mock(
            return_value=httpx.Response(
                400,
                json={"error": {"message": "Invalid parameter", "error_user_msg": "El nombre ya existe en ese idioma."}},
            )
        )
        resp = await client.post(
            _url(owner, inbox),
            json={"name": "recordatorio", "category": "UTILITY", "language": "es",
                  "components": [{"type": "BODY", "text": "x"}]},
            headers=headers,
        )
    assert resp.status_code == 422
    assert "ya existe" in resp.json()["message"]


async def test_edit_and_delete(client, db_session):
    owner, inbox, channel = await _seed(db_session, "-edit")
    headers = await _headers(db_session, owner.user)
    with respx.mock(assert_all_called=False) as mock:
        edit = mock.post(f"{GRAPH}/v23.0/222").mock(return_value=httpx.Response(200, json={"success": True}))
        _sync_route(mock, [APPROVED, {**REJECTED, "status": "PENDING", "rejected_reason": None}])
        resp = await client.post(
            f"{_url(owner, inbox)}/222",
            json={"components": [{"type": "BODY", "text": "Oferta de la semana"}]},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert json.loads(edit.calls.last.request.content)["components"][0]["text"] == "Oferta de la semana"

        delete = mock.delete(f"{GRAPH}/v23.0/WABA-1/message_templates").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        resp = await client.delete(f"{_url(owner, inbox)}/222", headers=headers)
    assert resp.status_code == 200, resp.text
    assert delete.calls.last.request.url.params["name"] == "promo"
    assert delete.calls.last.request.url.params["hsm_id"] == "222"
    await db_session.refresh(channel)
    assert [t["name"] for t in channel.message_templates] == ["recordatorio"]

    # An id the channel doesn't know (another account's WABA) is a 404.
    resp = await client.delete(f"{_url(owner, inbox)}/999", headers=headers)
    assert resp.status_code == 404


async def test_agents_can_not_manage_templates(client, db_session):
    owner, inbox, _ = await _seed(db_session, "-agent")
    agent = (
        await AccountBuilder(
            db_session,
            AccountBuilderParams(
                email="agente-tpl@watpl.example.com",
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
    resp = await client.delete(f"{_url(owner, inbox)}/222", headers=headers)
    assert resp.status_code in (401, 403)


async def test_status_webhook_updates_the_cached_template(db_session):
    _owner, inbox, channel = await _seed(db_session, "-hook")
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-1",
                "changes": [
                    {
                        "field": "message_template_status_update",
                        "value": {
                            "event": "REJECTED",
                            "message_template_id": 111,
                            "message_template_name": "recordatorio",
                            "message_template_language": "es",
                            "reason": "INCORRECT_CATEGORY",
                        },
                    },
                    {
                        "field": "template_category_update",
                        "value": {
                            "message_template_id": 222,
                            "previous_category": "MARKETING",
                            "new_category": "UTILITY",
                        },
                    },
                ],
            }
        ],
    }
    await process_cloud_webhook(db_session, channel=channel, inbox=inbox, payload=payload)
    await db_session.refresh(channel)
    by_id = {t["id"]: t for t in channel.message_templates}
    assert by_id["111"]["status"] == "REJECTED"
    assert by_id["111"]["rejected_reason"] == "INCORRECT_CATEGORY"
    assert by_id["222"]["category"] == "UTILITY"
