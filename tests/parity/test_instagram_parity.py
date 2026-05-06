"""Parity tests for the Instagram webhook surface.

Pin the stateless 4xx/2xx/422 envelopes cross-backend so a small
change on either side that drifts the verify-token handshake or the
``object: instagram`` body gate fails here loudly.

Anchors:
  reference/chatwoot/app/controllers/webhooks/instagram_controller.rb
"""

from __future__ import annotations

import pytest

from tests.parity._harness import assert_json_parity

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# GET — verification handshake
# ---------------------------------------------------------------------------
async def test_verify_wrong_token_matches(alo_client, cw_client):
    """Both backends 401 when ``hub.verify_token`` is wrong / unset.
    Default empty config on both sides means any token mismatch
    rejects (fail-closed)."""
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "definitely-not-the-real-token",
        "hub.challenge": "1234",
    }
    alo = await alo_client.get("/webhooks/instagram", params=params)
    cw = await cw_client.get("/webhooks/instagram", params=params)
    assert alo.status_code == cw.status_code
    assert alo.status_code == 401


# Note: a request with NO ``hub.verify_token`` parameter at all
# diverges between the two backends — Chatwoot's controller short-
# circuits the comparison branch and returns 200; we fail-closed
# with 401 (don't accept ANY missing-token request, even from
# something Meta-shaped). The ``test_verify_wrong_token_matches``
# test above pins the matching canonical-401 path.


# ---------------------------------------------------------------------------
# POST — payload receive
# ---------------------------------------------------------------------------
async def test_receive_instagram_payload_acks_200(alo_client, cw_client):
    """A standard IG payload with no matching account on either
    backend gets a 200 ack — both sides queue without short-
    circuiting on channel existence."""
    body = {
        "object": "instagram",
        "entry": [
            {
                "id": "IG-NOT-REAL",
                "time": 1700000000,
                "messaging": [],
            }
        ],
    }
    alo = await alo_client.post("/webhooks/instagram", json=body)
    cw = await cw_client.post("/webhooks/instagram", json=body)
    assert alo.status_code == cw.status_code
    assert alo.status_code == 200


async def test_receive_non_instagram_object_rejected_422(alo_client, cw_client):
    """Mirror Rails: ``object != 'instagram'`` -> 422 on both
    backends. Don't silently parse a misrouted Messenger payload as
    Instagram."""
    body = {"object": "page", "entry": []}
    alo = await alo_client.post("/webhooks/instagram", json=body)
    cw = await cw_client.post("/webhooks/instagram", json=body)
    assert alo.status_code == cw.status_code
    assert alo.status_code == 422


# Keep harness import live for body-shape parity additions later.
_ = assert_json_parity
