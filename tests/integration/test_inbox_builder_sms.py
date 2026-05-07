"""Integration tests for the TwilioSms + Sms (Bandwidth) branches
of InboxBuilder.

Anchors:
  reference/chatwoot/app/models/channel/twilio_sms.rb
  reference/chatwoot/app/models/channel/sms.rb
"""

from __future__ import annotations

import pytest

from app.core.errors import ChatwootHTTPException
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.models import (
    CHANNEL_TYPE_SMS,
    CHANNEL_TYPE_TWILIO_SMS,
    TWILIO_MEDIUM_SMS,
    TWILIO_MEDIUM_WHATSAPP,
    SmsChannel,
    TwilioSmsChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams

pytestmark = pytest.mark.integration


async def _make_account(db_session, suffix: str = ""):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@sms.example.com",
            account_name=f"SMS{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


# ===========================================================================
# Twilio SMS
# ===========================================================================
async def test_twilio_creates_sms_channel(db_session):
    owner = await _make_account(db_session, suffix="-tw-ok")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Acme Twilio",
            channel_type="twilio_sms",
            channel_params={
                "account_sid": "ACxxxxxxxxxxxxxxxxx",
                "auth_token": "atok-secret",
                "phone_number": "+15551234567",
            },
        ),
    ).perform()
    assert result.inbox.channel_type == CHANNEL_TYPE_TWILIO_SMS
    assert isinstance(result.channel, TwilioSmsChannel)
    ch = result.channel
    assert ch.account_sid == "ACxxxxxxxxxxxxxxxxx"
    assert ch.auth_token == "atok-secret"
    assert ch.phone_number == "+15551234567"
    assert ch.medium == TWILIO_MEDIUM_SMS  # default
    assert ch.medium_str == "sms"


async def test_twilio_accepts_messaging_service_sid_without_phone(db_session):
    """``phone_number`` and ``messaging_service_sid`` are alternatives;
    Twilio routes via the latter when set."""
    owner = await _make_account(db_session, suffix="-tw-msvc")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Acme Twilio MSvc",
            channel_type="twilio_sms",
            channel_params={
                "account_sid": "ACxxxx",
                "auth_token": "tok",
                "messaging_service_sid": "MGxxxx",
            },
        ),
    ).perform()
    assert result.channel.phone_number is None
    assert result.channel.messaging_service_sid == "MGxxxx"


async def test_twilio_whatsapp_medium_is_accepted(db_session):
    """``medium=whatsapp`` is accepted in 5f.1; the send path lights
    up in sub-phase 5f.6."""
    owner = await _make_account(db_session, suffix="-tw-wa")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Acme Twilio WhatsApp",
            channel_type="twilio_sms",
            channel_params={
                "account_sid": "ACxxxx",
                "auth_token": "tok",
                "phone_number": "+15551111111",
                "medium": "whatsapp",
            },
        ),
    ).perform()
    assert result.channel.medium == TWILIO_MEDIUM_WHATSAPP
    assert result.channel.medium_str == "whatsapp"


async def test_twilio_rejects_missing_account_sid(db_session):
    owner = await _make_account(db_session, suffix="-tw-noasid")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="twilio_sms",
                channel_params={
                    "auth_token": "tok",
                    "phone_number": "+15552223344",
                },
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "account_sid" in exc_info.value.detail.get("attributes", [])


async def test_twilio_rejects_missing_auth_token(db_session):
    owner = await _make_account(db_session, suffix="-tw-notok")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="twilio_sms",
                channel_params={
                    "account_sid": "ACxxxx",
                    "phone_number": "+15553334455",
                },
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "auth_token" in exc_info.value.detail.get("attributes", [])


async def test_twilio_rejects_missing_phone_and_msvc(db_session):
    owner = await _make_account(db_session, suffix="-tw-nopn")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="twilio_sms",
                channel_params={
                    "account_sid": "ACxxxx",
                    "auth_token": "tok",
                },
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "phone_number" in exc_info.value.detail.get("attributes", [])


async def test_twilio_phone_number_is_globally_unique(db_session):
    """Twilio only lets one Account own a phone number — the unique
    index is global."""
    owner_a = await _make_account(db_session, suffix="-tw-uniq-a")
    owner_b = await _make_account(db_session, suffix="-tw-uniq-b")
    base = {
        "account_sid": "ACxxxx",
        "auth_token": "tok",
        "phone_number": "+15554444444",
    }
    await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner_a.account,
            name="First",
            channel_type="twilio_sms",
            channel_params=dict(base),
        ),
    ).perform()
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner_b.account,
                name="Second",
                channel_type="twilio_sms",
                channel_params=dict(base),
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "already taken" in exc_info.value.detail["message"]


# ===========================================================================
# Bandwidth SMS
# ===========================================================================
def _bw_config() -> dict[str, str]:
    return {
        "account_id": "bw-acct-1",
        "api_token": "bw-token",
        "api_secret": "bw-secret",
        "application_id": "bw-app-1",
    }


async def test_bandwidth_creates_sms_channel(db_session):
    owner = await _make_account(db_session, suffix="-bw-ok")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Acme Bandwidth",
            channel_type="sms",
            channel_params={
                "phone_number": "+15555556677",
                "provider_config": _bw_config(),
            },
        ),
    ).perform()
    assert result.inbox.channel_type == CHANNEL_TYPE_SMS
    assert isinstance(result.channel, SmsChannel)
    ch = result.channel
    assert ch.phone_number == "+15555556677"
    assert ch.provider == "default"
    assert ch.provider_config == _bw_config()


async def test_bandwidth_rejects_missing_phone_number(db_session):
    owner = await _make_account(db_session, suffix="-bw-nopn")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="sms",
                channel_params={"provider_config": _bw_config()},
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "phone_number" in exc_info.value.detail.get("attributes", [])


@pytest.mark.parametrize(
    "missing", ["account_id", "api_token", "api_secret", "application_id"]
)
async def test_bandwidth_rejects_missing_provider_config_key(
    db_session, missing: str
):
    owner = await _make_account(
        db_session, suffix=f"-bw-cfg-{missing[:6]}"
    )
    cfg = _bw_config()
    cfg.pop(missing)
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="sms",
                channel_params={
                    "phone_number": "+15556667788",
                    "provider_config": cfg,
                },
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert (
        f"provider_config.{missing}"
        in exc_info.value.detail.get("attributes", [])
    )


async def test_bandwidth_phone_number_is_globally_unique(db_session):
    owner_a = await _make_account(db_session, suffix="-bw-uniq-a")
    owner_b = await _make_account(db_session, suffix="-bw-uniq-b")
    base = {
        "phone_number": "+15557778899",
        "provider_config": _bw_config(),
    }
    await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner_a.account,
            name="First",
            channel_type="sms",
            channel_params=dict(base),
        ),
    ).perform()
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner_b.account,
                name="Second",
                channel_type="sms",
                channel_params=dict(base),
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "already taken" in exc_info.value.detail["message"]
