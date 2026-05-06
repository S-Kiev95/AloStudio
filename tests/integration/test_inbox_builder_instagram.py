"""Integration tests for the InstagramChannel branch of InboxBuilder.

Pins the validation matrix (instagram_id + access_token required,
``instagram_id`` UNIQUE across accounts) and the auto-defaulted
``expires_at`` (Meta's 60-day long-lived-token TTL).

Anchors:
  reference/chatwoot/app/models/channel/instagram.rb
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.errors import ChatwootHTTPException
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.models import (
    CHANNEL_TYPE_INSTAGRAM,
    InstagramChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams

pytestmark = pytest.mark.integration


async def _make_account(db_session, suffix: str = ""):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@ig.example.com",
            account_name=f"IG{suffix}",
            user_full_name=f"IG Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


async def test_creates_instagram_channel(db_session):
    owner = await _make_account(db_session, suffix="-ok")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Acme IG",
            channel_type="instagram",
            channel_params={
                "instagram_id": "17841405822304914",
                "access_token": "EAAxxxx-ig",
            },
        ),
    ).perform()
    assert result.inbox.channel_type == CHANNEL_TYPE_INSTAGRAM
    assert isinstance(result.channel, InstagramChannel)
    assert result.channel.instagram_id == "17841405822304914"
    assert result.channel.access_token == "EAAxxxx-ig"
    # ``expires_at`` defaults to ~60 days out (long-lived token TTL).
    delta = result.channel.expires_at - datetime.now(UTC)
    assert timedelta(days=58) <= delta <= timedelta(days=61)


async def test_caller_supplied_expires_at_is_honored(db_session):
    owner = await _make_account(db_session, suffix="-explicit-exp")
    target = datetime.now(UTC) + timedelta(days=180)
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Acme IG",
            channel_type="instagram",
            channel_params={
                "instagram_id": "11111111111",
                "access_token": "tok",
                "expires_at": target.isoformat(),
            },
        ),
    ).perform()
    # Allow a 1-second drift for ISO round-trip.
    assert abs((result.channel.expires_at - target).total_seconds()) < 1.0


async def test_rejects_missing_instagram_id(db_session):
    owner = await _make_account(db_session, suffix="-noid")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="instagram",
                channel_params={"access_token": "tok"},
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "instagram_id" in exc_info.value.detail.get("attributes", [])


async def test_rejects_missing_access_token(db_session):
    owner = await _make_account(db_session, suffix="-notok")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="instagram",
                channel_params={"instagram_id": "111"},
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "access_token" in exc_info.value.detail.get("attributes", [])


async def test_rejects_malformed_expires_at(db_session):
    owner = await _make_account(db_session, suffix="-badexp")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="instagram",
                channel_params={
                    "instagram_id": "222",
                    "access_token": "tok",
                    "expires_at": "not-a-datetime",
                },
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "expires_at" in exc_info.value.detail.get("attributes", [])


async def test_instagram_id_is_globally_unique(db_session):
    """Meta only lets ONE app subscribe per IG id, so the unique
    index is account-agnostic. A second insert with the same
    ``instagram_id`` (even on a different account) raises 422."""
    owner_a = await _make_account(db_session, suffix="-a")
    owner_b = await _make_account(db_session, suffix="-b")
    base = {"instagram_id": "55555555", "access_token": "tok"}
    await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner_a.account,
            name="A",
            channel_type="instagram",
            channel_params=dict(base),
        ),
    ).perform()
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner_b.account,
                name="B",
                channel_type="instagram",
                channel_params=dict(base),
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "already taken" in exc_info.value.detail["message"]
