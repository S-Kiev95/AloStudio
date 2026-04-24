"""Parity tests for Phase 4a messages nested router.

Same philosophy as ``test_conversations_parity.py`` — we assert parity
on the stateless gates (401 unauthenticated) because happy-path parity
for message-create/index/destroy needs a seeded conversation + contact
+ inbox on both sides, which isn't worth the cross-backend coordination
when Chatwoot's own rspec + our integration suite already cover that
ground independently.

Covered endpoints:

  * ``GET    /api/v1/accounts/:account_id/conversations/:conv_id/messages``
  * ``POST   /api/v1/accounts/:account_id/conversations/:conv_id/messages``
  * ``DELETE /api/v1/accounts/:account_id/conversations/:conv_id/messages/:id``
"""

from __future__ import annotations

import pytest

from tests.parity._harness import assert_json_parity

pytestmark = pytest.mark.parity


async def test_index_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.get("/api/v1/accounts/1/conversations/1/messages")
    cw = await cw_client.get("/api/v1/accounts/1/conversations/1/messages")
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_create_without_auth_matches(alo_client, cw_client):
    body = {"content": "hi", "message_type": "outgoing"}
    alo = await alo_client.post(
        "/api/v1/accounts/1/conversations/1/messages", json=body
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/conversations/1/messages", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_destroy_without_auth_matches(alo_client, cw_client):
    alo = await alo_client.delete("/api/v1/accounts/1/conversations/1/messages/1")
    cw = await cw_client.delete("/api/v1/accounts/1/conversations/1/messages/1")
    assert alo.status_code == 401
    assert cw.status_code == 401


# ---------------------------------------------------------------------------
# Create with various bodies — still unauthenticated, just makes sure the
# 401 fires before body validation regardless of payload shape.
# ---------------------------------------------------------------------------
async def test_create_incoming_without_auth_matches(alo_client, cw_client):
    body = {"content": "hi", "message_type": "incoming"}
    alo = await alo_client.post(
        "/api/v1/accounts/1/conversations/1/messages", json=body
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/conversations/1/messages", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401


async def test_create_with_attachments_without_auth_matches(alo_client, cw_client):
    """``attachments`` as URL-metadata list — Phase 4a accepts the same
    shape Chatwoot does. Auth gate should fire before any validation."""
    body = {
        "content": "see pic",
        "message_type": "outgoing",
        "attachments": [
            {"file_type": "image", "external_url": "https://cdn.example.com/a.png"}
        ],
    }
    alo = await alo_client.post(
        "/api/v1/accounts/1/conversations/1/messages", json=body
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/conversations/1/messages", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401


# Keep the unused import quiet — assert_json_parity is wired for future
# body-envelope additions when we gain a seeded happy path.
_ = assert_json_parity
