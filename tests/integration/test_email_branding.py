"""Signature and logo, set per mailbox and used on the way out.

Two things worth guarding: that a PATCH on an email inbox actually reaches
the email channel row (it used to load the Api one and drop the update on
the floor), and that the same payload cannot reach the SMTP credentials
sitting next to those fields.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.email.template import render_html, render_plain
from app.domains.inboxes.models import EmailChannel
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration

SIGNATURE = "Instituto Ejemplo\nAtención: 9 a 17 h"
LOGO = "https://cdn.ejemplo.edu.uy/logo.png"


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


@pytest.fixture
async def mailbox(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@brand.example.com",
            account_name="Brand Inc",
            user_full_name="Admin Brand",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Soporte",
            channel_type="email",
            channel_params={
                "email": "soporte@ejemplo.edu.uy",
                "smtp_address": "smtp.ejemplo.edu.uy",
                "smtp_login": "soporte",
                "smtp_password": "SMTP-SECRET",
            },
        ),
    ).perform()
    return owner, headers.as_response_headers(), result.inbox


def _url(owner, inbox) -> str:
    return f"/api/v1/accounts/{owner.account.id}/inboxes/{inbox.id}"


async def _channel(db_session, inbox) -> EmailChannel:
    return (
        await db_session.exec(
            select(EmailChannel).where(EmailChannel.id == inbox.channel_id)
        )
    ).one()


async def test_a_mailbox_starts_with_no_branding(client, mailbox):
    owner, headers, inbox = mailbox
    body = (await client.get(_url(owner, inbox), headers=headers)).json()
    assert body["signature"] == ""
    assert body["logo_url"] == ""


async def test_the_signature_and_logo_are_saved(client, mailbox, db_session):
    owner, headers, inbox = mailbox
    resp = await client.patch(
        _url(owner, inbox),
        json={"channel": {"signature": SIGNATURE, "logo_url": LOGO}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    channel = await _channel(db_session, inbox)
    assert channel.signature == SIGNATURE
    assert channel.logo_url == LOGO


async def test_they_come_back_on_the_inbox(client, mailbox):
    owner, headers, inbox = mailbox
    await client.patch(
        _url(owner, inbox),
        json={"channel": {"signature": SIGNATURE, "logo_url": LOGO}},
        headers=headers,
    )
    body = (await client.get(_url(owner, inbox), headers=headers)).json()
    assert body["signature"] == SIGNATURE
    assert body["logo_url"] == LOGO


async def test_a_signature_can_be_cleared(client, mailbox, db_session):
    """Empty string is a real value, not an omitted field."""
    owner, headers, inbox = mailbox
    await client.patch(
        _url(owner, inbox),
        json={"channel": {"signature": SIGNATURE}},
        headers=headers,
    )
    await client.patch(
        _url(owner, inbox),
        json={"channel": {"signature": ""}},
        headers=headers,
    )
    assert (await _channel(db_session, inbox)).signature == ""


async def test_saving_the_screen_does_not_erase_a_stored_password(
    client, mailbox, db_session
):
    """The form has nothing to re-submit, so it posts "".

    A stored password is never sent to the browser. Writing the empty
    string back would wipe the credential every time anyone saved this
    screen for an unrelated reason — the signature, say.
    """
    owner, headers, inbox = mailbox
    await client.patch(
        _url(owner, inbox),
        json={"channel": {"signature": SIGNATURE, "smtp_password": ""}},
        headers=headers,
    )
    channel = await _channel(db_session, inbox)
    assert channel.signature == SIGNATURE
    assert channel.smtp_password == "SMTP-SECRET"


async def test_a_password_typed_in_replaces_the_stored_one(
    client, mailbox, db_session
):
    owner, headers, inbox = mailbox
    await client.patch(
        _url(owner, inbox),
        json={"channel": {"smtp_password": "NUEVA"}},
        headers=headers,
    )
    assert (await _channel(db_session, inbox)).smtp_password == "NUEVA"


async def test_the_transport_config_comes_back_without_the_passwords(
    client, mailbox
):
    owner, headers, inbox = mailbox
    await client.patch(
        _url(owner, inbox),
        json={
            "channel": {
                "imap_enabled": True,
                "imap_address": "imap.ejemplo.edu.uy",
                "imap_port": 993,
                "imap_login": "soporte",
                "imap_password": "IMAP-SECRET",
            }
        },
        headers=headers,
    )
    body = (await client.get(_url(owner, inbox), headers=headers)).json()
    assert body["imap_enabled"] is True
    assert body["imap_address"] == "imap.ejemplo.edu.uy"
    assert body["imap_port"] == 993
    # The form needs to know one is stored without being told what it is.
    assert body["imap_password_set"] is True
    assert "IMAP-SECRET" not in str(body)
    assert "imap_password" not in body


async def test_the_smtp_password_is_never_presented(client, mailbox):
    owner, headers, inbox = mailbox
    body = (await client.get(_url(owner, inbox), headers=headers)).json()
    assert "SMTP-SECRET" not in str(body)


async def test_another_accounts_mailbox_cannot_be_rebranded(
    client, mailbox, db_session
):
    owner, headers, _inbox = mailbox
    other = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@other.example.com",
            account_name="Other Inc",
            user_full_name="Admin Other",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    their_inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=other.account,
                name="Suyo",
                channel_type="email",
                channel_params={"email": "hola@otro.com"},
            ),
        ).perform()
    ).inbox

    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/inboxes/{their_inbox.id}",
        json={"channel": {"signature": "mío ahora"}},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_what_is_saved_is_what_goes_out(client, mailbox, db_session):
    """The end the whole feature exists for."""
    owner, headers, inbox = mailbox
    await client.patch(
        _url(owner, inbox),
        json={"channel": {"signature": SIGNATURE, "logo_url": LOGO}},
        headers=headers,
    )
    channel = await _channel(db_session, inbox)

    html = render_html(
        body="Ahí va el detalle",
        signature=channel.signature,
        logo_url=channel.logo_url,
    )
    text = render_plain(body="Ahí va el detalle", signature=channel.signature)
    assert "Instituto Ejemplo" in html
    assert LOGO in html
    assert text.endswith(SIGNATURE)


async def test_a_mailbox_can_bring_its_own_html(client, mailbox, db_session):
    owner, headers, inbox = mailbox
    tpl = '<div style="background:#003366">{{logo}}</div>{{contenido}}'
    resp = await client.patch(
        _url(owner, inbox), json={"channel": {"template_html": tpl}}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert (await _channel(db_session, inbox)).template_html == tpl

    body = (await client.get(_url(owner, inbox), headers=headers)).json()
    assert body["template_html"] == tpl


async def test_a_template_that_would_drop_the_message_is_refused(
    client, mailbox, db_session
):
    """It would send successfully with the reply missing.

    Nothing downstream would notice — the customer receives an empty
    shell — so this has to be caught at save time, not at send time.
    """
    owner, headers, inbox = mailbox
    resp = await client.patch(
        _url(owner, inbox),
        json={"channel": {"template_html": "<div>solo el encabezado</div>"}},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "contenido" in resp.text
    assert (await _channel(db_session, inbox)).template_html == ""


async def test_clearing_the_template_returns_to_the_built_in_design(
    client, mailbox, db_session
):
    owner, headers, inbox = mailbox
    await client.patch(
        _url(owner, inbox),
        json={"channel": {"template_html": "<p>{{contenido}}</p>"}},
        headers=headers,
    )
    resp = await client.patch(
        _url(owner, inbox), json={"channel": {"template_html": ""}}, headers=headers
    )
    assert resp.status_code == 200
    assert (await _channel(db_session, inbox)).template_html == ""


async def test_the_designer_settings_are_stored_with_the_html(
    client, mailbox, db_session
):
    """Reopening the designer needs the controls back.

    Parsing them out of the generated markup would be guesswork that
    breaks the moment anyone edits it.
    """
    owner, headers, inbox = mailbox
    resp = await client.patch(
        _url(owner, inbox),
        json={
            "channel": {
                "template_html": "<div>{{contenido}}</div>",
                "template_design": {"headerTitle": "Instituto", "showLogo": True},
            }
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    channel = await _channel(db_session, inbox)
    assert channel.template_design["headerTitle"] == "Instituto"

    body = (await client.get(_url(owner, inbox), headers=headers)).json()
    assert body["template_design"]["showLogo"] is True


async def test_hand_editing_the_html_forgets_the_design(
    client, mailbox, db_session
):
    """Otherwise the designer would reopen with controls that no longer
    describe the template, and overwrite the edit on the next save."""
    owner, headers, inbox = mailbox
    await client.patch(
        _url(owner, inbox),
        json={
            "channel": {
                "template_html": "<div>{{contenido}}</div>",
                "template_design": {"headerTitle": "Instituto"},
            }
        },
        headers=headers,
    )
    await client.patch(
        _url(owner, inbox),
        json={"channel": {"template_html": "<p>{{contenido}}</p> a mano"}},
        headers=headers,
    )
    channel = await _channel(db_session, inbox)
    assert channel.template_design is None
    assert "a mano" in channel.template_html


async def test_saving_something_else_leaves_the_design_alone(
    client, mailbox, db_session
):
    """Only an HTML change without a design means "hand-edited"."""
    owner, headers, inbox = mailbox
    await client.patch(
        _url(owner, inbox),
        json={
            "channel": {
                "template_html": "<div>{{contenido}}</div>",
                "template_design": {"headerTitle": "Instituto"},
            }
        },
        headers=headers,
    )
    await client.patch(
        _url(owner, inbox),
        json={"channel": {"signature": SIGNATURE}},
        headers=headers,
    )
    channel = await _channel(db_session, inbox)
    assert channel.template_design is not None
    assert channel.template_design["headerTitle"] == "Instituto"
