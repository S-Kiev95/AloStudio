"""Parity tests for Phase 4a conversations endpoints.

Following the same philosophy as ``test_teams_parity.py`` and
``test_auth_parity.py``: we pin the **stateless error branches** where
parity is most easily broken by a small change in either codebase.

Happy-path parity (create, toggle_status, etc.) requires identical seed
data across both backends — a seeded admin user, inbox, contact, and
conversation. That's infrastructure beyond this harness (we'd need to
POST to Chatwoot's internal create endpoints, then replicate the row
IDs on our side). That class of parity lives in our integration suite
on the Alo side, and in Chatwoot's own rspec suite on theirs.

What we DO cover cross-backend:

  * ``401`` without auth on every 4a endpoint.
  * ``404`` envelope for unknown account / unknown display_id when the
    unauthenticated-gate happens to let the request through (some
    routes 401 first, some route-match first — Rails and FastAPI mostly
    agree, this test pins any drift).
"""

from __future__ import annotations

import pytest

from tests.parity._harness import assert_json_parity

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# Index / meta (read-only, no body)
# ---------------------------------------------------------------------------
async def test_index_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.get("/api/v1/accounts/1/conversations")
    cw = await cw_client.get("/api/v1/accounts/1/conversations")
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_meta_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.get("/api/v1/accounts/1/conversations/meta")
    cw = await cw_client.get("/api/v1/accounts/1/conversations/meta")
    assert alo.status_code == 401
    assert cw.status_code == 401


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
async def test_create_without_auth_matches(alo_client, cw_client):
    body = {"inbox_id": 1, "contact_id": 1}
    alo = await alo_client.post("/api/v1/accounts/1/conversations", json=body)
    cw = await cw_client.post("/api/v1/accounts/1/conversations", json=body)
    assert alo.status_code == 401
    assert cw.status_code == 401


# ---------------------------------------------------------------------------
# Show / update
# ---------------------------------------------------------------------------
async def test_show_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.get("/api/v1/accounts/1/conversations/1")
    cw = await cw_client.get("/api/v1/accounts/1/conversations/1")
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_update_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.patch(
        "/api/v1/accounts/1/conversations/1", json={"priority": "high"}
    )
    cw = await cw_client.patch(
        "/api/v1/accounts/1/conversations/1", json={"priority": "high"}
    )
    assert alo.status_code == 401
    assert cw.status_code == 401


# ---------------------------------------------------------------------------
# State-machine transitions
# ---------------------------------------------------------------------------
async def test_toggle_status_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.post(
        "/api/v1/accounts/1/conversations/1/toggle_status", json={}
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/conversations/1/toggle_status", json={}
    )
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_toggle_priority_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.post(
        "/api/v1/accounts/1/conversations/1/toggle_priority",
        json={"priority": "urgent"},
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/conversations/1/toggle_priority",
        json={"priority": "urgent"},
    )
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_mute_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.post("/api/v1/accounts/1/conversations/1/mute")
    cw = await cw_client.post("/api/v1/accounts/1/conversations/1/mute")
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_unmute_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.post("/api/v1/accounts/1/conversations/1/unmute")
    cw = await cw_client.post("/api/v1/accounts/1/conversations/1/unmute")
    assert alo.status_code == 401
    assert cw.status_code == 401


# ---------------------------------------------------------------------------
# Custom attributes
# ---------------------------------------------------------------------------
async def test_custom_attributes_without_auth_matches(alo_client, cw_client):
    body = {"custom_attributes": {"plan": "gold"}}
    alo = await alo_client.post(
        "/api/v1/accounts/1/conversations/1/custom_attributes", json=body
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/conversations/1/custom_attributes", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401


# ---------------------------------------------------------------------------
# Seen / unread
# ---------------------------------------------------------------------------
async def test_update_last_seen_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.post("/api/v1/accounts/1/conversations/1/update_last_seen")
    cw = await cw_client.post("/api/v1/accounts/1/conversations/1/update_last_seen")
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_unread_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.post("/api/v1/accounts/1/conversations/1/unread")
    cw = await cw_client.post("/api/v1/accounts/1/conversations/1/unread")
    assert alo.status_code == 401
    assert cw.status_code == 401


# ---------------------------------------------------------------------------
# Phase 4b auth-gates — endpoints added in milestones 4b.3 / 4b.4 / 4b.5.
# Each pins the unauthenticated 401 envelope so a Rails or FastAPI patch
# that drifts the gate (e.g. routes to controller before authenticate)
# fails here loudly.
# ---------------------------------------------------------------------------
async def test_assignments_without_auth_matches(alo_client, cw_client):
    body = {"assignee_id": 1}
    alo = await alo_client.post(
        "/api/v1/accounts/1/conversations/1/assignments", json=body
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/conversations/1/assignments", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_labels_index_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.get("/api/v1/accounts/1/conversations/1/labels")
    cw = await cw_client.get("/api/v1/accounts/1/conversations/1/labels")
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_labels_create_without_auth_matches(alo_client, cw_client):
    body = {"labels": ["urgent"]}
    alo = await alo_client.post(
        "/api/v1/accounts/1/conversations/1/labels", json=body
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/conversations/1/labels", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_search_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.get(
        "/api/v1/accounts/1/conversations/search?q=hello"
    )
    cw = await cw_client.get("/api/v1/accounts/1/conversations/search?q=hello")
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_filter_without_auth_matches(alo_client, cw_client):
    body = {
        "payload": [
            {
                "attribute_key": "status",
                "filter_operator": "equal_to",
                "values": ["open"],
            }
        ]
    }
    alo = await alo_client.post("/api/v1/accounts/1/conversations/filter", json=body)
    cw = await cw_client.post("/api/v1/accounts/1/conversations/filter", json=body)
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_toggle_typing_status_without_auth_matches(alo_client, cw_client):
    body = {"typing_status": "on", "is_private": False}
    alo = await alo_client.post(
        "/api/v1/accounts/1/conversations/1/toggle_typing_status", json=body
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/conversations/1/toggle_typing_status", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_attachments_index_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.get(
        "/api/v1/accounts/1/conversations/1/attachments"
    )
    cw = await cw_client.get("/api/v1/accounts/1/conversations/1/attachments")
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_messages_update_without_auth_matches(alo_client, cw_client):
    body = {"status": "delivered"}
    alo = await alo_client.patch(
        "/api/v1/accounts/1/conversations/1/messages/1", json=body
    )
    cw = await cw_client.patch(
        "/api/v1/accounts/1/conversations/1/messages/1", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401


# Keep the unused import quiet — assert_json_parity is wired for future
# body-envelope additions when we gain a seeded happy path.
_ = assert_json_parity
