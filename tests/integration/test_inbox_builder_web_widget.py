"""Integration tests for the WebWidget branch of :class:`InboxBuilder`.

The widget channel adds a different shape of channel row than the
existing ``api`` branch, so we pin the happy path + the
``website_url`` validation guard here. The HTTP-level flow lands
with milestones 5a.2/5a.3.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WEB_WIDGET,
    WebWidget,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
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


async def test_creates_web_widget_channel_with_defaults(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@ww.example.com",
            account_name="WW Inc",
            user_full_name="WW Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()

    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Site Chat",
            channel_type="web_widget",
            channel_params={"website_url": "https://example.com"},
        ),
    ).perform()

    inbox = result.inbox
    assert inbox.channel_type == CHANNEL_TYPE_WEB_WIDGET
    assert isinstance(result.channel, WebWidget)
    ww = result.channel
    assert ww.website_url == "https://example.com"
    # Auto-generated tokens are present.
    assert ww.website_token and len(ww.website_token) >= 8
    assert ww.hmac_token and len(ww.hmac_token) >= 8
    assert ww.website_token != ww.hmac_token
    # Default colour + flags + pre-chat form options shipped.
    assert ww.widget_color == "#1f93ff"
    assert ww.feature_flags == 7  # attachments + emoji + end_conversation
    assert ww.attachments is True
    assert ww.emoji_picker is True
    assert ww.end_conversation is True
    assert ww.use_inbox_avatar_for_bot is False
    assert ww.allow_mobile_webview is False
    assert "pre_chat_message" in ww.pre_chat_form_options


async def test_rejects_missing_website_url(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@ww2.example.com",
            account_name="WW2",
            user_full_name="Admin2",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()

    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Bad Widget",
                channel_type="web_widget",
                channel_params={},  # no website_url
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "website_url" in exc_info.value.detail.get("attributes", [])


async def test_website_token_is_unique_across_widgets(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@ww3.example.com",
            account_name="WW3",
            user_full_name="Admin3",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()

    seen_tokens: set[str] = set()
    for n in range(3):
        result = await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name=f"Site {n}",
                channel_type="web_widget",
                channel_params={"website_url": f"https://site{n}.example.com"},
            ),
        ).perform()
        assert result.channel.website_token not in seen_tokens
        seen_tokens.add(result.channel.website_token)
