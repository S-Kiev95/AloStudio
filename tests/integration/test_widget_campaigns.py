"""Integration tests for the widget campaign surface
(``GET /api/v1/widget/campaigns`` + ``POST /api/v1/widget/events``).

Anchors:
  reference/chatwoot/app/controllers/api/v1/widget/campaigns_controller.rb
  reference/chatwoot/app/listeners/campaign_listener.rb
  reference/chatwoot/app/builders/campaigns/campaign_conversation_builder.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.campaigns.models import (
    CAMPAIGN_STATUS_ACTIVE,
    CAMPAIGN_TYPE_ONE_OFF,
    CAMPAIGN_TYPE_ONGOING,
    Campaign,
)
from app.domains.conversations.models import (
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
)
from app.domains.inboxes.models import WebWidget
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.main import app

pytestmark = pytest.mark.integration

ONGOING_MESSAGE = "¡Hola! ¿Necesitás ayuda con algo?"


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


async def _seed_widget(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@camp-w.example.com",
            account_name="CampW",
            user_full_name="CampW Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Widget",
            channel_type="web_widget",
            channel_params={"website_url": "https://example.com"},
        ),
    ).perform()
    web_widget = result.channel
    assert isinstance(web_widget, WebWidget)
    return owner, result.inbox, web_widget


def _campaign(owner, inbox, **overrides) -> Campaign:
    base = dict(
        display_id=1,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        title="Ongoing",
        message=ONGOING_MESSAGE,
        campaign_type=CAMPAIGN_TYPE_ONGOING,
        campaign_status=CAMPAIGN_STATUS_ACTIVE,
        enabled=True,
        trigger_rules={"url_path": "/pricing"},
    )
    base.update(overrides)
    return Campaign(**base)


async def _bootstrap_widget(client, ww: WebWidget) -> str:
    resp = await client.post(
        f"/api/v1/widget/config?website_token={ww.website_token}"
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["auth_token"]


async def test_campaigns_index_lists_only_enabled_ongoing(client, db_session):
    owner, inbox, ww = await _seed_widget(db_session)
    db_session.add(_campaign(owner, inbox, display_id=1))  # listed
    db_session.add(
        _campaign(owner, inbox, display_id=2, campaign_type=CAMPAIGN_TYPE_ONE_OFF)
    )  # one_off — excluded
    db_session.add(
        _campaign(owner, inbox, display_id=3, enabled=False)
    )  # disabled — excluded
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/widget/campaigns?website_token={ww.website_token}"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [c["id"] for c in body] == [1]
    assert body[0]["message"] == ONGOING_MESSAGE
    assert body[0]["trigger_rules"] == {"url_path": "/pricing"}


async def test_campaign_triggered_creates_conversation(client, db_session):
    owner, inbox, ww = await _seed_widget(db_session)
    campaign = _campaign(owner, inbox, display_id=1)
    db_session.add(campaign)
    await db_session.flush()

    token = await _bootstrap_widget(client, ww)

    resp = await client.post(
        f"/api/v1/widget/events?website_token={ww.website_token}",
        headers={"X-Auth-Token": token},
        json={
            "name": "campaign.triggered",
            "event_info": {
                "campaign_id": 1,
                "custom_attributes": {"plan": "pro"},
                "referer_url": "https://example.com/pricing",
            },
        },
    )
    assert resp.status_code == 200, resp.text

    convs = list(
        (
            await db_session.exec(
                select(Conversation).where(
                    Conversation.campaign_id == campaign.id
                )
            )
        ).all()
    )
    assert len(convs) == 1
    msgs = list(
        (
            await db_session.exec(
                select(Message).where(Message.conversation_id == convs[0].id)
            )
        ).all()
    )
    assert any(
        m.content == ONGOING_MESSAGE and m.message_type == MESSAGE_TYPE_OUTGOING
        for m in msgs
    )

    # Re-trigger: idempotent — the visitor already has a conversation.
    resp = await client.post(
        f"/api/v1/widget/events?website_token={ww.website_token}",
        headers={"X-Auth-Token": token},
        json={"name": "campaign.triggered", "event_info": {"campaign_id": 1}},
    )
    assert resp.status_code == 200, resp.text
    convs = list(
        (
            await db_session.exec(
                select(Conversation).where(
                    Conversation.campaign_id == campaign.id
                )
            )
        ).all()
    )
    assert len(convs) == 1
