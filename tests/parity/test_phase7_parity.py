"""Parity tests for Phase 7 — V2 reports surface.

Each test sends the same request to AloStudio and the reference
Chatwoot Rails app and asserts the 401 envelope matches byte-for-byte.

We focus on stateless 401 gates — happy-path body parity would
require seeded ReportingEvent rows on both backends, which is out of
scope for the parity tier (covered by integration on our side and
Chatwoot's own rspec on theirs).

Anchors:
  reference/chatwoot/app/controllers/api/v2/accounts/reports_controller.rb
  reference/chatwoot/app/controllers/api/v2/accounts/live_reports_controller.rb
  reference/chatwoot/app/controllers/api/v2/accounts/summary_reports_controller.rb
"""

from __future__ import annotations

import pytest

from tests.parity._harness import assert_json_parity

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# Reports (timeseries + summary + conversations)
# ---------------------------------------------------------------------------
async def test_reports_summary_unauthenticated_returns_401(
    alo_client, cw_client
):
    alo = await alo_client.get("/api/v2/accounts/1/reports/summary")
    cw = await cw_client.get("/api/v2/accounts/1/reports/summary")
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


async def test_reports_timeseries_unauthenticated_returns_401(
    alo_client, cw_client
):
    alo = await alo_client.get(
        "/api/v2/accounts/1/reports?metric=conversations_count"
    )
    cw = await cw_client.get(
        "/api/v2/accounts/1/reports?metric=conversations_count"
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


async def test_reports_conversations_unauthenticated_returns_401(
    alo_client, cw_client
):
    alo = await alo_client.get(
        "/api/v2/accounts/1/reports/conversations?type=conversation"
    )
    cw = await cw_client.get(
        "/api/v2/accounts/1/reports/conversations?type=conversation"
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


# ---------------------------------------------------------------------------
# Live reports
# ---------------------------------------------------------------------------
async def test_live_conversation_metrics_unauthenticated_returns_401(
    alo_client, cw_client
):
    alo = await alo_client.get(
        "/api/v2/accounts/1/live_reports/conversation_metrics"
    )
    cw = await cw_client.get(
        "/api/v2/accounts/1/live_reports/conversation_metrics"
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


async def test_grouped_conversation_metrics_unauthenticated_returns_401(
    alo_client, cw_client
):
    """The ``group_by`` invalid-value check sits BEHIND auth on Chatwoot
    (auth runs first), so the no-auth surface returns the same 401
    envelope regardless of payload."""
    alo = await alo_client.get(
        "/api/v2/accounts/1/live_reports/grouped_conversation_metrics"
        "?group_by=team_id"
    )
    cw = await cw_client.get(
        "/api/v2/accounts/1/live_reports/grouped_conversation_metrics"
        "?group_by=team_id"
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


# ---------------------------------------------------------------------------
# Summary reports (per-entity)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("entity", ["agent", "team", "inbox", "label"])
async def test_summary_reports_unauthenticated_returns_401(
    alo_client, cw_client, entity
):
    alo = await alo_client.get(
        f"/api/v2/accounts/1/summary_reports/{entity}"
    )
    cw = await cw_client.get(
        f"/api/v2/accounts/1/summary_reports/{entity}"
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)
