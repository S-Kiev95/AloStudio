"""Contact profile pictures (F14): fetch from Meta, store our copy, serve it.

Meta's Graph API, its CDN and the object store are mocked with respx.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import avatar
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.contacts.presenters import present_contact
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.main import app

pytestmark = pytest.mark.integration

_CDN = "https://scontent.xx.fbcdn.net/v/pic.jpg"


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
async def seeded(db_session):
    """Account with a Messenger inbox and a contact who wrote to it."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@avatar.example.com",
            account_name="Avatar Co",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Página",
                channel_type="facebook",
                channel_params={
                    "page_id": "555",
                    "page_access_token": "EAA-page",
                },
            ),
        ).perform()
    ).inbox
    contact = Contact(
        account_id=owner.account.id,
        name="Lucía Pereira",
        last_activity_at=datetime.now(UTC),
    )
    db_session.add(contact)
    await db_session.flush()
    db_session.add(
        ContactInbox(contact_id=contact.id, inbox_id=inbox.id, source_id="PSID-9")
    )
    await db_session.flush()

    headers, tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner.account, contact, headers.as_response_headers()


def _store() -> str:
    return get_settings().s3_endpoint_url.rstrip("/")


def _mock_graph(pic: str | None) -> respx.Route:
    body = {"id": "PSID-9"} | ({"profile_pic": pic} if pic else {})
    return respx.get(url__regex=r"https://graph\.facebook\.com/.*/PSID-9").mock(
        return_value=httpx.Response(200, json=body)
    )


@respx.mock
async def test_the_picture_is_stored_and_shown(db_session, seeded):
    _, contact, _ = seeded
    graph = _mock_graph(_CDN)
    respx.get(_CDN).mock(
        return_value=httpx.Response(
            200, content=b"\xff\xd8jpeg", headers={"content-type": "image/jpeg"}
        )
    )
    put = respx.put(url__startswith=_store()).mock(return_value=httpx.Response(200))

    assert await avatar.refresh_avatar(db_session, contact) is True

    assert graph.calls.last.request.url.params["fields"] == "profile_pic"
    assert put.calls.last.request.content == b"\xff\xd8jpeg"
    assert contact.avatar_url is not None
    assert contact.avatar_url.endswith(
        f"accounts/{contact.account_id}/contacts/{contact.id}/avatar"
    )
    assert contact.avatar_refreshed_at is not None
    thumb = present_contact(contact)["thumbnail"]
    assert thumb.startswith(
        f"/api/backend/api/v1/accounts/{contact.account_id}/contacts/{contact.id}/avatar?v="
    )


@respx.mock
async def test_without_a_picture_the_attempt_is_still_recorded(db_session, seeded):
    _, contact, _ = seeded
    _mock_graph(None)

    assert await avatar.refresh_avatar(db_session, contact) is False

    assert contact.avatar_url is None
    assert contact.avatar_refreshed_at is not None
    assert present_contact(contact)["thumbnail"] == ""


@respx.mock
async def test_something_that_is_not_an_image_is_not_stored(db_session, seeded):
    _, contact, _ = seeded
    _mock_graph(_CDN)
    respx.get(_CDN).mock(
        return_value=httpx.Response(
            200, content=b"<html>", headers={"content-type": "text/html"}
        )
    )
    put = respx.put(url__startswith=_store()).mock(return_value=httpx.Response(200))

    assert await avatar.refresh_avatar(db_session, contact) is False
    assert not put.called
    assert contact.avatar_url is None


async def test_a_whatsapp_only_contact_is_not_asked(db_session, seeded):
    account, _, _ = seeded
    other = Contact(account_id=account.id, name="Solo WhatsApp")
    db_session.add(other)
    await db_session.flush()

    # No Instagram or Messenger inbox: no request at all (respx not active,
    # so a real one would fail loudly).
    assert await avatar.refresh_avatar(db_session, other) is False
    assert other.avatar_refreshed_at is None


async def test_the_daily_refresh_picks_missing_and_old_pictures(db_session, seeded):
    _, contact, _ = seeded
    now = datetime.now(UTC)

    assert contact.id in await avatar.stale_contact_ids(db_session, now=now)

    contact.avatar_refreshed_at = now - timedelta(days=1)
    await db_session.flush()
    assert contact.id not in await avatar.stale_contact_ids(db_session, now=now)

    contact.avatar_refreshed_at = now - timedelta(days=8)
    await db_session.flush()
    assert contact.id in await avatar.stale_contact_ids(db_session, now=now)

    # Not active lately: left alone.
    contact.last_activity_at = now - timedelta(days=60)
    await db_session.flush()
    assert contact.id not in await avatar.stale_contact_ids(db_session, now=now)


@respx.mock
async def test_the_route_serves_the_stored_picture(client, db_session, seeded):
    account, contact, headers = seeded
    contact.avatar_url = f"{_store()}/{get_settings().s3_bucket}/{avatar.avatar_key(contact)}"
    contact.avatar_refreshed_at = datetime.now(UTC)
    await db_session.flush()
    respx.get(url__startswith=_store()).mock(
        return_value=httpx.Response(
            200, content=b"\xff\xd8jpeg", headers={"content-type": "image/jpeg"}
        )
    )
    respx.route(host="test").pass_through()

    resp = await client.get(
        f"/api/v1/accounts/{account.id}/contacts/{contact.id}/avatar",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.content == b"\xff\xd8jpeg"
    assert resp.headers["content-type"] == "image/jpeg"
    assert "max-age" in resp.headers["cache-control"]


async def test_the_route_is_404_without_a_picture(client, seeded):
    account, contact, headers = seeded
    resp = await client.get(
        f"/api/v1/accounts/{account.id}/contacts/{contact.id}/avatar",
        headers=headers,
    )
    assert resp.status_code == 404


async def test_the_route_needs_a_session(client, seeded):
    account, contact, _ = seeded
    resp = await client.get(
        f"/api/v1/accounts/{account.id}/contacts/{contact.id}/avatar"
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Uploaded by hand (F11)
# ---------------------------------------------------------------------------
@respx.mock
async def test_a_picture_uploaded_by_hand_wins_over_meta(client, db_session, seeded):
    account, contact, headers = seeded
    put = respx.put(url__startswith=_store()).mock(return_value=httpx.Response(200))
    respx.route(host="test").pass_through()
    url = f"/api/v1/accounts/{account.id}/contacts/{contact.id}/avatar"

    resp = await client.post(
        url, files={"file": ("foto.png", b"\x89PNGdata", "image/png")}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert put.calls.last.request.content == b"\x89PNGdata"
    assert resp.json()["payload"]["thumbnail"].startswith(f"/api/backend{url}?v=")

    # The daily refresh leaves it alone: Meta isn't even asked.
    graph = _mock_graph(_CDN)
    assert await avatar.refresh_avatar(db_session, contact) is False
    assert not graph.called

    removed = await client.delete(url, headers=headers)
    assert removed.json()["payload"]["thumbnail"] == ""
    assert not avatar.needs_first_fetch(contact)


@respx.mock
async def test_an_upload_that_is_not_a_picture_is_refused(client, seeded):
    account, contact, headers = seeded
    respx.route(host="test").pass_through()
    resp = await client.post(
        f"/api/v1/accounts/{account.id}/contacts/{contact.id}/avatar",
        files={"file": ("doc.pdf", b"%PDF", "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 422
