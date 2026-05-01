"""Integration tests for the WhatsappChannel branch of InboxBuilder.

Covers both providers (``whatsapp_cloud`` + ``default``/360dialog),
their respective ``provider_config`` validation matrices, the
auto-generated ``webhook_verify_token`` and the unique-phone
constraint that surfaces as a 422.

Anchors:
  reference/chatwoot/app/models/channel/whatsapp.rb
  reference/chatwoot/app/services/whatsapp/channel_creation_service.rb
"""

from __future__ import annotations

import pytest

from app.core.errors import ChatwootHTTPException
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WHATSAPP,
    WHATSAPP_PROVIDER_360DIALOG,
    WHATSAPP_PROVIDER_CLOUD,
    WhatsappChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams

pytestmark = pytest.mark.integration


async def _make_account(db_session, suffix: str = ""):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@wa.example.com",
            account_name=f"WA{suffix}",
            user_full_name=f"WA Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


# ---------------------------------------------------------------------------
# Cloud (whatsapp_cloud) provider
# ---------------------------------------------------------------------------
async def test_creates_whatsapp_cloud_channel(db_session):
    owner = await _make_account(db_session, suffix="-cloud")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WhatsApp Support",
            channel_type="whatsapp",
            channel_params={
                "phone_number": "+15551234567",
                "provider": WHATSAPP_PROVIDER_CLOUD,
                "provider_config": {
                    "api_key": "EAAxxxxxxxx",
                    "phone_number_id": "1234567890",
                    "business_account_id": "9876543210",
                },
            },
        ),
    ).perform()

    assert result.inbox.channel_type == CHANNEL_TYPE_WHATSAPP
    assert isinstance(result.channel, WhatsappChannel)
    ch = result.channel
    assert ch.phone_number == "+15551234567"
    assert ch.provider == WHATSAPP_PROVIDER_CLOUD
    cfg = ch.provider_config
    assert cfg["api_key"] == "EAAxxxxxxxx"
    assert cfg["phone_number_id"] == "1234567890"
    assert cfg["business_account_id"] == "9876543210"
    # webhook_verify_token is auto-generated.
    assert ch.webhook_verify_token
    assert len(ch.webhook_verify_token) >= 16


async def test_cloud_requires_api_key(db_session):
    owner = await _make_account(db_session, suffix="-cloud-noapi")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="whatsapp",
                channel_params={
                    "phone_number": "+15551111111",
                    "provider": WHATSAPP_PROVIDER_CLOUD,
                    "provider_config": {
                        "phone_number_id": "1",
                        "business_account_id": "1",
                    },
                },
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "provider_config.api_key" in exc_info.value.detail.get("attributes", [])


async def test_cloud_requires_phone_number_id(db_session):
    owner = await _make_account(db_session, suffix="-cloud-nopid")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="whatsapp",
                channel_params={
                    "phone_number": "+15552222222",
                    "provider": WHATSAPP_PROVIDER_CLOUD,
                    "provider_config": {
                        "api_key": "k",
                        "business_account_id": "1",
                    },
                },
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "provider_config.phone_number_id" in exc_info.value.detail.get("attributes", [])


async def test_cloud_uses_caller_supplied_verify_token_when_present(db_session):
    """The agent can pre-set ``webhook_verify_token`` if they're
    re-using an existing Meta app's value. We honor it and don't
    overwrite."""
    owner = await _make_account(db_session, suffix="-cloud-tok")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WA",
            channel_type="whatsapp",
            channel_params={
                "phone_number": "+15553333333",
                "provider": WHATSAPP_PROVIDER_CLOUD,
                "provider_config": {
                    "api_key": "k",
                    "phone_number_id": "1",
                    "business_account_id": "1",
                    "webhook_verify_token": "preset-token-from-meta-app",
                },
            },
        ),
    ).perform()
    assert result.channel.webhook_verify_token == "preset-token-from-meta-app"


# ---------------------------------------------------------------------------
# 360dialog (default) provider
# ---------------------------------------------------------------------------
async def test_creates_whatsapp_360dialog_channel(db_session):
    owner = await _make_account(db_session, suffix="-360d")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WA via 360dialog",
            channel_type="whatsapp",
            channel_params={
                "phone_number": "+15554444444",
                "provider": WHATSAPP_PROVIDER_360DIALOG,
                "provider_config": {
                    "api_key": "360d-key",
                    "url": "https://waba.360dialog.io/v1",
                },
            },
        ),
    ).perform()
    ch = result.channel
    assert isinstance(ch, WhatsappChannel)
    assert ch.provider == WHATSAPP_PROVIDER_360DIALOG
    assert ch.provider_config["url"] == "https://waba.360dialog.io/v1"


async def test_360dialog_defaults_when_provider_omitted(db_session):
    """``provider`` defaults to ``default`` (360dialog) when caller
    omits it — matches Rails ``default: 'default'`` in the schema."""
    owner = await _make_account(db_session, suffix="-360d-default")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="WA",
            channel_type="whatsapp",
            channel_params={
                "phone_number": "+15555555555",
                "provider_config": {
                    "api_key": "360d-key",
                    "url": "https://waba.360dialog.io/v1",
                },
            },
        ),
    ).perform()
    assert result.channel.provider == WHATSAPP_PROVIDER_360DIALOG


async def test_360dialog_requires_url(db_session):
    owner = await _make_account(db_session, suffix="-360d-nourl")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="whatsapp",
                channel_params={
                    "phone_number": "+15556666666",
                    "provider": WHATSAPP_PROVIDER_360DIALOG,
                    "provider_config": {"api_key": "360d-key"},
                },
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "provider_config.url" in exc_info.value.detail.get("attributes", [])


# ---------------------------------------------------------------------------
# Generic validation
# ---------------------------------------------------------------------------
async def test_rejects_missing_phone_number(db_session):
    owner = await _make_account(db_session, suffix="-nopn")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="whatsapp",
                channel_params={
                    "provider": WHATSAPP_PROVIDER_CLOUD,
                    "provider_config": {
                        "api_key": "k",
                        "phone_number_id": "1",
                        "business_account_id": "1",
                    },
                },
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "phone_number" in exc_info.value.detail.get("attributes", [])


async def test_rejects_unknown_provider(db_session):
    owner = await _make_account(db_session, suffix="-badprov")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="whatsapp",
                channel_params={
                    "phone_number": "+15557777777",
                    "provider": "twilio_pretender",
                    "provider_config": {"api_key": "k", "url": "x"},
                },
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "provider" in exc_info.value.detail.get("attributes", [])


async def test_phone_number_uniqueness(db_session):
    """The unique index on ``phone_number`` surfaces as a 422
    envelope mirroring the email-uniqueness flow in 5b.1."""
    owner = await _make_account(db_session, suffix="-uniq")
    base_params = {
        "phone_number": "+15558888888",
        "provider": WHATSAPP_PROVIDER_CLOUD,
        "provider_config": {
            "api_key": "k",
            "phone_number_id": "1",
            "business_account_id": "1",
        },
    }
    await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="First",
            channel_type="whatsapp",
            channel_params=dict(base_params),
        ),
    ).perform()

    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Second",
                channel_type="whatsapp",
                channel_params=dict(base_params),
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "already taken" in exc_info.value.detail["message"]
