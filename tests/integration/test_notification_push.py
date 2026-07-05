"""Integration tests for web-push notifications.

  * ``/api/v1/notification_subscriptions`` — vapid_key / subscribe / unsubscribe.
  * ``send_notification_push`` — honours the recipient's push preference,
    encrypts + POSTs (mocked) to each subscription, prunes dead endpoints.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.notifications.models import (
    NOTIFICATION_TYPE_CONVERSATION_ASSIGNMENT,
    NotificationSetting,
    NotificationSubscription,
)
from app.domains.notifications.push import send_notification_push
from app.domains.notifications.service import create_notification
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


async def _authed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"me{suffix}@push.example.com",
            account_name=f"Push{suffix}",
            user_full_name=f"Me{suffix}",
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


_SUB = {
    "endpoint": "https://push.example.com/ep/abc",
    "keys": {"p256dh": "BPk...", "auth": "abc"},
}


async def test_vapid_key_endpoint(client, db_session):
    _, headers = await _authed(db_session, "-vk")
    resp = await client.get(
        "/api/v1/notification_subscriptions/vapid_key", headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "public_key" in body and "enabled" in body


async def test_subscribe_then_unsubscribe(client, db_session):
    owner, headers = await _authed(db_session, "-sub")
    resp = await client.post(
        "/api/v1/notification_subscriptions",
        json={"notification_subscription": {"subscription_attributes": _SUB}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["subscription_attributes"]["endpoint"] == _SUB["endpoint"]

    rows = list(
        (
            await db_session.exec(
                select(NotificationSubscription).where(
                    NotificationSubscription.user_id == owner.user.id
                )
            )
        ).all()
    )
    assert len(rows) == 1 and rows[0].identifier == _SUB["endpoint"]

    # Re-subscribing the same endpoint upserts (no duplicate row).
    await client.post(
        "/api/v1/notification_subscriptions",
        json={"notification_subscription": {"subscription_attributes": _SUB}},
        headers=headers,
    )
    again = list(
        (
            await db_session.exec(
                select(NotificationSubscription).where(
                    NotificationSubscription.user_id == owner.user.id
                )
            )
        ).all()
    )
    assert len(again) == 1

    dele = await client.request(
        "DELETE",
        "/api/v1/notification_subscriptions",
        json={"endpoint": _SUB["endpoint"]},
        headers=headers,
    )
    assert dele.status_code == 200
    remaining = list(
        (
            await db_session.exec(
                select(NotificationSubscription).where(
                    NotificationSubscription.user_id == owner.user.id
                )
            )
        ).all()
    )
    assert remaining == []


async def test_push_sends_when_opted_in_and_prunes_dead(
    client, db_session, monkeypatch
):
    owner, _ = await _authed(db_session, "-send")
    aid, uid = owner.account.id, owner.user.id

    db_session.add(
        NotificationSetting(
            account_id=aid,
            user_id=uid,
            push_subscriptions=["conversation_assignment"],
        )
    )
    db_session.add(
        NotificationSubscription(
            user_id=uid,
            identifier=_SUB["endpoint"],
            subscription_attributes=_SUB,
        )
    )
    await db_session.flush()
    notification = await create_notification(
        db_session,
        account_id=aid,
        user_id=uid,
        notification_type=NOTIFICATION_TYPE_CONVERSATION_ASSIGNMENT,
        primary_actor_type="Conversation",
        primary_actor_id=999_999,  # no such conversation → payload has no url
    )

    # VAPID configured (patched on the cached settings singleton).
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", "pub", raising=False)
    monkeypatch.setattr(settings, "vapid_private_key", "priv", raising=False)

    calls: list[dict] = []

    async def _fake_send(subscription, payload, **kwargs):
        calls.append(subscription)
        return 201

    monkeypatch.setattr(
        "app.domains.notifications.push.send_web_push", _fake_send
    )

    reached = await send_notification_push(
        db_session, notification_id=notification.id
    )
    assert reached == 1
    assert calls and calls[0]["endpoint"] == _SUB["endpoint"]

    # A 410 Gone response prunes the subscription.
    async def _gone(subscription, payload, **kwargs):
        return 410

    monkeypatch.setattr(
        "app.domains.notifications.push.send_web_push", _gone
    )
    reached2 = await send_notification_push(
        db_session, notification_id=notification.id
    )
    assert reached2 == 0
    left = list(
        (
            await db_session.exec(
                select(NotificationSubscription).where(
                    NotificationSubscription.user_id == uid
                )
            )
        ).all()
    )
    assert left == []
