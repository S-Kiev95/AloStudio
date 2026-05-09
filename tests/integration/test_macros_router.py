"""Integration tests for Macros — CRUD, visibility scoping, execute.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/macros_controller.rb
  reference/chatwoot/app/policies/macro_policy.rb
  reference/chatwoot/app/services/macros/execution_service.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.models import (
    CONVERSATION_STATUS_RESOLVED,
    Conversation,
    Message,
    MESSAGE_TYPE_OUTGOING,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    create_conversation,
)
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.macros.models import Macro
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_AGENT,
    AccountUser,
)
from app.main import app

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
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


async def _seed_admin(db_session, suffix: str = ""):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@macros.example.com",
            account_name=f"Macros{suffix}",
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


async def _seed_agent_member(db_session, owner_account, suffix: str):
    """Add a non-admin agent to ``owner_account``. Returns (user, headers)."""
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agent{suffix}@macros.example.com",
            account_name=f"Other{suffix}",
            user_full_name=f"Agent{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner_account.id,
            user_id=agent.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    await db_session.flush()
    headers, new_tokens = create_new_auth_token(
        user_tokens=agent.user.tokens, uid=agent.user.uid
    )
    agent.user.tokens = new_tokens
    db_session.add(agent.user)
    await db_session.flush()
    return agent, headers.as_response_headers()


async def _seed_conversation(db_session, owner) -> Conversation:
    inbox = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="API",
            channel_type="api",
            channel_params={"webhook_url": "https://x.example.com"},
        ),
    ).perform()
    contact = Contact(account_id=owner.account.id, name="X")
    db_session.add(contact)
    await db_session.flush()
    ci = await ContactInboxBuilder(
        session=db_session,
        contact=contact,
        inbox=inbox.inbox,
        source_id=f"src-{contact.id}",
    ).perform()
    return await create_conversation(
        db_session,
        contact_inbox=ci,
        params=ConversationBuilderParams(),
    )


# ---------------------------------------------------------------------------
# Auth + index visibility
# ---------------------------------------------------------------------------
async def test_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/macros")
    assert resp.status_code == 401


async def test_index_empty_envelope(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-ix0")
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/macros", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json() == {"payload": []}


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
async def test_create_admin_global_macro(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-cr1")
    body = {
        "name": "Resolve VIP",
        "visibility": "global",
        "actions": [
            {"action_name": "resolve_conversation", "action_params": []},
            {"action_name": "add_label", "action_params": ["vip"]},
        ],
    }
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()["payload"]
    assert payload["name"] == "Resolve VIP"
    assert payload["visibility"] == "global"
    assert payload["account_id"] == owner.account.id
    assert payload["actions"] == body["actions"]
    assert payload["created_by"]["email"] == owner.user.email
    assert payload["updated_by"]["email"] == owner.user.email


async def test_create_agent_clamped_to_personal(client, db_session):
    owner, _ = await _seed_admin(db_session, suffix="-cl")
    agent, agent_headers = await _seed_agent_member(
        db_session, owner.account, suffix="-cl"
    )
    body = {
        "name": "Tries to be global",
        "visibility": "global",  # ignored — clamped
        "actions": [{"action_name": "mute_conversation", "action_params": []}],
    }
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json=body,
        headers=agent_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["payload"]["visibility"] == "personal"


async def test_create_rejects_unknown_action(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-rej")
    body = {
        "name": "Bad",
        "actions": [{"action_name": "frobnicate", "action_params": []}],
    }
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 422
    assert "frobnicate" in resp.json()["message"]
    assert "not supported" in resp.json()["message"]


async def test_create_rejects_blank_name(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-bn")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json={"name": "", "actions": []},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "blank" in resp.json()["message"].lower()


# ---------------------------------------------------------------------------
# Visibility scoping (index + show)
# ---------------------------------------------------------------------------
async def test_index_hides_other_users_personal_macros(client, db_session):
    """Two users in the same account each have a personal macro;
    each sees only their own + any global ones."""
    owner, owner_headers = await _seed_admin(db_session, suffix="-vp")
    agent, agent_headers = await _seed_agent_member(
        db_session, owner.account, suffix="-vp"
    )
    # Owner creates a global + a personal.
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json={
            "name": "Shared",
            "visibility": "global",
            "actions": [{"action_name": "mute_conversation", "action_params": []}],
        },
        headers=owner_headers,
    )
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json={
            "name": "Owner-only",
            "visibility": "personal",
            "actions": [],
        },
        headers=owner_headers,
    )
    # Agent creates one personal macro.
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json={"name": "Agent-only", "actions": []},
        headers=agent_headers,
    )

    owner_view = (
        await client.get(
            f"/api/v1/accounts/{owner.account.id}/macros", headers=owner_headers
        )
    ).json()["payload"]
    agent_view = (
        await client.get(
            f"/api/v1/accounts/{owner.account.id}/macros", headers=agent_headers
        )
    ).json()["payload"]
    owner_names = {m["name"] for m in owner_view}
    agent_names = {m["name"] for m in agent_view}
    assert owner_names == {"Shared", "Owner-only"}
    assert agent_names == {"Shared", "Agent-only"}


async def test_show_blocks_other_users_personal(client, db_session):
    owner, owner_headers = await _seed_admin(db_session, suffix="-sh")
    agent, agent_headers = await _seed_agent_member(
        db_session, owner.account, suffix="-sh"
    )
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json={"name": "Owner-private", "actions": []},
        headers=owner_headers,
    )
    mid = create.json()["payload"]["id"]
    blocked = await client.get(
        f"/api/v1/accounts/{owner.account.id}/macros/{mid}",
        headers=agent_headers,
    )
    assert blocked.status_code == 401


# ---------------------------------------------------------------------------
# Update / destroy
# ---------------------------------------------------------------------------
async def test_update_by_author(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-up")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json={"name": "first", "actions": []},
        headers=headers,
    )
    mid = create.json()["payload"]["id"]
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/macros/{mid}",
        json={"name": "second"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["payload"]["name"] == "second"


async def test_update_blocked_for_non_author_agent(client, db_session):
    owner, owner_headers = await _seed_admin(db_session, suffix="-bk")
    agent, agent_headers = await _seed_agent_member(
        db_session, owner.account, suffix="-bk"
    )
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json={
            "name": "global-by-admin",
            "visibility": "global",
            "actions": [],
        },
        headers=owner_headers,
    )
    mid = create.json()["payload"]["id"]
    blocked = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/macros/{mid}",
        json={"name": "agent-attempt"},
        headers=agent_headers,
    )
    assert blocked.status_code == 401


async def test_destroy_returns_200_empty(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-dl")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json={"name": "trash", "actions": []},
        headers=headers,
    )
    mid = create.json()["payload"]["id"]
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/macros/{mid}", headers=headers
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------
async def test_execute_resolves_and_labels(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-ex")
    conv = await _seed_conversation(db_session, owner)

    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json={
            "name": "Resolve+tag",
            "visibility": "global",
            "actions": [
                {"action_name": "add_label", "action_params": ["urgent"]},
                {"action_name": "resolve_conversation", "action_params": []},
            ],
        },
        headers=headers,
    )
    mid = create.json()["payload"]["id"]
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros/{mid}/execute",
        json={"conversation_ids": [conv.id]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    fresh = await db_session.get(Conversation, conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    assert fresh.status == CONVERSATION_STATUS_RESOLVED
    assert (fresh.cached_label_list or "").split(",") == ["urgent"]


async def test_execute_send_message_creates_outgoing(client, db_session):
    owner, headers = await _seed_admin(db_session, suffix="-msg")
    conv = await _seed_conversation(db_session, owner)
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json={
            "name": "Auto-greet",
            "visibility": "global",
            "actions": [
                {"action_name": "send_message", "action_params": ["hello!"]}
            ],
        },
        headers=headers,
    )
    mid = create.json()["payload"]["id"]
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros/{mid}/execute",
        json={"conversation_ids": [conv.id]},
        headers=headers,
    )
    assert resp.status_code == 200
    msgs = list(
        (
            await db_session.exec(
                select(Message).where(Message.conversation_id == conv.id)
            )
        ).all()
    )
    outgoing = [m for m in msgs if m.message_type == MESSAGE_TYPE_OUTGOING]
    assert len(outgoing) == 1
    assert outgoing[0].content == "hello!"
    assert outgoing[0].private is False


async def test_execute_unauthorized_for_non_visible_macro(client, db_session):
    owner, owner_headers = await _seed_admin(db_session, suffix="-unx")
    agent, agent_headers = await _seed_agent_member(
        db_session, owner.account, suffix="-unx"
    )
    conv = await _seed_conversation(db_session, owner)
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json={"name": "owner-private", "actions": []},
        headers=owner_headers,
    )
    mid = create.json()["payload"]["id"]
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros/{mid}/execute",
        json={"conversation_ids": [conv.id]},
        headers=agent_headers,
    )
    assert resp.status_code == 401


async def test_execute_skips_other_account_conversations(client, db_session):
    """``conversation_ids`` from a different account silently no-op
    (Rails scopes to ``Current.account.conversations``)."""
    owner, headers = await _seed_admin(db_session, suffix="-iso")
    other = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="other@macros.example.com",
            account_name="Other",
            user_full_name="Other",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    other_conv = await _seed_conversation(db_session, other)

    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros",
        json={
            "name": "Cross-account",
            "visibility": "global",
            "actions": [
                {"action_name": "resolve_conversation", "action_params": []}
            ],
        },
        headers=headers,
    )
    mid = create.json()["payload"]["id"]
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/macros/{mid}/execute",
        json={"conversation_ids": [other_conv.id]},
        headers=headers,
    )
    assert resp.status_code == 200
    fresh = await db_session.get(Conversation, other_conv.id)
    assert fresh is not None
    await db_session.refresh(fresh)
    # Other-account conversation untouched.
    assert fresh.status != CONVERSATION_STATUS_RESOLVED
