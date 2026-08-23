"""Letterheads an organisation reuses across mailboxes.

The two things that must hold: a mailbox connected before shared
templates existed keeps rendering exactly as it did, and a template that
would drop the agent's message is refused at save rather than discovered
by a customer receiving an empty shell.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.email import templates_service as svc
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration

TEMPLATE = "<html><body><h1>Acme</h1>{{contenido}}{{firma}}</body></html>"
OTHER = "<html><body><h1>Otra</h1>{{contenido}}</body></html>"


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


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@tpl.example.com",
            account_name=f"Tpl{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _email_inbox(db_session, owner, suffix, **fields):
    """A mailbox, then its branding.

    The builder takes transport settings only — the letterhead is
    configured afterwards, which is also the order a real admin does it
    in.
    """
    res = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"Casilla{suffix}",
            channel_type="email",
            channel_params={"email": f"buzon{suffix}@tpl.example.com"},
        ),
    ).perform()
    for key, value in fields.items():
        setattr(res.channel, key, value)
    if fields:
        db_session.add(res.channel)
        await db_session.flush()
    return res.inbox, res.channel


def _url(account_id: int) -> str:
    return f"/api/v1/accounts/{account_id}/email_templates"


# ---------------------------------------------------------------------------
# Several templates, one account
# ---------------------------------------------------------------------------
async def test_an_account_can_keep_more_than_one(client, db_session):
    owner, headers = await _seed(db_session, "-many")
    base = _url(owner.account.id)

    for name in ("Bienvenida", "Cierre de ticket"):
        resp = await client.post(
            base, headers=headers, json={"name": name, "template_html": TEMPLATE}
        )
        assert resp.status_code == 200, resp.text

    listed = await client.get(base, headers=headers)
    assert [t["name"] for t in listed.json()["payload"]] == [
        "Bienvenida",
        "Cierre de ticket",
    ]


async def test_two_templates_cannot_share_a_name(client, db_session):
    """A picker with two «Bienvenida» is a picker nobody can use."""
    owner, headers = await _seed(db_session, "-dup")
    base = _url(owner.account.id)
    await client.post(base, headers=headers, json={"name": "Bienvenida"})
    resp = await client.post(base, headers=headers, json={"name": "Bienvenida"})
    assert resp.status_code == 422
    assert "Ya existe una plantilla" in resp.json()["message"]


async def test_the_same_name_is_free_in_another_account(client, db_session):
    """Names are scoped to the tenant, not global."""
    one, one_headers = await _seed(db_session, "-scope-a")
    two, two_headers = await _seed(db_session, "-scope-b")
    r1 = await client.post(
        _url(one.account.id), headers=one_headers, json={"name": "Bienvenida"}
    )
    r2 = await client.post(
        _url(two.account.id), headers=two_headers, json={"name": "Bienvenida"}
    )
    assert r1.status_code == 200
    assert r2.status_code == 200


async def test_another_accounts_template_is_not_reachable(client, db_session):
    owner, owner_headers = await _seed(db_session, "-tenant-a")
    intruder, intruder_headers = await _seed(db_session, "-tenant-b")
    created = await client.post(
        _url(owner.account.id), headers=owner_headers, json={"name": "Privada"}
    )
    tid = created.json()["id"]

    # Asking under one's own account for someone else's id is a 404, not
    # a leak of whether it exists.
    resp = await client.get(
        f"{_url(intruder.account.id)}/{tid}", headers=intruder_headers
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# The rule that protects the customer
# ---------------------------------------------------------------------------
async def test_a_template_without_the_message_is_refused(client, db_session):
    """Without {{contenido}} every reply ships with the agent's text
    missing and the send still succeeds."""
    owner, headers = await _seed(db_session, "-novar")
    resp = await client.post(
        _url(owner.account.id),
        headers=headers,
        json={"name": "Rota", "template_html": "<html><body>hola</body></html>"},
    )
    assert resp.status_code == 422
    assert "{{contenido}}" in resp.json()["message"]


async def test_the_same_rule_applies_on_edit(client, db_session):
    owner, headers = await _seed(db_session, "-novar-edit")
    base = _url(owner.account.id)
    created = await client.post(
        base, headers=headers, json={"name": "Buena", "template_html": TEMPLATE}
    )
    resp = await client.patch(
        f"{base}/{created.json()['id']}",
        headers=headers,
        json={"template_html": "<p>sin variable</p>"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# How a mailbox resolves its markup
# ---------------------------------------------------------------------------
async def test_a_mailbox_without_a_link_keeps_its_own_html(db_session):
    """Every mailbox connected before shared templates existed."""
    owner, _ = await _seed(db_session, "-legacy")
    _inbox, channel = await _email_inbox(
        db_session, owner, "-legacy", template_html=TEMPLATE
    )
    assert await svc.resolve_html(db_session, channel=channel) == TEMPLATE


async def test_a_linked_template_wins_over_the_mailbox_html(db_session):
    owner, _ = await _seed(db_session, "-linked")
    _inbox, channel = await _email_inbox(
        db_session, owner, "-linked", template_html=TEMPLATE
    )
    shared = await svc.create_template(
        db_session,
        account_id=owner.account.id,
        name="Compartida",
        template_html=OTHER,
    )
    channel.email_template_id = shared.id
    db_session.add(channel)
    await db_session.flush()

    assert await svc.resolve_html(db_session, channel=channel) == OTHER


async def test_deleting_a_template_does_not_break_the_mailbox(
    client, db_session
):
    """ON DELETE SET NULL: the mailbox falls back, it does not go dark."""
    owner, headers = await _seed(db_session, "-del")
    _inbox, channel = await _email_inbox(
        db_session, owner, "-del", template_html=TEMPLATE
    )
    shared = await svc.create_template(
        db_session,
        account_id=owner.account.id,
        name="Temporal",
        template_html=OTHER,
    )
    channel.email_template_id = shared.id
    db_session.add(channel)
    await db_session.flush()

    resp = await client.delete(
        f"{_url(owner.account.id)}/{shared.id}", headers=headers
    )
    assert resp.status_code == 200, resp.text

    await db_session.refresh(channel)
    assert channel.email_template_id is None
    assert await svc.resolve_html(db_session, channel=channel) == TEMPLATE


async def test_a_link_to_a_vanished_template_falls_back(db_session):
    """Belt and braces: even if the FK ever failed to null the column."""
    owner, _ = await _seed(db_session, "-ghost")
    _inbox, channel = await _email_inbox(
        db_session, owner, "-ghost", template_html=TEMPLATE
    )
    channel.email_template_id = 987654321
    assert await svc.resolve_html(db_session, channel=channel) == TEMPLATE


async def test_an_empty_shared_template_falls_back_too(db_session):
    """A template someone created and never filled in must not blank the
    letterhead of every mailbox pointing at it."""
    owner, _ = await _seed(db_session, "-empty")
    _inbox, channel = await _email_inbox(
        db_session, owner, "-empty", template_html=TEMPLATE
    )
    shared = await svc.create_template(
        db_session, account_id=owner.account.id, name="Vacía"
    )
    channel.email_template_id = shared.id
    assert await svc.resolve_html(db_session, channel=channel) == TEMPLATE


# ---------------------------------------------------------------------------
# The sample the test send carries
# ---------------------------------------------------------------------------
def test_the_sample_fills_the_placeholders():
    html = svc.render_sample(
        template_html=TEMPLATE, signature="Acme S.A.", logo_url=""
    )
    assert "{{contenido}}" not in html
    assert "{{firma}}" not in html
    assert "Acme S.A." in html
    # Enough text to show how the layout wraps.
    assert "envío de prueba" in html
