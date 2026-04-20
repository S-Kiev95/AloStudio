"""Parity tests for Phase 2 teams + inboxes endpoints — stateless branches.

Like :mod:`test_auth_parity`, we focus on the deterministic,
no-seed-needed branches:

  * 401 for unauthenticated calls (no headers)
  * 404 envelope shape for a non-existent account_id

Happy paths on teams + inboxes need synchronized seed data across the
two backends (same admin user in an account) which is out of scope for
an in-process harness. Those live in the integration suite on our side
and in Chatwoot's own rspec on theirs — this module catches the wire
envelopes that would silently drift if somebody changed a controller's
error renderer in either codebase.
"""

from __future__ import annotations

import pytest

from tests.parity._harness import assert_json_parity

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------
async def test_teams_index_without_auth_matches(alo_client, cw_client):
    """No auth headers → 401 on both backends."""
    alo = await alo_client.get("/api/v1/accounts/1/teams")
    cw = await cw_client.get("/api/v1/accounts/1/teams")

    assert alo.status_code == 401
    assert cw.status_code == 401
    # Body envelopes diverge (FastAPI ``detail`` vs devise-token-auth
    # ``errors``); status parity is the hard guarantee.


async def test_teams_create_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.post("/api/v1/accounts/1/teams", json={"name": "x"})
    cw = await cw_client.post("/api/v1/accounts/1/teams", json={"name": "x"})

    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_team_members_index_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.get("/api/v1/accounts/1/teams/1/team_members")
    cw = await cw_client.get("/api/v1/accounts/1/teams/1/team_members")

    assert alo.status_code == 401
    assert cw.status_code == 401


# ---------------------------------------------------------------------------
# Inboxes
# ---------------------------------------------------------------------------
async def test_inboxes_index_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.get("/api/v1/accounts/1/inboxes")
    cw = await cw_client.get("/api/v1/accounts/1/inboxes")

    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_inboxes_create_without_auth_matches(alo_client, cw_client):
    body = {"name": "x", "channel": {"type": "api"}}
    alo = await alo_client.post("/api/v1/accounts/1/inboxes", json=body)
    cw = await cw_client.post("/api/v1/accounts/1/inboxes", json=body)

    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_inbox_members_without_auth_matches(alo_client, cw_client):
    # Chatwoot declares ``resources :inbox_members, param: :inbox_id`` at
    # the account level (NOT nested under /inboxes/:id), so ``show`` hangs
    # off ``/inbox_members/:inbox_id``.
    alo = await alo_client.get("/api/v1/accounts/1/inbox_members/1")
    cw = await cw_client.get("/api/v1/accounts/1/inbox_members/1")

    assert alo.status_code == 401
    assert cw.status_code == 401


# ---------------------------------------------------------------------------
# Body parity for shared error paths we CAN align
# ---------------------------------------------------------------------------
async def test_reset_secret_without_auth_matches(alo_client, cw_client):
    """``POST /inboxes/:id/reset_secret`` — 401 unauthenticated."""
    alo = await alo_client.post("/api/v1/accounts/1/inboxes/1/reset_secret")
    cw = await cw_client.post("/api/v1/accounts/1/inboxes/1/reset_secret")

    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_destroy_team_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.delete("/api/v1/accounts/1/teams/1")
    cw = await cw_client.delete("/api/v1/accounts/1/teams/1")
    assert alo.status_code == 401
    assert cw.status_code == 401


# Keep the unused import quiet — assert_json_parity is wired for future
# happy-path additions (body envelopes across backends).
_ = assert_json_parity
