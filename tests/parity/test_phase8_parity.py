"""Parity tests for Phase 8 — agent_bots, webhooks, integrations.

Each test sends the same request to AloStudio and the reference
Chatwoot Rails app and asserts the 401 envelope matches byte-for-byte.

Stateless 401 gates only (same posture as Phase 6/7 parity) —
seeded-data parity would require synchronising accounts/inboxes
across both backends.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/agent_bots_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/webhooks_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/integrations/{apps,hooks}_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/inboxes_controller.rb
    (set_agent_bot member action)
"""

from __future__ import annotations

import pytest

from tests.parity._harness import assert_json_parity

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# AgentBot (8.1)
# ---------------------------------------------------------------------------
async def test_agent_bots_index_unauthenticated_returns_401(
    alo_client, cw_client
):
    alo = await alo_client.get("/api/v1/accounts/1/agent_bots")
    cw = await cw_client.get("/api/v1/accounts/1/agent_bots")
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


async def test_agent_bots_create_unauthenticated_returns_401(
    alo_client, cw_client
):
    body = {"name": "parity"}
    alo = await alo_client.post(
        "/api/v1/accounts/1/agent_bots", json=body
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/agent_bots", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


async def test_set_agent_bot_unauthenticated_returns_401(
    alo_client, cw_client
):
    """Inbox-side attach action mirrors the same 401."""
    body = {"agent_bot": 1}
    alo = await alo_client.post(
        "/api/v1/accounts/1/inboxes/1/set_agent_bot", json=body
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/inboxes/1/set_agent_bot", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


# ---------------------------------------------------------------------------
# Webhooks (8.3)
# ---------------------------------------------------------------------------
async def test_webhooks_index_unauthenticated_returns_401(
    alo_client, cw_client
):
    alo = await alo_client.get("/api/v1/accounts/1/webhooks")
    cw = await cw_client.get("/api/v1/accounts/1/webhooks")
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


async def test_webhooks_create_unauthenticated_returns_401(
    alo_client, cw_client
):
    body = {
        "webhook": {
            "url": "https://parity.example.com",
            "subscriptions": ["message_created"],
        }
    }
    alo = await alo_client.post(
        "/api/v1/accounts/1/webhooks", json=body
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/webhooks", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


# ---------------------------------------------------------------------------
# Integrations apps + hooks (8.4)
# ---------------------------------------------------------------------------
async def test_integrations_apps_index_unauthenticated_returns_401(
    alo_client, cw_client
):
    alo = await alo_client.get("/api/v1/accounts/1/integrations/apps")
    cw = await cw_client.get("/api/v1/accounts/1/integrations/apps")
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


async def test_integrations_hook_create_unauthenticated_returns_401(
    alo_client, cw_client
):
    body = {"hook": {"app_id": "slack"}}
    alo = await alo_client.post(
        "/api/v1/accounts/1/integrations/hooks", json=body
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/integrations/hooks", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)
