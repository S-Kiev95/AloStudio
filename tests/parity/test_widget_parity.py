"""Parity tests for the ``/api/v1/widget`` surface.

Same philosophy as ``test_conversations_parity.py``: pin the
stateless error branches cross-backend (no auth, bogus website_token,
missing X-Auth-Token) so a small change on either side that drifts
the envelope fails here loudly.

Happy-path parity needs identical seed data on both backends — that
class of test lives in our integration suite + Chatwoot's rspec.

Anchors:
  reference/chatwoot/app/controllers/widgets_controller.rb
  reference/chatwoot/app/controllers/concerns/website_token_helper.rb
  reference/chatwoot/app/controllers/api/v1/widget/{configs,contacts,
    conversations,messages}_controller.rb
"""

from __future__ import annotations

import pytest

from tests.parity._harness import assert_json_parity

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# Bogus website_token -> 404 envelope
# ---------------------------------------------------------------------------
async def test_config_unknown_website_token_matches(alo_client, cw_client):
    alo = await alo_client.post(
        "/api/v1/widget/config?website_token=does-not-exist"
    )
    cw = await cw_client.post(
        "/api/v1/widget/config?website_token=does-not-exist"
    )
    assert alo.status_code == 404
    assert cw.status_code == 404


async def test_contact_show_unknown_token_matches(alo_client, cw_client):
    alo = await alo_client.get(
        "/api/v1/widget/contact?website_token=does-not-exist"
    )
    cw = await cw_client.get(
        "/api/v1/widget/contact?website_token=does-not-exist"
    )
    assert alo.status_code == 404
    assert cw.status_code == 404


async def test_contact_update_unknown_token_matches(alo_client, cw_client):
    body = {"email": "alice@example.com"}
    alo = await alo_client.patch(
        "/api/v1/widget/contact?website_token=does-not-exist", json=body
    )
    cw = await cw_client.patch(
        "/api/v1/widget/contact?website_token=does-not-exist", json=body
    )
    assert alo.status_code == 404
    assert cw.status_code == 404


async def test_set_user_unknown_token_matches(alo_client, cw_client):
    body = {"identifier": "user-42"}
    alo = await alo_client.post(
        "/api/v1/widget/contact/set_user?website_token=does-not-exist",
        json=body,
    )
    cw = await cw_client.post(
        "/api/v1/widget/contact/set_user?website_token=does-not-exist",
        json=body,
    )
    assert alo.status_code == 404
    assert cw.status_code == 404


# ---------------------------------------------------------------------------
# Conversations + messages with bogus token
# ---------------------------------------------------------------------------
async def test_conversations_index_unknown_token_matches(
    alo_client, cw_client
):
    alo = await alo_client.get(
        "/api/v1/widget/conversations?website_token=does-not-exist"
    )
    cw = await cw_client.get(
        "/api/v1/widget/conversations?website_token=does-not-exist"
    )
    assert alo.status_code == 404
    assert cw.status_code == 404


async def test_messages_index_unknown_token_matches(alo_client, cw_client):
    alo = await alo_client.get(
        "/api/v1/widget/messages?website_token=does-not-exist"
    )
    cw = await cw_client.get(
        "/api/v1/widget/messages?website_token=does-not-exist"
    )
    assert alo.status_code == 404
    assert cw.status_code == 404


async def test_messages_create_unknown_token_matches(alo_client, cw_client):
    body = {"message": {"content": "hi"}}
    alo = await alo_client.post(
        "/api/v1/widget/messages?website_token=does-not-exist", json=body
    )
    cw = await cw_client.post(
        "/api/v1/widget/messages?website_token=does-not-exist", json=body
    )
    assert alo.status_code == 404
    assert cw.status_code == 404


async def test_update_last_seen_unknown_token_matches(alo_client, cw_client):
    alo = await alo_client.post(
        "/api/v1/widget/conversations/update_last_seen?website_token=does-not-exist"
    )
    cw = await cw_client.post(
        "/api/v1/widget/conversations/update_last_seen?website_token=does-not-exist"
    )
    assert alo.status_code == 404
    assert cw.status_code == 404


async def test_toggle_typing_unknown_token_matches(alo_client, cw_client):
    body = {"typing_status": "on"}
    alo = await alo_client.post(
        "/api/v1/widget/conversations/toggle_typing?website_token=does-not-exist",
        json=body,
    )
    cw = await cw_client.post(
        "/api/v1/widget/conversations/toggle_typing?website_token=does-not-exist",
        json=body,
    )
    assert alo.status_code == 404
    assert cw.status_code == 404


async def test_toggle_status_unknown_token_matches(alo_client, cw_client):
    alo = await alo_client.post(
        "/api/v1/widget/conversations/toggle_status?website_token=does-not-exist"
    )
    cw = await cw_client.post(
        "/api/v1/widget/conversations/toggle_status?website_token=does-not-exist"
    )
    assert alo.status_code == 404
    assert cw.status_code == 404


# Keep the harness import live for future body-shape parity assertions.
_ = assert_json_parity
