"""Letterheads an organisation reuses across mailboxes.

The two things that must hold: a mailbox connected before shared
templates existed keeps rendering exactly as it did, and a template that
would drop the agent's message is refused at save rather than discovered
by a customer receiving an empty shell.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.core.security import hash_password
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.email import signatures_service as sig_svc
from app.domains.email import templates_service as svc
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser, User
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
    headers, new_tokens = create_new_auth_token(user_tokens=owner.user.tokens, uid=owner.user.uid)
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
    r1 = await client.post(_url(one.account.id), headers=one_headers, json={"name": "Bienvenida"})
    r2 = await client.post(_url(two.account.id), headers=two_headers, json={"name": "Bienvenida"})
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
    resp = await client.get(f"{_url(intruder.account.id)}/{tid}", headers=intruder_headers)
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
    _inbox, channel = await _email_inbox(db_session, owner, "-legacy", template_html=TEMPLATE)
    assert await svc.resolve_html(db_session, channel=channel) == TEMPLATE


async def test_a_linked_template_wins_over_the_mailbox_html(db_session):
    owner, _ = await _seed(db_session, "-linked")
    _inbox, channel = await _email_inbox(db_session, owner, "-linked", template_html=TEMPLATE)
    shared = await svc.create_template(
        db_session,
        account_id=owner.account.id,
        name="Compartida",
        template_html=OTHER,
    )
    channel.email_template_id = shared.id
    db_session.add(channel)
    await db_session.flush()

    assert await svc.resolve_html(db_session, channel=channel) == "<h1>Otra</h1>{{contenido}}"


async def test_deleting_a_template_does_not_break_the_mailbox(client, db_session):
    """ON DELETE SET NULL: the mailbox falls back, it does not go dark."""
    owner, headers = await _seed(db_session, "-del")
    _inbox, channel = await _email_inbox(db_session, owner, "-del", template_html=TEMPLATE)
    shared = await svc.create_template(
        db_session,
        account_id=owner.account.id,
        name="Temporal",
        template_html=OTHER,
    )
    channel.email_template_id = shared.id
    db_session.add(channel)
    await db_session.flush()

    resp = await client.delete(f"{_url(owner.account.id)}/{shared.id}", headers=headers)
    assert resp.status_code == 200, resp.text

    await db_session.refresh(channel)
    assert channel.email_template_id is None
    assert await svc.resolve_html(db_session, channel=channel) == TEMPLATE


async def test_a_link_to_a_vanished_template_falls_back(db_session):
    """Belt and braces: even if the FK ever failed to null the column."""
    owner, _ = await _seed(db_session, "-ghost")
    _inbox, channel = await _email_inbox(db_session, owner, "-ghost", template_html=TEMPLATE)
    channel.email_template_id = 987654321
    assert await svc.resolve_html(db_session, channel=channel) == TEMPLATE


async def test_an_empty_shared_template_falls_back_too(db_session):
    """A template someone created and never filled in must not blank the
    letterhead of every mailbox pointing at it."""
    owner, _ = await _seed(db_session, "-empty")
    _inbox, channel = await _email_inbox(db_session, owner, "-empty", template_html=TEMPLATE)
    shared = await svc.create_template(db_session, account_id=owner.account.id, name="Vacía")
    channel.email_template_id = shared.id
    assert await svc.resolve_html(db_session, channel=channel) == TEMPLATE


# ---------------------------------------------------------------------------
# The sample the test send carries
# ---------------------------------------------------------------------------
def test_the_sample_fills_the_placeholders():
    html = svc.render_sample(template_html=TEMPLATE, signature="Acme S.A.", logo_url="")
    assert "{{contenido}}" not in html
    assert "{{firma}}" not in html
    assert "Acme S.A." in html
    # Enough text to show how the layout wraps.
    assert "envío de prueba" in html


# ---------------------------------------------------------------------------
# Helpers for multi-member tests
# ---------------------------------------------------------------------------
async def _add_agent(db_session, account, *, email: str, name: str, job_title: str | None = None):
    user = User(
        email=email,
        uid=email,
        name=name,
        job_title=job_title,
        encrypted_password=hash_password("Password123!"),
        custom_attributes={"phone_number": "+598 99 000 111"},
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        AccountUser(
            account_id=account.id,
            user_id=user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    headers, new_tokens = create_new_auth_token(user_tokens=user.tokens, uid=user.uid)
    user.tokens = new_tokens
    db_session.add(user)
    await db_session.flush()
    return user, headers.as_response_headers()


# ---------------------------------------------------------------------------
# Personal templates: private per user, org remains admin-only
# ---------------------------------------------------------------------------
async def test_agent_can_manage_own_personal_templates_only(client, db_session):
    owner, admin_headers = await _seed(db_session, "-personal")
    agent_a, headers_a = await _add_agent(
        db_session, owner.account, email="a@tpl.example.com", name="Agente A"
    )
    _agent_b, headers_b = await _add_agent(
        db_session, owner.account, email="b@tpl.example.com", name="Agente B"
    )
    base_org = _url(owner.account.id)
    base_personal = f"{base_org}/personal"

    # Organisation templates remain admin-only (401 not_authorized per Chatwoot parity).
    org_post = await client.post(
        base_org,
        headers=headers_a,
        json={"name": "No permitido", "template_html": "<p>{{contenido}}</p>"},
    )
    assert org_post.status_code == 401
    assert org_post.json()["code"] == "not_authorized"
    org_get = await client.get(base_org, headers=headers_a)
    assert org_get.status_code == 401
    assert org_get.json()["code"] == "not_authorized"

    # Agent A creates a personal template and marks it as default.
    created = await client.post(
        base_personal,
        headers=headers_a,
        json={
            "name": "Mi estilo",
            "template_html": '<div style="color:#123">{{contenido}}</div>',
            "is_default": True,
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["scope"] == "personal"
    assert body["user_id"] == agent_a.id
    assert body["is_default"] is True
    tid = body["id"]

    # Agent A sees their own template; Agent B sees none and gets 404 on A's id.
    list_a = (await client.get(base_personal, headers=headers_a)).json()["payload"]
    assert [t["id"] for t in list_a] == [tid]
    list_b = (await client.get(base_personal, headers=headers_b)).json()["payload"]
    assert list_b == []
    assert (await client.get(f"{base_personal}/{tid}", headers=headers_b)).status_code == 404
    assert (
        await client.patch(f"{base_personal}/{tid}", headers=headers_b, json={"name": "Robada"})
    ).status_code == 404

    # Admin does NOT see personal templates in the organisation list, and can
    # create an org template with the exact same name without colliding.
    org_same_name = await client.post(
        base_org,
        headers=admin_headers,
        json={"name": "Mi estilo", "template_html": "<p>{{contenido}}</p>"},
    )
    assert org_same_name.status_code == 200, org_same_name.text


async def test_reply_template_precedence_personal_default_beats_mailbox(db_session):
    owner, _ = await _seed(db_session, "-prec")
    agent, _ = await _add_agent(db_session, owner.account, email="rep@tpl.example.com", name="Rep")
    _inbox, channel = await _email_inbox(
        db_session,
        owner,
        "-prec",
        template_html="<p>Bandeja {{contenido}}</p>",
    )
    org_tpl = await svc.create_template(
        db_session,
        account_id=owner.account.id,
        name="Org",
        template_html="<p>Org {{contenido}}</p>",
    )
    channel.email_template_id = org_tpl.id
    db_session.add(channel)
    await db_session.flush()

    # Without a personal default, mailbox's linked org template wins.
    assert (
        await svc.resolve_html(
            db_session,
            channel=channel,
            account_id=owner.account.id,
            sender_user_id=agent.id,
        )
        == "<p>Org {{contenido}}</p>"
    )

    # A non-default personal template does NOT override the mailbox.
    p1 = await svc.create_template(
        db_session,
        account_id=owner.account.id,
        user_id=agent.id,
        name="Opcional",
        template_html="<p>Opcional {{contenido}}</p>",
        is_default=False,
    )
    assert (
        await svc.resolve_html(
            db_session,
            channel=channel,
            account_id=owner.account.id,
            sender_user_id=agent.id,
        )
        == "<p>Org {{contenido}}</p>"
    )

    # Marking p1 as default makes it win over the mailbox template.
    await svc.update_template(db_session, template=p1, updates={"is_default": True})
    assert (
        await svc.resolve_html(
            db_session,
            channel=channel,
            account_id=owner.account.id,
            sender_user_id=agent.id,
        )
        == "<p>Opcional {{contenido}}</p>"
    )

    # Setting a second personal template as default clears the first one.
    p2 = await svc.create_template(
        db_session,
        account_id=owner.account.id,
        user_id=agent.id,
        name="Nueva por defecto",
        template_html="<p>Segunda {{contenido}}</p>",
        is_default=True,
    )
    await db_session.refresh(p1)
    assert p1.is_default is False
    assert p2.is_default is True
    assert (
        await svc.resolve_html(
            db_session,
            channel=channel,
            account_id=owner.account.id,
            sender_user_id=agent.id,
        )
        == "<p>Segunda {{contenido}}</p>"
    )


# ---------------------------------------------------------------------------
# Server-side sanitization on save
# ---------------------------------------------------------------------------
async def test_saving_template_sanitizes_malicious_html(client, db_session):
    owner, headers = await _seed(db_session, "-xss")
    resp = await client.post(
        _url(owner.account.id),
        headers=headers,
        json={
            "name": "Maliciosa",
            "template_html": (
                '<div onclick="alert(1)"><script>steal()</script>'
                '<iframe src="https://evil.test"></iframe>'
                '<a href="javascript:alert(2)">Link</a>'
                "{{contenido}}</div>"
            ),
        },
    )
    assert resp.status_code == 200, resp.text
    html = resp.json()["template_html"]
    assert "<script" not in html.lower()
    assert "<iframe" not in html.lower()
    assert "onclick" not in html.lower()
    assert "javascript:" not in html.lower()
    assert "{{contenido}}" in html


# ---------------------------------------------------------------------------
# Organisation & user signatures (CRUD, variables, fallback to message_signature)
# ---------------------------------------------------------------------------
async def test_org_and_personal_signatures_and_legacy_fallback(client, db_session):
    owner, admin_headers = await _seed(db_session, "-sigs")
    agent, agent_headers = await _add_agent(
        db_session,
        owner.account,
        email="lucia@tpl.example.com",
        name="Lucía Gómez",
        job_title="Ejecutiva de cuentas",
    )
    agent.message_signature = "Lucía <legacy>\nSoporte"
    db_session.add(agent)
    await db_session.flush()

    sig_base = f"/api/v1/accounts/{owner.account.id}/email_signatures"

    # Non-admin cannot edit the organisation signature.
    denied_sig = await client.put(
        f"{sig_base}/organization",
        headers=agent_headers,
        json={"signature_html": "<p>No</p>"},
    )
    assert denied_sig.status_code == 401
    assert denied_sig.json()["code"] == "not_authorized"

    # Admin saves the organisation signature (malicious tags stripped).
    org_resp = await client.put(
        f"{sig_base}/organization",
        headers=admin_headers,
        json={
            "signature_html": (
                '<table style="color:#003366"><tr><td><script>x()</script>'
                "<strong>Acme Corp</strong></td></tr></table>"
            ),
            "signature_text": "Acme Corp",
        },
    )
    assert org_resp.status_code == 200, org_resp.text
    assert "<script" not in org_resp.json()["signature_html"].lower()

    # Before agent creates a rich signature, resolve_signatures falls back to
    # their legacy plain-text ``message_signature`` (escaped).
    resolved_before = await sig_svc.resolve_signatures(
        db_session, account_id=owner.account.id, user=agent, channel=None
    )
    assert resolved_before.user_html == "Lucía &lt;legacy&gt;<br>Soporte"
    assert "Acme Corp" in resolved_before.org_html

    # Agent saves a rich personal signature using profile variables.
    pers_resp = await client.put(
        f"{sig_base}/personal",
        headers=agent_headers,
        json={
            "signature_html": (
                "<div><strong>{{nombre}}</strong> · {{cargo}}<br>{{correo}} · {{telefono}}</div>"
            ),
            "signature_text": "{{nombre}} - {{cargo}}",
        },
    )
    assert pers_resp.status_code == 200, pers_resp.text

    resolved_after = await sig_svc.resolve_signatures(
        db_session, account_id=owner.account.id, user=agent, channel=None
    )
    assert "<strong>Lucía Gómez</strong>" in resolved_after.user_html
    assert "Ejecutiva de cuentas" in resolved_after.user_html
    assert "lucia@tpl.example.com" in resolved_after.user_html
    assert "+598 99 000 111" in resolved_after.user_html
    assert resolved_after.user_plain == "Lucía Gómez - Ejecutiva de cuentas"


# ---------------------------------------------------------------------------
# AI design endpoint (respx): success & ai_down fallback
# ---------------------------------------------------------------------------
@respx.mock
async def test_ai_generate_route_returns_sanitized_html_and_handles_ai_down(
    client, db_session, monkeypatch
):
    owner, _ = await _seed(db_session, "-ai")
    _agent, agent_headers = await _add_agent(
        db_session, owner.account, email="ai@tpl.example.com", name="Agente IA"
    )
    s = get_settings()
    monkeypatch.setattr(s, "openai_api_key", "")
    monkeypatch.setattr(s, "local_llm_url", "https://api.groq.com/openai")
    monkeypatch.setattr(s, "local_llm_api_key", "groq-key")
    monkeypatch.setattr(s, "local_llm_model", "llama-3.3-70b")
    monkeypatch.setattr(s, "local_llm_fallback_url", "")

    url = f"{_url(owner.account.id)}/generate"

    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"html": "<div><script>x()</script>{{contenido}}</div>", '
                                '"notes": "Plantilla lista."}'
                            )
                        }
                    }
                ]
            },
        )
    )
    ok_resp = await client.post(
        url,
        headers=agent_headers,
        json={"prompt": "Membrete azul", "kind": "template"},
    )
    assert ok_resp.status_code == 200, ok_resp.text
    data = ok_resp.json()
    assert "{{contenido}}" in data["html"]
    assert "<script" not in data["html"].lower()
    assert data["notes"] == "Plantilla lista."

    # Provider outage → 503 with exact ai_down code & message.
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(503, text="down")
    )
    down_resp = await client.post(
        url,
        headers=agent_headers,
        json={"prompt": "Membrete azul", "kind": "template"},
    )
    assert down_resp.status_code == 503
    assert down_resp.json()["code"] == "email_ai.ai_down"
    assert down_resp.json()["message"] == "Servicios de AI temporalmente fuera, intenta mañana"
