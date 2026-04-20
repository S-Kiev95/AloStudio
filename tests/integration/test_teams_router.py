"""HTTP-level tests for ``/api/v1/accounts/:id/teams`` + nested
``team_members``.

Parity anchors:
  * ``Api::V1::Accounts::TeamsController`` + ``TeamPolicy``
  * ``Api::V1::Accounts::TeamMembersController``
  * ``_team.json.jbuilder`` + ``_agent.json.jbuilder`` partials

Coverage:
  * admin happy paths: create / show / index / update / destroy
  * agent read-only (index + show allowed; mutations 401)
  * name lowercasing (before_validation hook)
  * uniqueness error shape — 422 ``{"message": "Name has already been taken"}``
  * team_members list / add / replace (PATCH) / remove
  * ``is_member`` flag per-row on list + show
  * non-member validation → 401 ``{"error": "Invalid User IDs"}``
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
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


async def _mint_headers(db_session, user) -> dict[str, str]:
    """Rotate an auth token for ``user`` and return devise-token-auth headers."""
    headers, new_tokens = create_new_auth_token(
        user_tokens=user.tokens, uid=user.uid
    )
    user.tokens = new_tokens
    db_session.add(user)
    await db_session.flush()
    return headers.as_response_headers()


@pytest.fixture
async def seeded(db_session):
    """Admin + extra agent in the same account. Returns (admin_owner, agent, agent_headers, admin_headers)."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@teams.example.com",
            account_name="Teams Inc",
            user_full_name="Admin Owner",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()

    # Second user built via AccountBuilder (own account) then linked as
    # agent on the owner's account.
    side = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent@teams.example.com",
            account_name="Agent Side Account",
            user_full_name="Agent Beta",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner.account.id,
            user_id=side.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    await db_session.flush()

    admin_headers = await _mint_headers(db_session, owner.user)
    agent_headers = await _mint_headers(db_session, side.user)
    return owner, side, admin_headers, agent_headers


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------
async def test_teams_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/teams")
    assert resp.status_code == 401


async def test_teams_create_requires_auth(client):
    resp = await client.post("/api/v1/accounts/1/teams", json={"name": "x"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Create + wire shape
# ---------------------------------------------------------------------------
async def test_admin_creates_team_name_is_lowercased(client, seeded):
    owner, _, admin_h, _ = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/teams",
        json={"name": "Support", "description": "front line"},
        headers=admin_h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Rails ``before_validation { self.name = name.downcase }``
    assert body["name"] == "support"
    assert body["description"] == "front line"
    assert body["account_id"] == owner.account.id
    assert body["allow_auto_assign"] is True
    # Creator is not auto-joined.
    assert body["is_member"] is False
    # ID populated.
    assert isinstance(body["id"], int)


async def test_agent_cannot_create_team(client, seeded):
    owner, _, _, agent_h = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/teams",
        json={"name": "forbidden"},
        headers=agent_h,
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "You are not authorized to do this action"}


async def test_duplicate_team_name_422(client, seeded):
    owner, _, admin_h, _ = seeded
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/teams",
        json={"name": "ops"},
        headers=admin_h,
    )
    # Uniqueness is scoped to (name, account_id); same account_id + "ops"
    # should hit the constraint. ``"OPS"`` lowercases to the same row.
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/teams",
        json={"name": "OPS"},
        headers=admin_h,
    )
    assert resp.status_code == 422
    assert resp.json() == {"message": "Name has already been taken"}


async def test_create_with_allow_auto_assign_false(client, seeded):
    owner, _, admin_h, _ = seeded
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/teams",
        json={"name": "vip", "allow_auto_assign": False},
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.json()["allow_auto_assign"] is False


# ---------------------------------------------------------------------------
# Index / Show
# ---------------------------------------------------------------------------
async def test_teams_index_is_top_level_array(client, seeded):
    owner, _, admin_h, _ = seeded
    # Seed two teams.
    for name in ["alpha", "beta"]:
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/teams",
            json={"name": name},
            headers=admin_h,
        )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/teams", headers=admin_h
    )
    assert resp.status_code == 200
    body = resp.json()
    # Chatwoot jbuilder: ``json.array!`` — top-level array, not wrapped.
    assert isinstance(body, list)
    assert {row["name"] for row in body} == {"alpha", "beta"}
    # Admin isn't a member of anything yet.
    assert all(row["is_member"] is False for row in body)


async def test_agent_can_read_teams(client, seeded):
    """``TeamPolicy#index?`` = true — both roles read."""
    owner, _, admin_h, agent_h = seeded
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/teams",
        json={"name": "shared"},
        headers=admin_h,
    )
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/teams", headers=agent_h
    )
    assert resp.status_code == 200
    assert [t["name"] for t in resp.json()] == ["shared"]


async def test_show_team_returns_single_object(client, seeded):
    owner, _, admin_h, _ = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/teams",
            json={"name": "billing"},
            headers=admin_h,
        )
    ).json()

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}",
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]
    assert resp.json()["name"] == "billing"


async def test_show_team_404_when_not_in_account(client, seeded):
    owner, _, admin_h, _ = seeded
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/teams/999999",
        headers=admin_h,
    )
    assert resp.status_code == 404
    assert resp.json() == {"error": "Resource could not be found"}


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
async def test_admin_updates_team(client, seeded):
    owner, _, admin_h, _ = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/teams",
            json={"name": "old-name"},
            headers=admin_h,
        )
    ).json()
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}",
        json={"name": "New-Name", "description": "updated"},
        headers=admin_h,
    )
    assert resp.status_code == 200
    body = resp.json()
    # Lowercased on write.
    assert body["name"] == "new-name"
    assert body["description"] == "updated"


async def test_agent_cannot_update_team(client, seeded):
    owner, _, admin_h, agent_h = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/teams",
            json={"name": "locked"},
            headers=admin_h,
        )
    ).json()
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}",
        json={"name": "hijack"},
        headers=agent_h,
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Destroy
# ---------------------------------------------------------------------------
async def test_admin_destroys_team(client, seeded):
    owner, _, admin_h, _ = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/teams",
            json={"name": "gone"},
            headers=admin_h,
        )
    ).json()
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}",
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.json() == {}  # head :ok
    # And it's really gone.
    again = await client.get(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}",
        headers=admin_h,
    )
    assert again.status_code == 404


async def test_agent_cannot_destroy_team(client, seeded):
    owner, _, admin_h, agent_h = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/teams",
            json={"name": "sticky"},
            headers=admin_h,
        )
    ).json()
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}",
        headers=agent_h,
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# team_members
# ---------------------------------------------------------------------------
async def test_team_members_add_list_and_is_member_flag(client, seeded):
    owner, side, admin_h, _ = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/teams",
            json={"name": "escalations"},
            headers=admin_h,
        )
    ).json()

    # Add both users as members.
    add_resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}/team_members",
        json={"user_ids": [owner.user.id, side.user.id]},
        headers=admin_h,
    )
    assert add_resp.status_code == 200
    payload = add_resp.json()
    assert isinstance(payload, list)
    assert len(payload) == 2
    assert {a["id"] for a in payload} == {owner.user.id, side.user.id}

    # Show flips ``is_member`` for the current caller (admin).
    show = await client.get(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}",
        headers=admin_h,
    )
    assert show.json()["is_member"] is True

    # Plain GET on members returns the same shape.
    listing = await client.get(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}/team_members",
        headers=admin_h,
    )
    assert listing.status_code == 200
    assert {a["id"] for a in listing.json()} == {owner.user.id, side.user.id}


async def test_team_members_patch_replaces_set(client, seeded):
    owner, side, admin_h, _ = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/teams",
            json={"name": "rotating"},
            headers=admin_h,
        )
    ).json()
    # Start with just the owner.
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}/team_members",
        json={"user_ids": [owner.user.id]},
        headers=admin_h,
    )
    # Replace: only side agent should remain.
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}/team_members",
        json={"user_ids": [side.user.id]},
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert [a["id"] for a in resp.json()] == [side.user.id]


async def test_team_members_delete_removes_listed(client, seeded):
    owner, side, admin_h, _ = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/teams",
            json={"name": "trim"},
            headers=admin_h,
        )
    ).json()
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}/team_members",
        json={"user_ids": [owner.user.id, side.user.id]},
        headers=admin_h,
    )
    resp = await client.request(
        "DELETE",
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}/team_members",
        json={"user_ids": [side.user.id]},
        headers=admin_h,
    )
    assert resp.status_code == 200
    assert resp.json() == {}
    # Owner still there, side gone.
    listing = await client.get(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}/team_members",
        headers=admin_h,
    )
    assert [a["id"] for a in listing.json()] == [owner.user.id]


async def test_team_members_reject_non_account_user(client, seeded, db_session):
    owner, _, admin_h, _ = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/teams",
            json={"name": "gated"},
            headers=admin_h,
        )
    ).json()
    # Build a stranger user in a different account.
    stranger = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="stranger@outside.example.com",
            account_name="Outsider Corp",
            user_full_name="Stranger",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()

    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}/team_members",
        json={"user_ids": [stranger.user.id]},
        headers=admin_h,
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "Invalid User IDs"}


async def test_team_members_add_idempotent_over_duplicates(client, seeded):
    """Chatwoot's ``members_to_be_added_ids`` subtracts the current set, so
    sending the same user_ids twice is a no-op."""
    owner, _, admin_h, _ = seeded
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/teams",
            json={"name": "once-only"},
            headers=admin_h,
        )
    ).json()
    for _ in range(2):
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}/team_members",
            json={"user_ids": [owner.user.id]},
            headers=admin_h,
        )
    listing = await client.get(
        f"/api/v1/accounts/{owner.account.id}/teams/{created['id']}/team_members",
        headers=admin_h,
    )
    assert [a["id"] for a in listing.json()] == [owner.user.id]
