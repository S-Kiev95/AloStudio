"""Parity tests for the Telegram webhook surface.

Anchors:
  reference/chatwoot/app/controllers/webhooks/telegram_controller.rb
  reference/chatwoot/config/routes.rb (post 'webhooks/telegram/:bot_token')

Chatwoot's controller is a single line — ``head :ok`` — and queues
the work into ``Webhooks::TelegramEventsJob`` regardless of payload
shape. Our FastAPI router mirrors that ack-and-defer contract: every
request gets a 2xx, unknown tokens / group chats / non-message
updates all queue silently.

Intentional divergence — malformed JSON: Rails 400s before the
controller runs (the rack JSON parser raises); our router catches the
parse error and 200s. Telegram never sends malformed JSON in practice,
and accepting bad bodies is strictly more tolerant — no functional
divergence in the happy path. Documented here so future readers don't
mistake it for a regression.
"""

from __future__ import annotations

import pytest

from tests.parity._harness import assert_json_parity

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# POST /webhooks/telegram/<bot_token>
# ---------------------------------------------------------------------------
async def test_telegram_unknown_token_acks_2xx(alo_client, cw_client):
    """Unknown bot_token in the URL — both backends 2xx.

    Telegram retries with exponential backoff on non-2xx, so even
    obvious bad tokens must ack."""
    body = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "from": {
                "id": 99,
                "is_bot": False,
                "first_name": "Stranger",
                "username": "stranger",
            },
            "chat": {"id": 99, "type": "private"},
            "date": 1700000000,
            "text": "hi",
        },
    }
    alo = await alo_client.post(
        "/webhooks/telegram/unknown:99",
        json=body,
    )
    cw = await cw_client.post(
        "/webhooks/telegram/unknown:99",
        json=body,
    )
    assert 200 <= alo.status_code < 300
    assert 200 <= cw.status_code < 300


async def test_telegram_empty_body_still_2xx(alo_client, cw_client):
    alo = await alo_client.post(
        "/webhooks/telegram/empty:1", json={}
    )
    cw = await cw_client.post(
        "/webhooks/telegram/empty:1", json={}
    )
    assert 200 <= alo.status_code < 300
    assert 200 <= cw.status_code < 300


async def test_telegram_non_message_update_acks_2xx(alo_client, cw_client):
    """Telegram sends many update kinds beyond ``message`` (callback_query,
    edited_message, channel_post, …). Chatwoot's
    ``IncomingMessageService#process`` returns early when the payload has
    no usable ``message`` block; we mirror that by dropping silently.
    Both backends 2xx in either case."""
    body = {"update_id": 42, "callback_query": {"id": "cbq-1"}}
    alo = await alo_client.post(
        "/webhooks/telegram/cbq:1", json=body
    )
    cw = await cw_client.post(
        "/webhooks/telegram/cbq:1", json=body
    )
    assert 200 <= alo.status_code < 300
    assert 200 <= cw.status_code < 300


# Keep harness import live for body-shape parity additions later (e.g.
# once we expose the inbox/agent dashboards under /api/v2 we'll diff
# the rendered conversation JSON for a synthesised inbound message).
_ = assert_json_parity
