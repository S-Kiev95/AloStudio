"""The private-reply send, and what it reports back.

Reading the response matters: a comment carries no IGSID, so Meta's
``recipient_id`` is the first moment we learn who the reply reached, and
``message_id`` is the key that keeps the echo from landing twice.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.core.models_registry import import_all_models
from app.domains.inboxes.models import InstagramChannel
from app.domains.instagram.sender import send_private_reply_instagram

pytestmark = pytest.mark.unit

# Instantiating a channel configures the mappers, which need every model.
import_all_models()

SEND_URL = (
    f"https://graph.facebook.com/{get_settings().facebook_api_version}/me/messages"
)


@pytest.fixture
def channel() -> InstagramChannel:
    return InstagramChannel(
        id=1,
        account_id=1,
        instagram_id="IG-BIZ",
        access_token="PAGE-TOKEN",  # a fixture value, not a credential
    )


async def _send(channel: InstagramChannel):
    return await send_private_reply_instagram(
        channel=channel, ig_comment_id="CMT-1", text="acá va el link"
    )


@respx.mock
async def test_reports_the_recipient_and_the_mid(channel):
    route = respx.post(SEND_URL).mock(
        return_value=httpx.Response(
            200, json={"recipient_id": "IGSID-9", "message_id": "MID-9"}
        )
    )
    result = await _send(channel)
    assert result.ok
    assert result.recipient_igsid == "IGSID-9"
    assert result.message_id == "MID-9"
    # Addressed by comment, not by user — that is what a private reply is.
    body = json.loads(respx.calls.last.request.content)
    assert body["recipient"] == {"comment_id": "CMT-1"}
    assert route.called


@respx.mock
async def test_a_result_is_truthy_when_it_succeeded(channel):
    """Callers written against the old bool return keep working."""
    respx.post(SEND_URL).mock(
        return_value=httpx.Response(200, json={"recipient_id": "X"})
    )
    assert bool(await _send(channel)) is True


@respx.mock
async def test_an_api_error_is_reported_not_raised(channel):
    respx.post(SEND_URL).mock(
        return_value=httpx.Response(
            400, json={"error": {"message": "outside the allowed window"}}
        )
    )
    result = await _send(channel)
    assert result.ok is False
    assert bool(result) is False
    assert result.recipient_igsid is None


@respx.mock
async def test_a_transport_failure_is_reported_not_raised(channel):
    respx.post(SEND_URL).mock(side_effect=httpx.ConnectError("boom"))
    assert (await _send(channel)).ok is False


@respx.mock
async def test_an_unparseable_body_still_counts_as_sent(channel):
    """The reply reached the person; we just cannot file it."""
    respx.post(SEND_URL).mock(return_value=httpx.Response(200, text="not json"))
    result = await _send(channel)
    assert result.ok is True
    assert result.recipient_igsid is None
    assert result.message_id is None
