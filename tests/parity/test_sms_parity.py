"""Parity tests for the Twilio + Bandwidth SMS webhook surfaces.

Anchors:
  reference/chatwoot/app/controllers/twilio/callback_controller.rb
  reference/chatwoot/app/controllers/webhooks/sms_controller.rb
"""

from __future__ import annotations

import pytest

from tests.parity._harness import assert_json_parity

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# Twilio webhook — POST /twilio/callback
# ---------------------------------------------------------------------------
async def test_twilio_form_post_acks_unknown_account(alo_client, cw_client):
    """A form-encoded payload with an AccountSid that doesn't resolve
    on either backend still gets a 2xx ack — both sides queue without
    a channel-existence check. Status codes match (Rails returns 204
    head_no_content; we return 200 with empty body)."""
    data = {
        "AccountSid": "ACdoesnotexist",
        "To": "+19999999999",
        "From": "+15551234567",
        "Body": "hi",
        "SmsSid": "SM-x",
        "MessageSid": "SM-x",
    }
    alo = await alo_client.post("/twilio/callback", data=data)
    cw = await cw_client.post("/twilio/callback", data=data)
    # Twilio accepts any 2xx; Rails ships 204, we ship 200. Pin the
    # 2xx invariant rather than a strict equality so the divergence
    # in HTTP status code (a stylistic Rails head :no_content
    # convention) doesn't break parity.
    assert 200 <= alo.status_code < 300
    assert 200 <= cw.status_code < 300


async def test_twilio_empty_body_still_2xx(alo_client, cw_client):
    """Empty body — Twilio retries on 5xx, both backends 2xx."""
    alo = await alo_client.post("/twilio/callback", data={})
    cw = await cw_client.post("/twilio/callback", data={})
    assert 200 <= alo.status_code < 300
    assert 200 <= cw.status_code < 300


# ---------------------------------------------------------------------------
# Bandwidth webhook — POST /webhooks/sms/<phone>
# ---------------------------------------------------------------------------
async def test_bandwidth_unknown_phone_acks_2xx(alo_client, cw_client):
    """Unknown phone in the URL — both backends 2xx."""
    alo = await alo_client.post(
        "/webhooks/sms/+19999999999",
        json=[{"type": "message-received"}],
    )
    cw = await cw_client.post(
        "/webhooks/sms/+19999999999",
        json=[{"type": "message-received"}],
    )
    assert 200 <= alo.status_code < 300
    assert 200 <= cw.status_code < 300


async def test_bandwidth_empty_array_acks_2xx(alo_client, cw_client):
    alo = await alo_client.post(
        "/webhooks/sms/+19999999999", json=[]
    )
    cw = await cw_client.post(
        "/webhooks/sms/+19999999999", json=[]
    )
    assert 200 <= alo.status_code < 300
    assert 200 <= cw.status_code < 300


# Keep harness import live for body-shape parity additions later.
_ = assert_json_parity
