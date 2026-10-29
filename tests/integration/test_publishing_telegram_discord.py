"""Telegram and Discord: networks connected by form (a bot token and a
channel, or a channel webhook), publishing and figures. Both APIs are
mocked with respx."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.publishing import service as svc
from app.domains.publishing.adapters.discord import DiscordAdapter
from app.domains.publishing.adapters.telegram import TelegramAdapter
from app.domains.publishing.models import PublishingChannel
from app.domains.teams import models as _teams  # noqa: F401
from app.main import app

pytestmark = pytest.mark.integration

TOKEN = "123:ABC"
BOT = f"https://api.telegram.org/bot{TOKEN}"
HOOK = "https://discord.com/api/webhooks/555/tok-en"
IMAGE = {"type": "image", "url": "https://cdn.example.com/a.jpg"}
VIDEO = {"type": "video", "url": "https://cdn.example.com/a.mp4"}


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


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@forms.example.com",
            account_name=f"FRM{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _channel(db_session, account, network: str, credentials: dict, **fields):
    channel = PublishingChannel(
        account_id=account.id, network=network, credentials=credentials, **fields
    )
    db_session.add(channel)
    await db_session.flush()
    return channel


async def _target(db_session, account, channel, *, content="Hola", media=None):
    publication = await svc.create_publication(
        db_session,
        account_id=account.id,
        payload={
            "content": content,
            "media": media or [],
            "scheduled_for": datetime.now(UTC) + timedelta(hours=1),
            "targets": [{"channel_id": channel.id}],
        },
    )
    (target,) = (
        await svc.targets_by_publication(db_session, publication_ids=[publication.id])
    )[publication.id]
    return publication, target


def _ok(result) -> httpx.Response:
    return httpx.Response(200, json={"ok": True, "result": result})


def _form(call) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(call.request.content.decode()).items()}


# ---------------------------------------------------------------------------
# Connecting by form
# ---------------------------------------------------------------------------
async def test_networks_describe_the_form(client, db_session):
    owner, h = await _seed(db_session, "-nets")

    r = await client.get(f"/api/v1/accounts/{owner.account.id}/publications/networks", headers=h)

    by_network = {n["network"]: n for n in r.json()}
    assert by_network["telegram"]["kind"] == "form"
    assert [f["name"] for f in by_network["telegram"]["fields"]] == ["bot_token", "chat"]
    assert by_network["telegram"]["fields"][0]["secret"] is True
    assert by_network["discord"]["kind"] == "form" and by_network["discord"]["configured"]
    assert by_network["threads"]["kind"] == "authorize"


@respx.mock
async def test_connect_telegram(client, db_session):
    owner, h = await _seed(db_session, "-tg")
    url = f"/api/v1/accounts/{owner.account.id}/publications/channels/connect/telegram"
    respx.post(f"{BOT}/getMe").mock(return_value=_ok({"id": 77, "is_bot": True}))
    get_chat = respx.post(f"{BOT}/getChat").mock(
        return_value=_ok({"id": -1001234, "title": "Mi canal", "username": "micanal", "type": "channel"})
    )
    respx.post(f"{BOT}/getChatMember").mock(
        return_value=_ok({"status": "administrator", "can_post_messages": True})
    )

    r = await client.post(url, headers=h, json={"fields": {"bot_token": TOKEN, "chat": "t.me/micanal"}})

    assert r.status_code == 200, r.text
    presented = r.json()["channel"]
    assert (presented["network"], presented["name"], presented["username"]) == (
        "telegram",
        "Mi canal",
        "micanal",
    )
    assert "credentials" not in presented
    assert _form(get_chat.calls[0])["chat_id"] == "@micanal"
    stored = await db_session.get(PublishingChannel, presented["id"])
    assert stored.external_id == "-1001234" and stored.credentials == {"bot_token": TOKEN}

    r = await client.post(url, headers=h, json={"fields": {"bot_token": TOKEN}})
    assert r.status_code == 422 and "Canal o grupo" in r.json()["message"]


@respx.mock
async def test_telegram_connection_problems(client, db_session):
    owner, h = await _seed(db_session, "-tgbad")
    url = f"/api/v1/accounts/{owner.account.id}/publications/channels/connect/telegram"
    get_me = respx.post(f"{BOT}/getMe").mock(
        return_value=httpx.Response(401, json={"ok": False, "error_code": 401, "description": "Unauthorized"})
    )
    r = await client.post(url, headers=h, json={"fields": {"bot_token": TOKEN, "chat": "@micanal"}})
    assert r.status_code == 422 and "token del bot no es válido" in r.json()["message"]

    get_me.mock(return_value=_ok({"id": 77}))
    respx.post(f"{BOT}/getChat").mock(return_value=_ok({"id": -1001234, "title": "Mi canal"}))
    respx.post(f"{BOT}/getChatMember").mock(return_value=_ok({"status": "member"}))
    r = await client.post(url, headers=h, json={"fields": {"bot_token": TOKEN, "chat": "@micanal"}})
    assert r.status_code == 422 and "no es administrador" in r.json()["message"]
    channels = (
        await db_session.exec(
            select(PublishingChannel).where(PublishingChannel.account_id == owner.account.id)
        )
    ).all()
    assert channels == []


@respx.mock
async def test_connect_discord(client, db_session):
    owner, h = await _seed(db_session, "-dc")
    url = f"/api/v1/accounts/{owner.account.id}/publications/channels/connect/discord"

    r = await client.post(url, headers=h, json={"fields": {"webhook_url": "https://example.com/x"}})
    assert r.status_code == 422 and "webhook de Discord" in r.json()["message"]

    respx.get(HOOK).mock(
        return_value=httpx.Response(
            200,
            json={"id": "555", "name": "Novedades", "channel_id": "9", "guild_id": "8", "avatar": None},
        )
    )
    r = await client.post(url, headers=h, json={"fields": {"webhook_url": HOOK}})

    assert r.status_code == 200, r.text
    stored = await db_session.get(PublishingChannel, r.json()["channel"]["id"])
    assert (stored.external_id, stored.name) == ("555", "Novedades")
    assert stored.credentials == {"webhook_url": HOOK, "guild_id": "8", "channel_id": "9"}


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
async def _telegram(db_session, account, **fields):
    return await _channel(
        db_session,
        account,
        "telegram",
        {"bot_token": TOKEN},
        external_id="-1001234",
        username="micanal",
        name="Mi canal",
        **fields,
    )


@respx.mock
async def test_telegram_text_photo_and_album(db_session):
    owner, _h = await _seed(db_session, "-tgpub")
    channel = await _telegram(db_session, owner.account)
    adapter = TelegramAdapter()
    send = respx.post(f"{BOT}/sendMessage").mock(return_value=_ok({"message_id": 10}))
    photo = respx.post(f"{BOT}/sendPhoto").mock(return_value=_ok({"message_id": 11}))
    album = respx.post(f"{BOT}/sendMediaGroup").mock(
        return_value=_ok([{"message_id": 12}, {"message_id": 13}])
    )

    publication, target = await _target(db_session, owner.account, channel)
    result = await adapter.publish(db_session, publication, target)
    assert result.ok and result.permalink == "https://t.me/micanal/10"
    assert _form(send.calls[0]) == {"chat_id": "-1001234", "text": "Hola"}

    publication, target = await _target(db_session, owner.account, channel, media=[IMAGE])
    result = await adapter.publish(db_session, publication, target)
    assert result.ok and result.external_id == "11"
    assert _form(photo.calls[0]) == {"chat_id": "-1001234", "photo": IMAGE["url"], "caption": "Hola"}

    publication, target = await _target(db_session, owner.account, channel, media=[IMAGE, VIDEO])
    result = await adapter.publish(db_session, publication, target)
    assert result.ok and result.permalink == "https://t.me/micanal/12"
    assert json.loads(_form(album.calls[0])["media"]) == [
        {"type": "photo", "media": IMAGE["url"], "caption": "Hola"},
        {"type": "video", "media": VIDEO["url"]},
    ]


@respx.mock
async def test_telegram_bot_removed_flags_reconnect(db_session):
    owner, _h = await _seed(db_session, "-tgkick")
    channel = await _telegram(db_session, owner.account)
    respx.post(f"{BOT}/sendMessage").mock(
        return_value=httpx.Response(
            403,
            json={"ok": False, "error_code": 403, "description": "Forbidden: bot was kicked"},
        )
    )
    publication, target = await _target(db_session, owner.account, channel)

    result = await TelegramAdapter().publish(db_session, publication, target)

    assert not result.ok and not result.retryable
    await db_session.refresh(channel)
    assert channel.status == "reconnect"
    assert TOKEN not in (result.error_message or "")


@respx.mock
async def test_telegram_figures_and_limits(db_session):
    owner, _h = await _seed(db_session, "-tgstats")
    channel = await _telegram(db_session, owner.account)
    adapter = TelegramAdapter()
    respx.post(f"{BOT}/getChatMemberCount").mock(return_value=_ok(321))

    figures = await adapter.fetch_channel_metrics(db_session, channel, days=[date(2026, 10, 28)])
    assert figures.metrics == {"followers": 321}

    publication, target = await _target(db_session, owner.account, channel, media=[IMAGE])
    publication.content = "x" * 1025
    assert "1024" in adapter.validate(publication, target)[0]
    publication.media = []
    assert adapter.validate(publication, target) == []
    publication.media = [IMAGE] * 11
    publication.content = "ok"
    assert "10" in adapter.validate(publication, target)[0]


# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------
async def _discord(db_session, account):
    return await _channel(
        db_session,
        account,
        "discord",
        {"webhook_url": HOOK, "guild_id": "8", "channel_id": "9"},
        external_id="555",
        name="Novedades",
    )


@respx.mock
async def test_discord_message_with_images_and_video(db_session):
    owner, _h = await _seed(db_session, "-dcpub")
    channel = await _discord(db_session, owner.account)
    route = respx.post(HOOK).mock(
        return_value=httpx.Response(200, json={"id": "999", "channel_id": "9"})
    )
    publication, target = await _target(
        db_session, owner.account, channel, media=[IMAGE, VIDEO]
    )

    result = await DiscordAdapter().publish(db_session, publication, target)

    assert result.ok, result.error_message
    assert result.permalink == "https://discord.com/channels/8/9/999"
    request = route.calls[0].request
    assert request.url.params["wait"] == "true"
    assert json.loads(request.content) == {
        "content": f"Hola\n{VIDEO['url']}",
        "embeds": [{"image": {"url": IMAGE["url"]}}],
    }


@respx.mock
async def test_discord_deleted_webhook_flags_reconnect(db_session):
    owner, _h = await _seed(db_session, "-dcgone")
    channel = await _discord(db_session, owner.account)
    respx.post(HOOK).mock(return_value=httpx.Response(404, json={"message": "Unknown Webhook"}))
    publication, target = await _target(db_session, owner.account, channel)

    result = await DiscordAdapter().publish(db_session, publication, target)

    assert not result.ok
    await db_session.refresh(channel)
    assert channel.status == "reconnect"

    publication.content = "x" * 2001
    assert "2000" in DiscordAdapter().validate(publication, target)[0]
