"""Parity tests for Phase 9 — working hours, portals, articles,
categories, campaigns.

Same posture as Phase 6/7/8 — stateless 401 gates only. Seeded
happy-path body parity would require synchronising accounts +
inboxes across both backends.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/working_hours_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/portals_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/articles_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/categories_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/campaigns_controller.rb
"""

from __future__ import annotations

import pytest

from tests.parity._harness import assert_json_parity

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# Working hours (9.1)
# ---------------------------------------------------------------------------
async def test_working_hours_single_update_unauthenticated_returns_401(
    alo_client, cw_client
):
    body = {"working_hour": {"day_of_week": 1, "open_hour": 9}}
    alo = await alo_client.patch(
        "/api/v1/accounts/1/working_hours/1", json=body
    )
    cw = await cw_client.patch(
        "/api/v1/accounts/1/working_hours/1", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


# ---------------------------------------------------------------------------
# Portals (9.3)
# ---------------------------------------------------------------------------
async def test_portals_index_unauthenticated_returns_401(
    alo_client, cw_client
):
    alo = await alo_client.get("/api/v1/accounts/1/portals")
    cw = await cw_client.get("/api/v1/accounts/1/portals")
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


async def test_portals_create_unauthenticated_returns_401(
    alo_client, cw_client
):
    body = {"portal": {"name": "Acme", "slug": "acme-help"}}
    alo = await alo_client.post(
        "/api/v1/accounts/1/portals", json=body
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/portals", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


async def test_articles_index_unauthenticated_returns_401(
    alo_client, cw_client
):
    alo = await alo_client.get(
        "/api/v1/accounts/1/portals/parity/articles"
    )
    cw = await cw_client.get(
        "/api/v1/accounts/1/portals/parity/articles"
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


async def test_categories_index_unauthenticated_returns_401(
    alo_client, cw_client
):
    alo = await alo_client.get(
        "/api/v1/accounts/1/portals/parity/categories"
    )
    cw = await cw_client.get(
        "/api/v1/accounts/1/portals/parity/categories"
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


# ---------------------------------------------------------------------------
# Campaigns (9.4)
# ---------------------------------------------------------------------------
async def test_campaigns_index_unauthenticated_returns_401(
    alo_client, cw_client
):
    alo = await alo_client.get("/api/v1/accounts/1/campaigns")
    cw = await cw_client.get("/api/v1/accounts/1/campaigns")
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)


async def test_campaigns_create_unauthenticated_returns_401(
    alo_client, cw_client
):
    body = {
        "campaign": {"title": "x", "message": "y", "inbox_id": 1}
    }
    alo = await alo_client.post(
        "/api/v1/accounts/1/campaigns", json=body
    )
    cw = await cw_client.post(
        "/api/v1/accounts/1/campaigns", json=body
    )
    assert alo.status_code == 401
    assert cw.status_code == 401
    assert_json_parity(alo, cw)
