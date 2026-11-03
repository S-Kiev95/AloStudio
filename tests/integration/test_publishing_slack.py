"""Slack: a channel connected by form (an incoming webhook and the channel's
name) and publishing to it. Slack is mocked with respx."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.db import get_session
from app.domains.publishing.adapters.slack import SlackAdapter
from app.domains.publishing.models import PublishingChannel
from app.main import app
from tests.integration.test_publishing_telegram_discord import (
    IMAGE,
    VIDEO,
    _channel,
    _seed,
    _target,
)

pytestmark = pytest.mark.integration

HOOK = "https://hooks.slack.com/services/T0001/B0002/secretXYZ"


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


async def _slack(db_session, account):
    return await _channel(
        db_session,
        account,
        "slack",
        {"webhook_url": HOOK, "team_id": "T0001"},
        external_id="B0002",
        name="#novedades",
    )


@respx.mock
async def test_connect_slack(client, db_session):
    owner, h = await _seed(db_session, "-sl")
    url = f"/api/v1/accounts/{owner.account.id}/publications/channels/connect/slack"

    r = await client.post(
        url, headers=h, json={"fields": {"webhook_url": "https://example.com/x", "channel_name": "x"}}
    )
    assert r.status_code == 422 and "webhook de Slack" in r.json()["message"]

    # A revoked webhook.
    respx.post(HOOK).mock(return_value=httpx.Response(403, text="invalid_token"))
    r = await client.post(
        url, headers=h, json={"fields": {"webhook_url": HOOK, "channel_name": "novedades"}}
    )
    assert r.status_code == 422 and "no reconoce" in r.json()["message"]

    # A live one refuses the empty message without posting it.
    probe = respx.post(HOOK).mock(return_value=httpx.Response(400, text="no_text"))
    r = await client.post(
        url, headers=h, json={"fields": {"webhook_url": HOOK, "channel_name": "novedades"}}
    )

    assert r.status_code == 200, r.text
    assert json.loads(probe.calls[-1].request.content) == {}
    stored = await db_session.get(PublishingChannel, r.json()["channel"]["id"])
    assert (stored.external_id, stored.name) == ("B0002", "#novedades")
    assert stored.credentials == {"webhook_url": HOOK, "team_id": "T0001"}


@respx.mock
async def test_slack_message_with_images_and_video(db_session):
    owner, _h = await _seed(db_session, "-slpub")
    channel = await _slack(db_session, owner.account)
    route = respx.post(HOOK).mock(return_value=httpx.Response(200, text="ok"))
    publication, target = await _target(
        db_session, owner.account, channel, content="Hola <equipo> & co", media=[IMAGE, VIDEO]
    )

    result = await SlackAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    text = f"Hola &lt;equipo&gt; &amp; co\n{VIDEO['url']}"
    assert json.loads(route.calls[0].request.content) == {
        "text": text,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "image", "image_url": IMAGE["url"], "alt_text": "imagen"},
        ],
    }


@respx.mock
async def test_slack_revoked_webhook_flags_reconnect(db_session):
    owner, _h = await _seed(db_session, "-slgone")
    channel = await _slack(db_session, owner.account)
    respx.post(HOOK).mock(return_value=httpx.Response(404, text="no_service"))
    publication, target = await _target(db_session, owner.account, channel)

    result = await SlackAdapter().publish(db_session, publication, target)

    assert not result.ok
    await db_session.refresh(channel)
    assert channel.status == "reconnect"

    publication.content = "x" * 3001
    assert "3000" in SlackAdapter().validate(publication, target)[0]
    publication.content = "Hola"
    publication.media = [IMAGE] * 11
    assert "10 imágenes" in SlackAdapter().validate(publication, target)[0]


@respx.mock
async def test_slack_webhook_to_a_direct_message_is_not_retried(db_session):
    owner, _h = await _seed(db_session, "-sldm")
    channel = await _slack(db_session, owner.account)
    # Slack answers this setup error with a 500.
    respx.post(HOOK).mock(return_value=httpx.Response(500, text="messages_tab_disabled"))
    publication, target = await _target(db_session, owner.account, channel)

    result = await SlackAdapter().publish(db_session, publication, target)

    assert not result.ok and not result.retryable
    assert "mensaje directo" in result.error_message
    await db_session.refresh(channel)
    assert channel.status == "reconnect"
