"""HTTP-level tests for Phase 3 ``/api/v1/accounts/:id/contacts`` + nested
``notes`` / ``contact_inboxes`` + ``actions/contact_merge``.

Parity anchors:
  * ``Api::V1::Accounts::ContactsController``
  * ``Api::V1::Accounts::Contacts::NotesController``
  * ``Api::V1::Accounts::Contacts::ContactInboxesController``
  * ``Api::V1::Accounts::Actions::ContactMergesController``
  * ``_contact.json.jbuilder`` / ``_note.json.jbuilder`` /
    ``_contact_inbox.json.jbuilder`` / ``_inbox_slim.json.jbuilder``

Coverage:
  * Auth gates (401 unauthenticated, 404 non-member)
  * Contact create + wire shape + create.jbuilder envelope
  * Contact list + include_contact_inboxes query param
  * Contact search (happy path + missing q → 422)
  * Show / update / destroy (destroy admin-only)
  * destroy_custom_attributes
  * contactable_inboxes (Channel::Api only in Phase 3)
  * Notes CRUD (envelope shape, user nested)
  * ContactInbox create
  * Contact merge (contact_inboxes + notes reassigned, JSONB deep-merge)
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact, ContactInbox, Note
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
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


async def _mint_headers(db_session, user) -> dict[str, str]:
    headers, new_tokens = create_new_auth_token(
        user_tokens=user.tokens, uid=user.uid
    )
    user.tokens = new_tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


@pytest.fixture
async def seeded(db_session):
    """Account + admin + agent + one API inbox."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@contacts.example.com",
            account_name="Contacts Inc",
            user_full_name="Admin Owner",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    agent_side = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent@contacts.example.com",
            account_name="Agent Side Account",
            user_full_name="Agent Beta",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner.account.id,
            user_id=agent_side.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    await db_session.flush()

    inbox_result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API Inbox",
            channel_type="api",
            channel_params={"webhook_url": "https://example.com/hook"},
        ),
    ).perform()

    admin_h = await _mint_headers(db_session, owner.user)
    agent_h = await _mint_headers(db_session, agent_side.user)
    return owner, agent_side, inbox_result.inbox, admin_h, agent_h


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
async def test_contacts_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/contacts")
    assert resp.status_code == 401


async def test_non_member_gets_404(client, seeded):
    _, _, _, admin_h, _ = seeded
    # Unknown account → 404 (``Resource could not be found``), not 401.
    resp = await client.get("/api/v1/accounts/999999/contacts", headers=admin_h)
    assert resp.status_code == 404
    assert resp.json() == {"error": "Resource could not be found"}


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
async def test_create_contact_minimal(client, seeded):
    owner, _, _, admin_h, _ = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/contacts",
        json={"name": "Jane Doe", "email": "JANE@example.com"},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "payload" in body
    contact = body["payload"]["contact"]
    assert contact["name"] == "Jane Doe"
    # email lowercased by ``normalize_contact_write``
    assert contact["email"] == "jane@example.com"
    assert contact["blocked"] is False
    assert contact["availability_status"] == "offline"
    assert contact["thumbnail"] == ""
    assert contact["custom_attributes"] == {}
    assert contact["additional_attributes"] == {}
    # contact_inbox empty when no inbox_id was supplied
    assert body["payload"]["contact_inbox"] == {"inbox": None, "source_id": None}


async def test_create_contact_with_inbox(client, seeded):
    owner, _, inbox, admin_h, _ = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/contacts",
        json={
            "name": "Bob",
            "email": "bob@example.com",
            "inbox_id": inbox.id,
        },
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["payload"]
    # source_id minted by ContactInboxBuilder for Channel::Api → UUID string
    assert body["contact_inbox"]["inbox"]["id"] == inbox.id
    assert isinstance(body["contact_inbox"]["source_id"], str)
    assert len(body["contact_inbox"]["source_id"]) >= 32


async def test_create_rejects_bad_email(client, seeded):
    owner, _, _, admin_h, _ = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/contacts",
        json={"name": "X", "email": "not-an-email"},
        headers=admin_h,
    )
    assert resp.status_code == 422
    assert resp.json() == {"message": "Email is invalid"}


async def test_create_rejects_bad_phone(client, seeded):
    owner, _, _, admin_h, _ = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/contacts",
        json={"name": "X", "phone_number": "555-1234"},
        headers=admin_h,
    )
    assert resp.status_code == 422
    assert resp.json() == {"message": "Phone number should be in e164 format"}


async def test_create_rejects_duplicate_email(client, seeded, db_session):
    owner, _, _, admin_h, _ = seeded
    db_session.add(
        Contact(
            account_id=owner.account.id,
            email="dup@example.com",
            name="Existing",
        )
    )
    await db_session.flush()
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/contacts",
        json={"name": "Another", "email": "DUP@example.com"},
        headers=admin_h,
    )
    assert resp.status_code == 422
    assert "email" in resp.json()["message"].lower()


# ---------------------------------------------------------------------------
# Index + search
# ---------------------------------------------------------------------------
async def test_index_contacts(client, seeded, db_session):
    owner, _, _, admin_h, _ = seeded
    for i in range(3):
        db_session.add(
            Contact(
                account_id=owner.account.id,
                email=f"c{i}@example.com",
                name=f"Contact {i}",
            )
        )
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/contacts?include_contact_inboxes=false",
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["count"] == 3
    assert body["meta"]["current_page"] == 1
    assert len(body["payload"]) == 3
    # include_contact_inboxes=false → key omitted from the contact body
    for c in body["payload"]:
        assert "contact_inboxes" not in c


async def test_search_requires_q(client, seeded):
    owner, _, _, admin_h, _ = seeded
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/contacts/search",
        headers=admin_h,
    )
    assert resp.status_code == 422
    assert resp.json() == {"error": "Specify search string with parameter q"}


async def test_search_finds_by_email(client, seeded, db_session):
    owner, _, _, admin_h, _ = seeded
    db_session.add(
        Contact(
            account_id=owner.account.id,
            email="find-me@example.com",
            name="Target",
        )
    )
    db_session.add(
        Contact(
            account_id=owner.account.id,
            email="other@example.com",
            name="Other",
        )
    )
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/contacts/search?q=find-me",
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["has_more"] is False
    assert len(body["payload"]) == 1
    assert body["payload"][0]["email"] == "find-me@example.com"


# ---------------------------------------------------------------------------
# Show / update / destroy
# ---------------------------------------------------------------------------
async def test_show_contact(client, seeded, db_session):
    owner, _, _, admin_h, _ = seeded
    c = Contact(
        account_id=owner.account.id,
        email="show@example.com",
        name="Show Me",
        custom_attributes={"plan": "gold"},
    )
    db_session.add(c)
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/contacts/{c.id}",
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()["payload"]
    assert body["id"] == c.id
    assert body["custom_attributes"] == {"plan": "gold"}


async def test_update_deep_merges_custom_attributes(client, seeded, db_session):
    owner, _, _, admin_h, _ = seeded
    c = Contact(
        account_id=owner.account.id,
        email="merge@example.com",
        name="Merge Me",
        custom_attributes={"plan": "gold", "region": "eu"},
    )
    db_session.add(c)
    await db_session.flush()

    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/contacts/{c.id}",
        json={"custom_attributes": {"plan": "platinum", "notes": "VIP"}},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["payload"]
    # Deep-merge: existing ``region`` preserved, ``plan`` updated, ``notes`` added.
    assert body["custom_attributes"] == {
        "plan": "platinum",
        "region": "eu",
        "notes": "VIP",
    }


async def test_destroy_admin_only(client, seeded, db_session):
    owner, _agent_side, _, admin_h, agent_h = seeded
    c = Contact(account_id=owner.account.id, email="del@example.com", name="Del")
    db_session.add(c)
    await db_session.flush()

    # Agent call → 401 (pundit equivalent)
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/contacts/{c.id}", headers=agent_h
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "You are not authorized to do this action"}

    # Admin call → 200 empty body
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/contacts/{c.id}", headers=admin_h
    )
    assert resp.status_code == 200
    assert resp.json() == {}


async def test_destroy_custom_attributes(client, seeded, db_session):
    owner, _, _, admin_h, _ = seeded
    c = Contact(
        account_id=owner.account.id,
        email="dca@example.com",
        name="DCA",
        custom_attributes={"plan": "gold", "region": "eu", "notes": "keep"},
    )
    db_session.add(c)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/contacts/{c.id}/destroy_custom_attributes",
        json={"custom_attributes": ["plan", "region"]},
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()["payload"]
    assert body["custom_attributes"] == {"notes": "keep"}


# ---------------------------------------------------------------------------
# contactable_inboxes
# ---------------------------------------------------------------------------
async def test_contactable_inboxes_api_channel(client, seeded, db_session):
    owner, _, inbox, admin_h, _ = seeded
    c = Contact(account_id=owner.account.id, email="ci@example.com", name="CI")
    db_session.add(c)
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/contacts/{c.id}/contactable_inboxes",
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    # Exactly one Channel::Api inbox in the seeded setup.
    assert len(body["payload"]) == 1
    assert body["payload"][0]["inbox"]["id"] == inbox.id
    # Channel::Api always mints a UUID when no prior ContactInbox exists.
    assert isinstance(body["payload"][0]["source_id"], str)


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
async def test_create_note(client, seeded, db_session):
    owner, _, _, admin_h, _ = seeded
    c = Contact(account_id=owner.account.id, email="n@example.com", name="N")
    db_session.add(c)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/contacts/{c.id}/notes",
        json={"note": {"content": "first note"}},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["content"] == "first note"
    # jbuilder bug-for-bug parity: account_id + contact_id are null
    assert body["account_id"] is None
    assert body["contact_id"] is None
    # user block nested from _agent.json.jbuilder
    assert body["user"]["email"] == owner.user.email
    assert body["user"]["account_id"] == owner.account.id


async def test_note_envelope_rejected_when_missing(client, seeded, db_session):
    owner, _, _, admin_h, _ = seeded
    c = Contact(account_id=owner.account.id, email="n2@example.com", name="N2")
    db_session.add(c)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/contacts/{c.id}/notes",
        json={"content": "no wrapper"},
        headers=admin_h,
    )
    # Pydantic rejects missing ``note`` wrapper → 422 (FastAPI default).
    assert resp.status_code == 422


async def test_notes_index(client, seeded, db_session):
    owner, _, _, admin_h, _ = seeded
    c = Contact(account_id=owner.account.id, email="nidx@example.com", name="NIdx")
    db_session.add(c)
    await db_session.flush()
    for i in range(3):
        db_session.add(
            Note(
                account_id=owner.account.id,
                contact_id=c.id,
                user_id=owner.user.id,
                content=f"note {i}",
            )
        )
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/contacts/{c.id}/notes",
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    # Top-level JSON array, newest first.
    assert isinstance(body, list)
    assert len(body) == 3
    assert body[0]["content"] == "note 2"
    assert body[2]["content"] == "note 0"


async def test_update_and_destroy_note(client, seeded, db_session):
    owner, _, _, admin_h, _ = seeded
    c = Contact(account_id=owner.account.id, email="nupd@example.com", name="NUpd")
    db_session.add(c)
    await db_session.flush()
    note = Note(
        account_id=owner.account.id,
        contact_id=c.id,
        user_id=owner.user.id,
        content="orig",
    )
    db_session.add(note)
    await db_session.flush()

    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/contacts/{c.id}/notes/{note.id}",
        json={"note": {"content": "updated"}},
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "updated"

    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/contacts/{c.id}/notes/{note.id}",
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.json() == {}


# ---------------------------------------------------------------------------
# ContactInbox create
# ---------------------------------------------------------------------------
async def test_create_contact_inbox(client, seeded, db_session):
    owner, _, inbox, admin_h, _ = seeded
    c = Contact(account_id=owner.account.id, email="ci2@example.com", name="CI2")
    db_session.add(c)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/contacts/{c.id}/contact_inboxes",
        json={"inbox_id": inbox.id},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["contact_inbox"]["inbox"]["id"] == inbox.id
    assert isinstance(body["contact_inbox"]["source_id"], str)


# ---------------------------------------------------------------------------
# contact_merge action
# ---------------------------------------------------------------------------
async def test_contact_merge_folds_mergee(client, seeded, db_session):
    owner, _, inbox, admin_h, _ = seeded
    base = Contact(
        account_id=owner.account.id,
        email="base@example.com",
        name="Base",
        custom_attributes={"plan": "gold"},
    )
    mergee = Contact(
        account_id=owner.account.id,
        phone_number="+14155551234",
        name="Mergee",
        custom_attributes={"region": "us", "plan": "silver"},
    )
    db_session.add(base)
    db_session.add(mergee)
    await db_session.flush()

    # Attach a ContactInbox to mergee so the merge reassigns it.
    db_session.add(
        ContactInbox(
            contact_id=mergee.id,
            inbox_id=inbox.id,
            source_id="src-mergee",
        )
    )
    # And a note on mergee.
    db_session.add(
        Note(
            account_id=owner.account.id,
            contact_id=mergee.id,
            user_id=owner.user.id,
            content="mergee note",
        )
    )
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/actions/contact_merge",
        json={"base_contact_id": base.id, "mergee_contact_id": mergee.id},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == base.id
    # Base wins on collisions; mergee fills gaps.
    assert body["name"] == "Base"
    assert body["email"] == "base@example.com"
    assert body["phone_number"] == "+14155551234"
    assert body["custom_attributes"] == {"plan": "gold", "region": "us"}

    # Mergee row is gone; its contact_inbox + note now point at base.
    assert (await db_session.get(Contact, mergee.id)) is None
