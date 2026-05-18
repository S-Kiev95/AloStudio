"""Parity tests for Phase 10 — public Help Center + health.

The new endpoints in Phase 10 are mostly internal-facing (scheduler
worker, observability middleware) — only the public Help Center has
a true cross-backend wire to compare against.

Anchors:
  reference/chatwoot/app/controllers/public/api/v1/portals_controller.rb
  reference/chatwoot/app/controllers/public/api/v1/portals/articles_controller.rb
  reference/chatwoot/app/controllers/public/api/v1/portals/categories_controller.rb
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# Public Help Center — unknown slug 404
# ---------------------------------------------------------------------------
async def test_public_portal_unknown_slug_returns_404(
    alo_client, cw_client
):
    """Both backends return 404 for a slug that doesn't resolve.

    Body shape divergence (intentional, documented here): Rails
    renders the Action Dispatch ``layout: 'portal'`` 404 page (HTML);
    we return our domain JSON envelope. Both 404 the request and
    leak no resource existence — we pin the status code only."""
    alo = await alo_client.get("/hc/parity-no-such-portal")
    cw = await cw_client.get("/hc/parity-no-such-portal")
    assert alo.status_code == 404
    assert cw.status_code == 404


async def test_public_articles_unknown_slug_returns_404(
    alo_client, cw_client
):
    alo = await alo_client.get(
        "/hc/parity-no-such-portal/articles"
    )
    cw = await cw_client.get("/hc/parity-no-such-portal/articles")
    assert alo.status_code == 404
    assert cw.status_code == 404


async def test_public_categories_unknown_slug_returns_404(
    alo_client, cw_client
):
    alo = await alo_client.get(
        "/hc/parity-no-such-portal/categories"
    )
    cw = await cw_client.get(
        "/hc/parity-no-such-portal/categories"
    )
    assert alo.status_code == 404
    assert cw.status_code == 404


# ---------------------------------------------------------------------------
# Health — status code parity only
# ---------------------------------------------------------------------------
async def test_health_returns_200_on_both(alo_client, cw_client):
    """Documented divergence: Chatwoot's ``/health`` returns
    ``{"status":"woot"}`` (a one-shot liveness probe); ours returns a
    component map with per-dependency status. Both 200 means the
    process is alive — same observable contract. Body shape is
    intentionally NOT asserted (our payload is a superset)."""
    alo = await alo_client.get("/health")
    cw = await cw_client.get("/health")
    assert alo.status_code == 200
    assert cw.status_code == 200
