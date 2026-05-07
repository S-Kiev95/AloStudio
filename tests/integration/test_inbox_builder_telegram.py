"""Integration tests for the TelegramChannel branch of InboxBuilder.

Anchors:
  reference/chatwoot/app/models/channel/telegram.rb
"""

from __future__ import annotations

import pytest

from app.core.errors import ChatwootHTTPException
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.models import (
    CHANNEL_TYPE_TELEGRAM,
    TelegramChannel,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams

pytestmark = pytest.mark.integration


async def _make_account(db_session, suffix: str = ""):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@tg.example.com",
            account_name=f"TG{suffix}",
            user_full_name=f"TG Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


async def test_creates_telegram_channel(db_session):
    owner = await _make_account(db_session, suffix="-ok")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Acme Telegram",
            channel_type="telegram",
            channel_params={
                "bot_token": "1234567890:AAAxxxxxxxxxxxxxxxxxx",
                "bot_name": "AcmeBot",
            },
        ),
    ).perform()
    assert result.inbox.channel_type == CHANNEL_TYPE_TELEGRAM
    assert isinstance(result.channel, TelegramChannel)
    assert result.channel.bot_token == "1234567890:AAAxxxxxxxxxxxxxxxxxx"
    assert result.channel.bot_name == "AcmeBot"


async def test_bot_name_defaults_when_omitted(db_session):
    owner = await _make_account(db_session, suffix="-noname")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="bot",
            channel_type="telegram",
            channel_params={"bot_token": "111:ZZZ"},
        ),
    ).perform()
    assert result.channel.bot_name == "telegram-bot"


async def test_rejects_missing_bot_token(db_session):
    owner = await _make_account(db_session, suffix="-notok")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="telegram",
                channel_params={"bot_name": "no-tok"},
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "bot_token" in exc_info.value.detail.get("attributes", [])


async def test_bot_token_is_globally_unique(db_session):
    """The bot_token unique index is account-agnostic — Telegram only
    binds a bot to one webhook URL, so the same token can't auth two
    different inboxes."""
    owner_a = await _make_account(db_session, suffix="-uniq-a")
    owner_b = await _make_account(db_session, suffix="-uniq-b")
    base = {"bot_token": "999:DUP-TOKEN"}
    await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner_a.account,
            name="First",
            channel_type="telegram",
            channel_params=dict(base),
        ),
    ).perform()
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner_b.account,
                name="Second",
                channel_type="telegram",
                channel_params=dict(base),
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "already taken" in exc_info.value.detail["message"]
