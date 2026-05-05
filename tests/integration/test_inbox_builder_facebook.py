"""Integration tests for the FacebookPage branch of InboxBuilder.

Pins the validation matrix (page_id + page_access_token required,
the (page_id, account_id) uniqueness constraint) and the Instagram
hand-off slot (``instagram_id``) that Phase 5e will read.

Anchors:
  reference/chatwoot/app/models/channel/facebook_page.rb
"""

from __future__ import annotations

import pytest

from app.core.errors import ChatwootHTTPException
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.models import (
    CHANNEL_TYPE_FACEBOOK,
    FacebookPage,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams

pytestmark = pytest.mark.integration


async def _make_account(db_session, suffix: str = ""):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@fb.example.com",
            account_name=f"FB{suffix}",
            user_full_name=f"FB Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


async def test_creates_facebook_page_channel(db_session):
    owner = await _make_account(db_session, suffix="-ok")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Acme Page",
            channel_type="facebook",
            channel_params={
                "page_id": "1234567890",
                "page_access_token": "EAAxxxx-page",
                "user_access_token": "EAAxxxx-user",
            },
        ),
    ).perform()

    assert result.inbox.channel_type == CHANNEL_TYPE_FACEBOOK
    assert isinstance(result.channel, FacebookPage)
    assert result.channel.page_id == "1234567890"
    assert result.channel.page_access_token == "EAAxxxx-page"
    assert result.channel.user_access_token == "EAAxxxx-user"
    assert result.channel.instagram_id is None


async def test_user_access_token_defaults_to_page_token(db_session):
    """Caller can omit ``user_access_token`` — InboxBuilder copies the
    page token over so the column's NOT NULL constraint is satisfied
    in the common single-token deployment path."""
    owner = await _make_account(db_session, suffix="-default-tok")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Acme Page",
            channel_type="facebook",
            channel_params={
                "page_id": "9999999999",
                "page_access_token": "EAAxxxx-page",
            },
        ),
    ).perform()
    assert result.channel.user_access_token == "EAAxxxx-page"


async def test_stores_instagram_id_when_provided(db_session):
    owner = await _make_account(db_session, suffix="-ig")
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Acme Page + IG",
            channel_type="facebook",
            channel_params={
                "page_id": "5555555555",
                "page_access_token": "tok",
                "instagram_id": "17841405822304914",
            },
        ),
    ).perform()
    assert result.channel.instagram_id == "17841405822304914"


async def test_rejects_missing_page_id(db_session):
    owner = await _make_account(db_session, suffix="-nopid")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="facebook",
                channel_params={"page_access_token": "tok"},
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "page_id" in exc_info.value.detail.get("attributes", [])


async def test_rejects_missing_page_access_token(db_session):
    owner = await _make_account(db_session, suffix="-notok")
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="bad",
                channel_type="facebook",
                channel_params={"page_id": "111"},
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "page_access_token" in exc_info.value.detail.get("attributes", [])


async def test_page_id_unique_per_account(db_session):
    """``(page_id, account_id)`` UNIQUE — the same agent can't connect
    two inboxes to the same page. Surfaces as a 422 with the
    canonical "already taken" envelope."""
    owner = await _make_account(db_session, suffix="-uniq")
    base = {"page_id": "8888888888", "page_access_token": "tok"}

    await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="First",
            channel_type="facebook",
            channel_params=dict(base),
        ),
    ).perform()
    with pytest.raises(ChatwootHTTPException) as exc_info:
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Second",
                channel_type="facebook",
                channel_params=dict(base),
            ),
        ).perform()
    assert exc_info.value.status_code == 422
    assert "already taken" in exc_info.value.detail["message"]


async def test_same_page_id_different_account_is_allowed(db_session):
    """The unique index is scoped — two separate accounts can each
    connect to the same FB page (rare but valid: whitelabel
    resellers do this)."""
    owner_a = await _make_account(db_session, suffix="-ma")
    owner_b = await _make_account(db_session, suffix="-mb")
    base = {"page_id": "7777777777", "page_access_token": "tok"}

    await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner_a.account,
            name="A",
            channel_type="facebook",
            channel_params=dict(base),
        ),
    ).perform()
    # Should NOT raise.
    await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner_b.account,
            name="B",
            channel_type="facebook",
            channel_params=dict(base),
        ),
    ).perform()
