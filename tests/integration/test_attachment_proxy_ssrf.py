"""The attachment proxy must not become a window into the server's network.

``GET /accounts/{id}/attachments/{att}`` fetches ``external_url`` from the
server and returns the body. That URL is stored as it arrives — from a
dashboard message, from a widget visitor, from an Instagram webhook that
may not have been verified. Pointed at ``http://127.0.0.1:…``, the proxy
used to read whatever answered there and hand it back.

The internal URL is *mocked* here with a body that would be a leak, so the
test cannot pass by accident: without the guard nothing stops the request,
respx answers 200, and the secret comes back. (An unmocked localhost URL
would fail to connect on a test machine and 502 either way — a test with
no teeth.)
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.conversations.models import (
    MESSAGE_TYPE_INCOMING,
    Attachment,
    Conversation,
    Message,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration

INTERNAL = "http://127.0.0.1:8000/health"


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


async def _attachment_pointing_at(db_session, url: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@ssrf.example.com",
            account_name="SSRF",
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
                name="API",
                channel_type="api",
                channel_params={"webhook_url": ""},
            ),
        ).perform()
    ).inbox
    contact = Contact(account_id=owner.account.id, name="Visitante")
    db_session.add(contact)
    await db_session.flush()
    ci = ContactInbox(contact_id=contact.id, inbox_id=inbox.id, source_id="v-1")
    db_session.add(ci)
    await db_session.flush()
    conv = Conversation(
        account_id=owner.account.id,
        inbox_id=inbox.id,
        contact_id=contact.id,
        contact_inbox_id=ci.id,
        display_id=1,
    )
    db_session.add(conv)
    await db_session.flush()
    msg = Message(
        account_id=owner.account.id,
        inbox_id=inbox.id,
        conversation_id=conv.id,
        message_type=MESSAGE_TYPE_INCOMING,
        content="mirá esto",
    )
    db_session.add(msg)
    await db_session.flush()
    att = Attachment(
        account_id=owner.account.id,
        message_id=msg.id,
        file_type=0,
        external_url=url,
    )
    db_session.add(att)

    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, att, headers.as_response_headers()


@respx.mock
async def test_an_internal_url_is_not_fetched_or_returned(client, db_session):
    internal = respx.get(INTERNAL).mock(
        return_value=httpx.Response(200, text="secreto-interno")
    )
    owner, att, headers = await _attachment_pointing_at(db_session, INTERNAL)

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/attachments/{att.id}",
        headers=headers,
    )

    assert resp.status_code == 502
    assert "secreto-interno" not in resp.text
    assert not internal.called, "el servidor llegó a pedir la URL interna"
