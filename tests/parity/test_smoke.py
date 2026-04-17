"""Phase 0 parity smoke test.

We don't have ported endpoints yet, so this test only confirms that:
  1. The parity harness can spin up AloStudio in-process (alo_client).
  2. The parity harness can reach the Chatwoot reference (cw_client) OR cleanly
     skip when it is not running.

Once Phase 1 lands, real parity assertions on /auth/sign_up, /auth/sign_in,
and /api/v1/profile get added here.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.parity


async def test_alo_is_up(alo_client) -> None:
    r = await alo_client.get("/")
    assert r.status_code == 200


async def test_chatwoot_reference_is_up(cw_client) -> None:
    # Chatwoot's root serves the Vue frontend HTML; we just want HTTP < 500.
    r = await cw_client.get("/")
    assert r.status_code < 500
