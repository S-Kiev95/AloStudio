"""Integration tests for campaign delivery analytics.

``GET /api/v1/accounts/{id}/campaigns/{display_id}/analytics`` reports the
conversations a campaign created plus the delivery-status breakdown of its
outgoing messages. Not a Chatwoot port — a value-add surface (see
``app/domains/campaigns/service.campaign_analytics``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.campaigns.builder import build_campaign_conversation
from app.domains.campaigns.models import CAMPAIGN_TYPE_ONE_OFF, Campaign
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    MESSAGE_STATUS_DELIVERED,
    MESSAGE_STATUS_FAILED,
    Message,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration


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


async def _seed_admin(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@ca.example.com",
            account_name=f"CA{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _seed_inbox(db_session, owner):
    return (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="API",
                channel_type="api",
                channel_params={"webhook_url": "https://x.example.com"},
            ),
        ).perform()
    ).inbox


async def _seed_campaign(db_session, owner, inbox, *, audience_size: int):
    campaign = Campaign(
        account_id=owner.account.id,
        inbox_id=inbox.id,
        display_id=1,
        title="Promo",
        message="¡Oferta especial!",
        campaign_type=CAMPAIGN_TYPE_ONE_OFF,
        audience=[
            {"type": "Contact", "id": i} for i in range(audience_size)
        ],
        enabled=True,
    )
    db_session.add(campaign)
    await db_session.flush()
    await db_session.refresh(campaign)
    return campaign


async def _campaign_conversation(db_session, campaign, inbox, owner, tag: str):
    contact = Contact(account_id=owner.account.id, name=f"C{tag}")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox,
        source_id=f"src-{tag}-{contact.id}",
    ).perform()
    return await build_campaign_conversation(
        db_session, campaign=campaign, contact_inbox=ci
    )


async def test_analytics_counts_conversations_and_delivery(client, db_session):
    owner, headers = await _seed_admin(db_session, "-an")
    inbox = await _seed_inbox(db_session, owner)
    campaign = await _seed_campaign(db_session, owner, inbox, audience_size=3)

    await _campaign_conversation(db_session, campaign, inbox, owner, "a")
    await _campaign_conversation(db_session, campaign, inbox, owner, "b")

    # Move the two campaign messages to distinct delivery states.
    msgs = list(
        (
            await db_session.exec(
                select(Message).where(Message.account_id == owner.account.id)
            )
        ).all()
    )
    campaign_msgs = [
        m
        for m in msgs
        if (m.additional_attributes or {}).get("campaign_id") == campaign.id
    ]
    assert len(campaign_msgs) == 2
    campaign_msgs[0].status = MESSAGE_STATUS_DELIVERED
    campaign_msgs[1].status = MESSAGE_STATUS_FAILED
    db_session.add_all(campaign_msgs)
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/campaigns/{campaign.display_id}/analytics",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["campaign_id"] == campaign.display_id
    assert body["audience_count"] == 3
    assert body["conversations_count"] == 2
    assert body["messages_count"] == 2
    assert body["delivery"] == {
        "sent": 0,
        "delivered": 1,
        "read": 0,
        "failed": 1,
    }


async def test_analytics_zero_for_fresh_campaign(client, db_session):
    owner, headers = await _seed_admin(db_session, "-zero")
    inbox = await _seed_inbox(db_session, owner)
    campaign = await _seed_campaign(db_session, owner, inbox, audience_size=5)

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/campaigns/{campaign.display_id}/analytics",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["audience_count"] == 5
    assert body["conversations_count"] == 0
    assert body["messages_count"] == 0
    assert body["delivery"] == {"sent": 0, "delivered": 0, "read": 0, "failed": 0}


async def test_analytics_404_for_unknown_campaign(client, db_session):
    owner, headers = await _seed_admin(db_session, "-nf")
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/campaigns/9999/analytics",
        headers=headers,
    )
    assert resp.status_code == 404
