"""Importing an Instagram account's past DMs when it connects.

* Every thread Meta lists (paged), with its recent messages: the
  customer's as incoming, the account's as outgoing, original dates.
* Quiet: resolved conversations, nothing sent.
* Named with the participant's username; a reaction-only message is
  skipped; files are stored like a webhook's.
* Running it again stores nothing twice.
* Instagram Login asks ``/me/conversations`` on graph.instagram.com.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx
from sqlmodel import select

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts.models import Contact
from app.domains.conversations.models import (
    CONVERSATION_STATUS_RESOLVED,
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Attachment,
    Conversation,
    Message,
)
from app.domains.inboxes.models import Inbox, InstagramChannel
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram import connect_service
from app.domains.instagram.history import HistoryError, import_history
from app.domains.teams import models as _teams  # noqa: F401  (mapper)

pytestmark = pytest.mark.integration

IG_ID = "17841400000000001"
PAGE_ID = "page-77"


async def _channel(db_session, suffix: str, *, login_type: str = "facebook"):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@ighist.example.com",
            account_name=f"IGH{suffix}",
            user_full_name="Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Tienda IG",
            channel_type="instagram",
            channel_params={
                "instagram_id": IG_ID + suffix,
                "access_token": "page-token",
                "expires_at": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
            },
        ),
    ).perform()
    channel = result.channel
    assert isinstance(channel, InstagramChannel)
    await connect_service.record_connection(
        db_session,
        channel_instagram_id=channel.id,
        login_type=login_type,
        connect_method="oauth",
        page_id=PAGE_ID if login_type == "facebook" else None,
    )
    return channel, result.inbox


def _thread(ours: str, igsid: str, username: str, messages: list[dict[str, Any]]) -> dict:
    return {
        "id": f"t-{igsid}",
        "updated_time": "2026-10-02T10:00:00+0000",
        "participants": {
            "data": [{"id": ours, "username": "tienda"}, {"id": igsid, "username": username}]
        },
        "messages": {"data": messages},
    }


def _msg(mid: str, sender: str, when: str, text: str | None = None, **extra) -> dict:
    out: dict[str, Any] = {"id": mid, "created_time": when, "from": {"id": sender}}
    if text is not None:
        out["message"] = text
    out.update(extra)
    return out


async def _messages(db_session, inbox: Inbox) -> list[Message]:
    return list(
        (
            await db_session.exec(
                select(Message).where(Message.inbox_id == inbox.id).order_by(Message.created_at)
            )
        ).all()
    )


async def test_facebook_login_imports_every_thread_quietly(db_session, monkeypatch):
    channel, inbox = await _channel(db_session, "-fb")
    ours = channel.instagram_id

    async def _stored(*, account_id, url, key_hint):
        return {"external_url": f"https://files.example.com/{key_hint[:6]}.jpg", "extension": "jpg"}

    monkeypatch.setattr("app.domains.instagram.incoming.download_and_store_ig_media", _stored)
    first_page = {
        "data": [
            _thread(
                ours,
                "igsid-ana",
                "ana.compra",
                [
                    # Meta lists newest first.
                    _msg("m3", ours, "2026-10-02T10:00:00+0000", "Te esperamos el lunes"),
                    _msg("m2", "igsid-ana", "2026-10-01T09:30:00+0000", "¿Tienen turnos?"),
                    _msg(
                        "m1",
                        "igsid-ana",
                        "2026-10-01T09:00:00+0000",
                        attachments={
                            "data": [{"image_data": {"url": "https://cdn.example.com/a.jpg"}}]
                        },
                    ),
                    _msg("m0", "igsid-ana", "2026-10-01T08:00:00+0000"),  # a reaction
                ],
            )
        ],
        "paging": {"next": "https://graph.facebook.com/v23.0/page-77/conversations?after=xyz"},
    }
    second_page = {
        "data": [
            _thread(
                ours,
                "igsid-beto",
                "beto",
                [_msg("m9", "igsid-beto", "2026-09-15T12:00:00+0000", "Hola")],
            )
        ]
    }
    with respx.mock(assert_all_called=False) as mock:
        listing = mock.get(url__regex=r"https://graph\.facebook\.com/.*/page-77/conversations.*")
        listing.side_effect = [
            httpx.Response(200, json=first_page),
            httpx.Response(200, json=second_page),
        ]
        result = await import_history(db_session, channel.id)

    assert result == {"conversations": 2, "messages": 4}
    first = listing.calls[0].request.url
    assert first.params["platform"] == "instagram"
    assert first.params["access_token"] == "page-token"

    rows = await _messages(db_session, inbox)
    assert [(m.source_id, m.message_type) for m in rows] == [
        ("m9", MESSAGE_TYPE_INCOMING),
        ("m1", MESSAGE_TYPE_INCOMING),
        ("m2", MESSAGE_TYPE_INCOMING),
        ("m3", MESSAGE_TYPE_OUTGOING),
    ]
    assert rows[-1].created_at == datetime(2026, 10, 2, 10, 0, tzinfo=UTC)
    assert all(m.content_attributes.get("imported_history") for m in rows)
    photo = (
        await db_session.exec(select(Attachment).where(Attachment.message_id == rows[1].id))
    ).all()
    assert len(photo) == 1

    conversations = (
        await db_session.exec(select(Conversation).where(Conversation.inbox_id == inbox.id))
    ).all()
    assert {c.status for c in conversations} == {CONVERSATION_STATUS_RESOLVED}
    names = {
        c.name
        for c in (
            await db_session.exec(select(Contact).where(Contact.account_id == channel.account_id))
        ).all()
    }
    assert names == {"ana.compra", "beto"}

    # Again (a reconnect): nothing twice.
    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__regex=r".*/page-77/conversations.*").mock(
            return_value=httpx.Response(200, json={"data": first_page["data"]})
        )
        again = await import_history(db_session, channel.id)
    assert again == {"conversations": 0, "messages": 0}
    assert len(await _messages(db_session, inbox)) == 4


async def test_instagram_login_asks_me_on_the_instagram_host(db_session):
    channel, _inbox = await _channel(db_session, "-igl", login_type="instagram")
    with respx.mock(assert_all_called=False) as mock:
        listing = mock.get(url__regex=r"https://graph\.instagram\.com/.*/me/conversations.*").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        _thread(
                            channel.instagram_id,
                            "igsid-caro",
                            "caro",
                            [_msg("n1", "igsid-caro", "2026-08-01T10:00:00+0000", "Hola!")],
                        )
                    ]
                },
            )
        )
        result = await import_history(db_session, channel.id)
    assert listing.called
    assert result == {"conversations": 1, "messages": 1}


async def test_a_refused_listing_raises_and_stores_nothing(db_session):
    channel, inbox = await _channel(db_session, "-err")
    with respx.mock(assert_all_called=False) as mock:
        mock.get(url__regex=r".*/page-77/conversations.*").mock(
            return_value=httpx.Response(
                400, json={"error": {"message": "Missing permission", "code": 10}}
            )
        )
        with pytest.raises(HistoryError):
            await import_history(db_session, channel.id)
    assert await _messages(db_session, inbox) == []
