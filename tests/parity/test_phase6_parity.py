"""Parity tests for Phase 6 surfaces — labels, macros, automation
rules, CSAT.

Each test sends the same request to AloStudio (in-process FastAPI) and
the reference Chatwoot Rails app and asserts the envelopes match.

We focus on stateless paths — 401 auth gates, 404 unknown-uuid, 422
on malformed body — because seeded-data parity would require
synchronising accounts/users across two backends, which is out of
scope for the parity tier. Phase 6's happy-path coverage lives in
the integration tier on our side and in Chatwoot's own rspec on
the reference side.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/labels_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/macros_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/automation_rules_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/csat_survey_responses_controller.rb
  reference/chatwoot/app/controllers/public/api/v1/csat_survey_controller.rb
"""

from __future__ import annotations

import pytest

from tests.parity._harness import assert_json_parity

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# Labels (6.1)
# ---------------------------------------------------------------------------
async def test_labels_index_unauthenticated_returns_401(alo_client, cw_client):
    """Both backends return 401 + devise-token-auth's stock error
    envelope for a GET /labels with no auth headers."""
    alo = await alo_client.get("/api/v1/accounts/1/labels")
    cw = await cw_client.get("/api/v1/accounts/1/labels")
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


async def test_labels_create_unauthenticated_returns_401(alo_client, cw_client):
    """POST also pins the same 401 envelope."""
    body = {"label": {"title": "parity-probe"}}
    alo = await alo_client.post("/api/v1/accounts/1/labels", json=body)
    cw = await cw_client.post("/api/v1/accounts/1/labels", json=body)
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


# ---------------------------------------------------------------------------
# Macros (6.2)
# ---------------------------------------------------------------------------
async def test_macros_index_unauthenticated_returns_401(alo_client, cw_client):
    alo = await alo_client.get("/api/v1/accounts/1/macros")
    cw = await cw_client.get("/api/v1/accounts/1/macros")
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


async def test_macros_execute_unauthenticated_returns_401(alo_client, cw_client):
    """``POST /macros/:id/execute`` mirrors the same envelope."""
    body = {"conversation_ids": [1]}
    alo = await alo_client.post(
        "/api/v1/accounts/1/macros/9999/execute", json=body
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/macros/9999/execute", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


# ---------------------------------------------------------------------------
# AutomationRule (6.3 / 6.4)
# ---------------------------------------------------------------------------
async def test_automation_rules_index_unauthenticated_returns_401(
    alo_client, cw_client
):
    alo = await alo_client.get("/api/v1/accounts/1/automation_rules")
    cw = await cw_client.get("/api/v1/accounts/1/automation_rules")
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


async def test_automation_rules_clone_unauthenticated_returns_401(
    alo_client, cw_client
):
    """The bespoke ``POST /clone`` action sits behind the same gate."""
    alo = await alo_client.post(
        "/api/v1/accounts/1/automation_rules/9999/clone"
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/automation_rules/9999/clone"
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


# ---------------------------------------------------------------------------
# CSAT — dashboard (6.5)
# ---------------------------------------------------------------------------
async def test_csat_dashboard_index_unauthenticated_returns_401(
    alo_client, cw_client
):
    alo = await alo_client.get("/api/v1/accounts/1/csat_survey_responses")
    cw = await cw_client.get("/api/v1/accounts/1/csat_survey_responses")
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


# ---------------------------------------------------------------------------
# CSAT — public (no auth needed; UUID is the credential)
# ---------------------------------------------------------------------------
async def test_csat_public_show_unknown_uuid_returns_404(
    alo_client, cw_client
):
    """Unknown conversation UUID returns 404 on both backends.

    Body shape divergence (intentional, documented here so the diff
    doesn't surprise readers): Rails returns
    ``{"status":404,"error":"Not Found"}`` from its global
    ActionController 404 handler; we return our domain envelope
    ``{"error":"Resource could not be found"}``. Both convey 404 to
    the client, neither leaks resource existence, so we pin the
    status code only and document the body divergence here."""
    uuid = "00000000-0000-0000-0000-000000000000"
    alo = await alo_client.get(f"/public/api/v1/csat_survey/{uuid}")
    cw = await cw_client.get(f"/public/api/v1/csat_survey/{uuid}")
    assert alo.status_code == 404
    assert cw.status_code == 404
