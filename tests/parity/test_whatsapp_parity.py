"""Parity tests for the WhatsApp webhook surface.

Pin the stateless 4xx/2xx envelopes cross-backend (Chatwoot reference
vs AloStudio) so a small change on either side that drifts the
verify-token handshake or the unknown-phone 404 fails here loudly.

Anchors:
  reference/chatwoot/app/controllers/webhooks/whatsapp_controller.rb
  reference/chatwoot/app/controllers/concerns/meta_token_verify_concern.rb
"""

from __future__ import annotations

import pytest

from tests.parity._harness import assert_json_parity

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# GET — verification handshake
# ---------------------------------------------------------------------------
async def test_verify_unknown_phone_returns_401(alo_client, cw_client):
    """Rails ``valid_token?`` short-circuits to nil for unknown phones,
    the MetaTokenVerifyConcern then renders 401 with the canonical
    envelope. We mirror that — unknown phones get the same 401 as
    wrong-token requests so we don't leak which phones are registered.
    """
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "anything",
        "hub.challenge": "1234",
    }
    alo = await alo_client.get(
        "/webhooks/whatsapp/+19999999999", params=params
    )
    cw = await cw_client.get(
        "/webhooks/whatsapp/+19999999999", params=params
    )
    assert alo.status_code == cw.status_code
    assert alo.status_code == 401


async def test_verify_missing_token_returns_401(alo_client, cw_client):
    """No hub.verify_token at all -> 401 (Rails' ``valid_token?(nil)``
    returns false in every branch)."""
    params = {"hub.mode": "subscribe", "hub.challenge": "1234"}
    alo = await alo_client.get(
        "/webhooks/whatsapp/+19999999999", params=params
    )
    cw = await cw_client.get(
        "/webhooks/whatsapp/+19999999999", params=params
    )
    assert alo.status_code == cw.status_code
    assert alo.status_code == 401


# ---------------------------------------------------------------------------
# POST — payload receive
# ---------------------------------------------------------------------------
async def test_receive_unknown_phone_acks_200(alo_client, cw_client):
    """Rails ``process_payload`` queues the events job without
    checking the channel — unknown phones still get ``head :ok``.
    Meta retries on 5xx so we never want to send anything but 2xx for
    a malformed/unknown payload."""
    body = {
        "object": "whatsapp_business_account",
        "entry": [],
    }
    alo = await alo_client.post(
        "/webhooks/whatsapp/+19999999999", json=body
    )
    cw = await cw_client.post(
        "/webhooks/whatsapp/+19999999999", json=body
    )
    assert alo.status_code == cw.status_code
    assert alo.status_code == 200


# Keep harness import live for body-shape parity additions in 5c.6.
_ = assert_json_parity
