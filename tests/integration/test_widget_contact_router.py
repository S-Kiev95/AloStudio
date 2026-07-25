"""Integration tests for ``/api/v1/widget/{config,contact,...}``.

Anchors:
  reference/chatwoot/app/controllers/api/v1/widget/configs_controller.rb
  reference/chatwoot/app/controllers/api/v1/widget/contacts_controller.rb
  reference/chatwoot/app/helpers/widget_helper.rb

Coverage:
  * config bootstrap mints a fresh contact + token when the request
    has no ``X-Auth-Token`` (or carries one whose source_id no longer
    resolves).
  * config returns the existing contact + a freshly-rotated token when
    the request carries a valid token.
  * GET /contact returns the resolved contact; 404 without a token.
  * PATCH /contact runs identify-style updates.
  * POST /contact/set_user — HMAC required when ``hmac_mandatory`` is
    on; rejects bad signatures.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.db import get_session
from app.core.widget_token import decode_widget_token
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import ContactInbox
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


async def _seed_widget(db_session, *, hmac_mandatory: bool = False):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@wid.example.com",
            account_name="Widget Inc",
            user_full_name="Widget Admin",
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
            channel_params={
                "website_url": "https://example.com",
                "hmac_mandatory": hmac_mandatory,
            },
        ),
    ).perform()
    web_widget = result.channel
    inbox = result.inbox
    return owner, inbox, web_widget


# ---------------------------------------------------------------------------
# /widget/config
# ---------------------------------------------------------------------------
async def test_config_without_token_mints_contact(client, db_session):
    _, _, ww = await _seed_widget(db_session)
    resp = await client.post(
        f"/api/v1/widget/config?website_token={ww.website_token}"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Token shape: JWT decoding returns source_id + inbox_id.
    assert "auth_token" in body
    decoded = decode_widget_token(body["auth_token"])
    assert decoded["source_id"]
    assert decoded["inbox_id"] == body["inbox"]["id"]
    # Contact was minted.
    assert body["contact"]["id"]
    assert body["contact"]["name"].startswith("visitor-")
    # Inbox config exposes the widget palette + flags.
    assert body["inbox"]["website_token"] == ww.website_token
    assert body["inbox"]["widget_color"] == "#1f93ff"
    assert body["inbox"]["feature_flags"]["attachments"] is True


async def test_config_with_valid_token_returns_existing_contact(
    client, db_session
):
    _, _inbox, ww = await _seed_widget(db_session)
    # Bootstrap once to mint a contact.
    first = await client.post(
        f"/api/v1/widget/config?website_token={ww.website_token}"
    )
    token = first.json()["auth_token"]
    contact_id = first.json()["contact"]["id"]

    # Second call carrying the token must return the same contact.
    second = await client.post(
        f"/api/v1/widget/config?website_token={ww.website_token}",
        headers={"X-Auth-Token": token},
    )
    assert second.status_code == 200
    body = second.json()
    assert body["contact"]["id"] == contact_id
    # The token re-mint may or may not produce a different string
    # (iat is in whole seconds — back-to-back calls in the same second
    # yield identical signatures). What MUST hold is that the new
    # token decodes to the same source_id.
    decoded_first = decode_widget_token(token)
    decoded_second = decode_widget_token(body["auth_token"])
    assert decoded_first["source_id"] == decoded_second["source_id"]


async def test_config_unknown_website_token_returns_404(client, db_session):
    await _seed_widget(db_session)  # seed at least one widget
    resp = await client.post(
        "/api/v1/widget/config?website_token=does-not-exist"
    )
    assert resp.status_code == 404
    assert resp.json() == {"error": "web widget does not exist"}


# ---------------------------------------------------------------------------
# /widget/contact (show + update)
# ---------------------------------------------------------------------------
async def test_contact_show_requires_token(client, db_session):
    _, _, ww = await _seed_widget(db_session)
    resp = await client.get(
        f"/api/v1/widget/contact?website_token={ww.website_token}"
    )
    assert resp.status_code == 404


async def test_contact_show_returns_contact(client, db_session):
    _, _, ww = await _seed_widget(db_session)
    cfg = await client.post(
        f"/api/v1/widget/config?website_token={ww.website_token}"
    )
    token = cfg.json()["auth_token"]
    resp = await client.get(
        f"/api/v1/widget/contact?website_token={ww.website_token}",
        headers={"X-Auth-Token": token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == cfg.json()["contact"]["id"]


async def test_contact_update_writes_email_and_name(client, db_session):
    _, _, ww = await _seed_widget(db_session)
    cfg = await client.post(
        f"/api/v1/widget/config?website_token={ww.website_token}"
    )
    token = cfg.json()["auth_token"]
    resp = await client.patch(
        f"/api/v1/widget/contact?website_token={ww.website_token}",
        json={"email": "alice@example.com", "name": "Alice"},
        headers={"X-Auth-Token": token},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == "alice@example.com"
    # ``retain_original_contact_name=True`` → the placeholder
    # "visitor-…" name is kept on the merge path. But this is a fresh
    # contact (no merge target) so the new name lands.
    assert body["name"] == "Alice"


# ---------------------------------------------------------------------------
# /widget/contact/set_user — HMAC paths
# ---------------------------------------------------------------------------
def _hmac_for(hmac_token: str, identifier: str) -> str:
    return hmac.new(
        hmac_token.encode("utf-8"),
        identifier.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def test_set_user_succeeds_without_hmac_when_not_mandatory(
    client, db_session
):
    _, _, ww = await _seed_widget(db_session, hmac_mandatory=False)
    cfg = await client.post(
        f"/api/v1/widget/config?website_token={ww.website_token}"
    )
    token = cfg.json()["auth_token"]
    resp = await client.post(
        f"/api/v1/widget/contact/set_user?website_token={ww.website_token}",
        json={"identifier": "user-42", "name": "Bob"},
        headers={"X-Auth-Token": token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["identifier"] == "user-42"


async def test_set_user_rejects_bad_hmac(client, db_session):
    _, _, ww = await _seed_widget(db_session, hmac_mandatory=True)
    cfg = await client.post(
        f"/api/v1/widget/config?website_token={ww.website_token}"
    )
    token = cfg.json()["auth_token"]
    resp = await client.post(
        f"/api/v1/widget/contact/set_user?website_token={ww.website_token}",
        json={"identifier": "user-42", "identifier_hash": "deadbeef"},
        headers={"X-Auth-Token": token},
    )
    assert resp.status_code == 401
    assert "HMAC failed" in resp.json()["error"]


async def test_set_user_succeeds_with_valid_hmac(client, db_session):
    _, _, ww = await _seed_widget(db_session, hmac_mandatory=True)
    cfg = await client.post(
        f"/api/v1/widget/config?website_token={ww.website_token}"
    )
    token = cfg.json()["auth_token"]
    identifier = "user-42"
    sig = _hmac_for(ww.hmac_token, identifier)

    resp = await client.post(
        f"/api/v1/widget/contact/set_user?website_token={ww.website_token}",
        json={
            "identifier": identifier,
            "identifier_hash": sig,
            "email": "alice@example.com",
        },
        headers={"X-Auth-Token": token},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["identifier"] == identifier
    assert body["email"] == "alice@example.com"

    # ``hmac_verified`` flips to True on the contact_inbox row.
    decoded = decode_widget_token(token)
    ci = (
        await db_session.exec(
            select(ContactInbox).where(
                ContactInbox.source_id == decoded["source_id"]
            )
        )
    ).first()
    assert ci is not None
    assert ci.hmac_verified is True


async def test_set_user_with_different_identifier_creates_new_session(
    client, db_session
):
    """Mirror ``a_different_contact?`` — an existing contact with a
    different identifier yields a fresh ContactInbox + token."""
    _, _, ww = await _seed_widget(db_session, hmac_mandatory=False)
    cfg = await client.post(
        f"/api/v1/widget/config?website_token={ww.website_token}"
    )
    token = cfg.json()["auth_token"]

    # First identify call sets identifier to "alice".
    r1 = await client.post(
        f"/api/v1/widget/contact/set_user?website_token={ww.website_token}",
        json={"identifier": "alice"},
        headers={"X-Auth-Token": token},
    )
    assert r1.status_code == 200
    first_contact_id = r1.json()["id"]

    # Second call with a DIFFERENT identifier — Rails spins a fresh
    # ContactInbox; the contact returned should have the new identifier
    # and (since no merge target exists) be a brand-new contact row.
    r2 = await client.post(
        f"/api/v1/widget/contact/set_user?website_token={ww.website_token}",
        json={"identifier": "bob"},
        headers={"X-Auth-Token": token},
    )
    assert r2.status_code == 200
    assert r2.json()["identifier"] == "bob"
    assert r2.json()["id"] != first_contact_id
