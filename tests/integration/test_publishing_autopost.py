"""Auto post: RSS / Atom entries become publications. Feeds are mocked with
respx."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.publishing import autopost
from app.domains.publishing import service as svc
from app.domains.publishing.models import Publication, PublishingAutopost
from app.domains.teams import models as _teams  # noqa: F401
from app.main import app
from tests.integration._publishing import channel_id_of

pytestmark = pytest.mark.integration

FEED = "https://blog.example.com/feed.xml"


def _rss(*items: tuple[str, str, str | None]) -> str:
    """``(guid, title, image_url)`` entries, newest first."""
    body = "".join(
        f"""<item><guid>{guid}</guid><title>{title}</title>
        <link>https://blog.example.com/{guid}</link>
        {f'<media:content url="{image}" medium="image"/>' if image else ""}
        </item>"""
        for guid, title, image in items
    )
    return f"""<?xml version="1.0"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>Blog</title>{body}</channel></rss>"""


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
            email=f"admin{suffix}@autopost.example.com",
            account_name=f"AUTO{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, tokens = create_new_auth_token(user_tokens=owner.user.tokens, uid=owner.user.uid)
    owner.user.tokens = tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _channels(db_session, account, suffix: str) -> tuple[int, int]:
    page = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=account,
                name="Pagina",
                channel_type="facebook",
                channel_params={"page_id": f"PG{suffix}", "page_access_token": "t"},
            ),
        ).perform()
    ).inbox
    insta = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=account,
                name="Insta",
                channel_type="instagram",
                channel_params={"instagram_id": f"1784{abs(hash(suffix)) % 10**7}", "access_token": "ig"},
            ),
        ).perform()
    ).inbox
    return await channel_id_of(db_session, page), await channel_id_of(db_session, insta)


async def _publications(db_session, account_id: int) -> list[Publication]:
    return list(
        (
            await db_session.exec(
                select(Publication)
                .where(Publication.account_id == account_id)
                .order_by(Publication.id)
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def test_parses_rss_and_atom():
    rss = autopost.parse_feed(_rss(("b", "Segunda", None), ("a", "Primera", "https://img/a.jpg")).encode())
    assert [(i.key, i.title, i.image_url) for i in rss] == [
        ("b", "Segunda", None),
        ("a", "Primera", "https://img/a.jpg"),
    ]
    atom = autopost.parse_feed(
        b"""<feed xmlns="http://www.w3.org/2005/Atom">
        <entry><id>tag:1</id><title>Viejo</title><updated>2026-10-01T10:00:00Z</updated>
          <link href="https://blog/1"/></entry>
        <entry><id>tag:2</id><title>Nuevo</title><updated>2026-10-02T10:00:00Z</updated>
          <link rel="alternate" href="https://blog/2"/>
          <link rel="enclosure" type="image/png" href="https://img/2.png"/></entry>
        </feed>"""
    )
    assert [(i.key, i.link, i.image_url) for i in atom] == [
        ("tag:2", "https://blog/2", "https://img/2.png"),
        ("tag:1", "https://blog/1", None),
    ]
    assert atom[0].published_at == datetime(2026, 10, 2, 10, tzinfo=UTC)
    with pytest.raises(autopost.FeedError):
        autopost.parse_feed(b"<html>no</html>")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@respx.mock
async def test_preview_and_create(client, db_session):
    owner, h = await _seed(db_session, "-api")
    page_id, _ig = await _channels(db_session, owner.account, "api")
    base = f"/api/v1/accounts/{owner.account.id}/publications/autoposts"
    respx.get(FEED).mock(return_value=httpx.Response(200, text=_rss(("a", "Hola", None))))

    r = await client.post(f"{base}/preview", headers=h, json={"feed_url": FEED})
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["title"] == "Hola"

    r = await client.post(
        base,
        headers=h,
        json={"name": "Blog", "feed_url": FEED, "mode": "draft", "channel_ids": [page_id]},
    )
    assert r.status_code == 200, r.text
    created = r.json()
    assert (created["mode"], created["channel_ids"], created["active"]) == ("draft", [page_id], True)

    r = await client.patch(f"{base}/{created['id']}", headers=h, json={"active": False})
    assert r.json()["active"] is False
    assert [a["name"] for a in (await client.get(base, headers=h)).json()] == ["Blog"]
    assert (await client.delete(f"{base}/{created['id']}", headers=h)).status_code == 200


@respx.mock
async def test_bad_feeds_and_values_are_refused(client, db_session):
    owner, h = await _seed(db_session, "-bad")
    other, _ = await _seed(db_session, "-bad2")
    foreign, _ig = await _channels(db_session, other.account, "bad2")
    base = f"/api/v1/accounts/{owner.account.id}/publications/autoposts"
    respx.get(FEED).mock(return_value=httpx.Response(200, text="<html>no es un feed</html>"))
    respx.get("https://blog.example.com/ok.xml").mock(
        return_value=httpx.Response(200, text=_rss(("a", "Hola", None)))
    )

    for body in (
        {"name": "x", "feed_url": FEED},
        {"name": "x", "feed_url": "http://127.0.0.1:8000/feed"},
        {"name": "x", "feed_url": "https://blog.example.com/ok.xml", "mode": "later"},
        {"name": "x", "feed_url": "https://blog.example.com/ok.xml", "channel_ids": [foreign]},
    ):
        r = await client.post(base, headers=h, json=body)
        assert r.status_code == 422, (body, r.text)


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------
async def _autopost(db_session, account, **fields) -> PublishingAutopost:
    row = PublishingAutopost(account_id=account.id, name="Blog", feed_url=FEED, **fields)
    db_session.add(row)
    await db_session.flush()
    return row


@respx.mock
async def test_new_entries_become_publications_on_the_channels_that_take_them(db_session):
    owner, _h = await _seed(db_session, "-sync")
    page_id, ig_id = await _channels(db_session, owner.account, "sync")
    row = await _autopost(db_session, owner.account)
    route = respx.get(FEED)

    # First read: remembers where the feed is, publishes nothing.
    route.mock(return_value=httpx.Response(200, text=_rss(("a", "Viejo", None))))
    assert await autopost.sync_autopost(db_session, row) == 0
    assert row.last_item_key == "a"

    route.mock(
        return_value=httpx.Response(
            200,
            text=_rss(("c", "Con foto", "https://img/c.jpg"), ("b", "Sin foto", None), ("a", "Viejo", None)),
        )
    )
    assert await autopost.sync_autopost(db_session, row) == 2
    assert row.last_item_key == "c"

    first, second = await _publications(db_session, owner.account.id)
    assert first.content == "Sin foto\n\nhttps://blog.example.com/b" and first.media == []
    assert second.media[0]["url"] == "https://img/c.jpg"
    targets = await svc.targets_by_publication(db_session, publication_ids=[first.id, second.id])
    # Instagram needs an image: the entry without one goes only to the page.
    assert [t.channel_id for t in targets[first.id]] == [page_id]
    assert sorted(t.channel_id for t in targets[second.id]) == sorted([page_id, ig_id])
    assert first.state == "scheduled"

    # Nothing new: nothing published.
    assert await autopost.sync_autopost(db_session, row) == 0


@respx.mock
async def test_drafts_first_entry_cap_and_errors(db_session):
    owner, _h = await _seed(db_session, "-draft")
    page_id, _ig = await _channels(db_session, owner.account, "draft")
    row = await _autopost(
        db_session, owner.account, mode="draft", start_with_latest=True, channel_ids=[page_id]
    )
    route = respx.get(FEED)
    route.mock(return_value=httpx.Response(200, text=_rss(("z", "Ultima", None), ("y", "Anterior", None))))

    assert await autopost.sync_autopost(db_session, row) == 1
    (only,) = await _publications(db_session, owner.account.id)
    assert (only.state, only.content.split("\n")[0]) == ("draft", "Ultima")

    burst = [(f"n{i}", f"Entrada {i}", None) for i in range(10, 0, -1)] + [("z", "Ultima", None)]
    route.mock(return_value=httpx.Response(200, text=_rss(*burst)))
    assert await autopost.sync_autopost(db_session, row) == autopost.MAX_PER_RUN
    assert row.last_item_key == "n10"

    route.mock(return_value=httpx.Response(500))
    assert await autopost.sync_autopost(db_session, row) == 0
    assert "error" in row.last_error and row.last_checked_at is not None
