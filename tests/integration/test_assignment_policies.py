"""Integration tests for the AssignmentPolicy CRUD + inbox-link surface.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/assignment_policies_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/inboxes/assignment_policies_controller.rb
  reference/chatwoot/app/policies/assignment_policy_policy.rb  (admin-only)
  reference/chatwoot/app/models/assignment_policy.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
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


async def _seed_admin(db_session, suffix: str = ""):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@policy.example.com",
            account_name=f"Policy{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers = await _mint_headers(db_session, owner.user)
    return owner, headers


async def _seed_agent(db_session, owner, suffix: str = ""):
    """A second user, member of ``owner``'s account with the agent role."""
    side = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agent{suffix}@policy.example.com",
            account_name=f"Side{suffix}",
            user_full_name=f"Agent{suffix}",
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
    headers = await _mint_headers(db_session, side.user)
    return side, headers


async def _make_inbox(db_session, owner, name: str = "Policy Inbox"):
    return (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name=name,
                channel_type="api",
                channel_params={"webhook_url": "https://example.com/h"},
            ),
        ).perform()
    ).inbox


def _base(account_id: int) -> str:
    return f"/api/v1/accounts/{account_id}/assignment_policies"


def _inbox_base(account_id: int, inbox_id: int) -> str:
    return (
        f"/api/v1/accounts/{account_id}/inboxes/{inbox_id}/assignment_policy"
    )


async def _create(client, base, headers, name, **extra):
    return await client.post(
        base,
        json={"assignment_policy": {"name": name, **extra}},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
async def test_create_defaults_and_index_bare_array(client, db_session):
    owner, headers = await _seed_admin(db_session, "-idx")
    base = _base(owner.account.id)

    r1 = await _create(client, base, headers, "Balanced")
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert body["name"] == "Balanced"
    # Defaults surface as their string enum names + the numeric windows.
    assert body["enabled"] is True
    assert body["assignment_order"] == "round_robin"
    assert body["conversation_priority"] == "earliest_created"
    assert body["fair_distribution_limit"] == 100
    assert body["fair_distribution_window"] == 3600
    assert "account_id" not in body  # presenter omits it

    await _create(client, base, headers, "Priority")
    listing = await client.get(base, headers=headers)
    assert listing.status_code == 200
    rows = listing.json()
    assert isinstance(rows, list)
    assert {r["name"] for r in rows} == {"Balanced", "Priority"}


async def test_create_honours_all_fields(client, db_session):
    owner, headers = await _seed_admin(db_session, "-fields")
    base = _base(owner.account.id)
    r = await _create(
        client,
        base,
        headers,
        "Longest",
        description="pick oldest waiting",
        enabled=False,
        assignment_order="round_robin",
        conversation_priority="longest_waiting",
        fair_distribution_limit=5,
        fair_distribution_window=1800,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["description"] == "pick oldest waiting"
    assert body["enabled"] is False
    assert body["conversation_priority"] == "longest_waiting"
    assert body["fair_distribution_limit"] == 5
    assert body["fair_distribution_window"] == 1800


async def test_show_update_destroy(client, db_session):
    owner, headers = await _seed_admin(db_session, "-crud")
    base = _base(owner.account.id)
    created = (await _create(client, base, headers, "Orig")).json()
    pid = created["id"]

    shown = await client.get(f"{base}/{pid}", headers=headers)
    assert shown.status_code == 200
    assert shown.json()["name"] == "Orig"

    upd = await client.patch(
        f"{base}/{pid}",
        json={
            "assignment_policy": {
                "name": "Renamed",
                "conversation_priority": "longest_waiting",
            }
        },
        headers=headers,
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["name"] == "Renamed"
    assert upd.json()["conversation_priority"] == "longest_waiting"

    dele = await client.delete(f"{base}/{pid}", headers=headers)
    assert dele.status_code == 200
    assert dele.json() == {}
    assert (await client.get(f"{base}/{pid}", headers=headers)).status_code == 404


async def test_show_unknown_is_404(client, db_session):
    owner, headers = await _seed_admin(db_session, "-404")
    r = await client.get(f"{_base(owner.account.id)}/999999", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Validations
# ---------------------------------------------------------------------------
async def test_name_presence(client, db_session):
    owner, headers = await _seed_admin(db_session, "-pres")
    base = _base(owner.account.id)
    assert (await _create(client, base, headers, "   ")).status_code == 422
    assert (await _create(client, base, headers, "")).status_code == 422


async def test_name_unique_per_account(client, db_session):
    owner, headers = await _seed_admin(db_session, "-uniq")
    base = _base(owner.account.id)
    assert (await _create(client, base, headers, "Dup")).status_code == 200
    clash = await _create(client, base, headers, "Dup")
    assert clash.status_code == 422, clash.text
    assert "taken" in clash.json()["message"].lower()


async def test_positive_window_validations(client, db_session):
    owner, headers = await _seed_admin(db_session, "-win")
    base = _base(owner.account.id)
    assert (
        await _create(client, base, headers, "L", fair_distribution_limit=0)
    ).status_code == 422
    assert (
        await _create(client, base, headers, "W", fair_distribution_window=-1)
    ).status_code == 422


async def test_invalid_enum_is_422(client, db_session):
    owner, headers = await _seed_admin(db_session, "-enum")
    base = _base(owner.account.id)
    r = await _create(client, base, headers, "Bad", conversation_priority="nope")
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# Authorisation (admin-only)
# ---------------------------------------------------------------------------
async def test_agent_forbidden(client, db_session):
    owner, _ = await _seed_admin(db_session, "-authz")
    _, agent_headers = await _seed_agent(db_session, owner, "-authz")
    base = _base(owner.account.id)
    assert (await client.get(base, headers=agent_headers)).status_code == 401
    assert (
        await _create(client, base, agent_headers, "Nope")
    ).status_code == 401


# ---------------------------------------------------------------------------
# Inbox link (singular resource, one policy per inbox)
# ---------------------------------------------------------------------------
async def test_inbox_link_lifecycle(client, db_session):
    owner, headers = await _seed_admin(db_session, "-link")
    inbox = await _make_inbox(db_session, owner)
    base = _base(owner.account.id)
    ibase = _inbox_base(owner.account.id, inbox.id)

    # No policy yet → dedicated not-found body.
    empty = await client.get(ibase, headers=headers)
    assert empty.status_code == 404
    assert empty.json()["error"] == "Assignment policy not found"

    p1 = (await _create(client, base, headers, "First")).json()
    p2 = (await _create(client, base, headers, "Second")).json()

    linked = await client.post(
        ibase, json={"assignment_policy_id": p1["id"]}, headers=headers
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["name"] == "First"

    shown = await client.get(ibase, headers=headers)
    assert shown.status_code == 200
    assert shown.json()["id"] == p1["id"]

    # Re-linking replaces (only one per inbox).
    relinked = await client.post(
        ibase, json={"assignment_policy_id": p2["id"]}, headers=headers
    )
    assert relinked.status_code == 200
    assert (await client.get(ibase, headers=headers)).json()["id"] == p2["id"]

    dele = await client.delete(ibase, headers=headers)
    assert dele.status_code == 200
    assert dele.json() == {}
    assert (await client.get(ibase, headers=headers)).status_code == 404


async def test_inbox_link_policy_from_other_account_is_404(client, db_session):
    owner, headers = await _seed_admin(db_session, "-xacct")
    other, other_headers = await _seed_admin(db_session, "-xacct-other")
    inbox = await _make_inbox(db_session, owner)
    ibase = _inbox_base(owner.account.id, inbox.id)

    # A policy that belongs to a *different* account.
    foreign = (
        await _create(client, _base(other.account.id), other_headers, "Foreign")
    ).json()

    r = await client.post(
        ibase, json={"assignment_policy_id": foreign["id"]}, headers=headers
    )
    assert r.status_code == 404, r.text


async def test_inbox_link_agent_forbidden(client, db_session):
    owner, _ = await _seed_admin(db_session, "-linkauthz")
    _, agent_headers = await _seed_agent(db_session, owner, "-linkauthz")
    inbox = await _make_inbox(db_session, owner)
    ibase = _inbox_base(owner.account.id, inbox.id)
    assert (await client.get(ibase, headers=agent_headers)).status_code == 401
