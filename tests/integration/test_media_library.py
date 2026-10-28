"""Integration tests for the media library and its use in publications.

The object store is replaced by an in-memory stand-in: these tests are
about the library's rules (conversion, scoping, in-use protection, fresh
links at publish time), not about MinIO.
"""

from __future__ import annotations

import io
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.media_library import service as media_svc
from app.domains.media_library.models import MediaAsset
from app.domains.publishing import service as pub_svc
from app.domains.publishing.adapters import PublishResult
from app.domains.publishing.adapters.facebook_page import FacebookPageAdapter
from app.domains.publishing.models import Publication
from app.domains.teams import models as _teams  # noqa: F401
from app.domains.uploads.public_router import public_media_url
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
from app.main import app
from app.workers import publishing as publishing_worker
from tests.integration._publishing import channel_id_of

pytestmark = pytest.mark.integration


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


@pytest.fixture
def store(monkeypatch) -> dict[str, bytes]:
    """In-memory object store: key → bytes."""
    objects: dict[str, bytes] = {}
    counter = iter(range(1, 10_000))

    async def _store(account_id, *, filename, content_type, data):
        key = f"accounts/{account_id}/uploads/k{next(counter)}/{filename}"
        objects[key] = data
        return {"key": key, "file_url": f"http://minio/{key}"}

    async def _delete(key):
        objects.pop(key, None)

    async def _no_enqueue(publication_id):
        return None

    monkeypatch.setattr(media_svc, "store_upload_blob", _store)
    monkeypatch.setattr(media_svc, "delete_object", _delete)
    monkeypatch.setattr(publishing_worker, "enqueue_publication", _no_enqueue)
    return objects


async def _seed_admin(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@media.example.com",
            account_name=f"MEDIA{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def _seed_agent(db_session, account_id: int, suffix: str):
    other, _ = await _seed_admin(db_session, f"{suffix}-agent")
    db_session.add(
        AccountUser(
            account_id=account_id, user_id=other.user.id, role=ACCOUNT_USER_ROLE_AGENT
        )
    )
    await db_session.flush()
    headers, new_tokens = create_new_auth_token(
        user_tokens=other.user.tokens, uid=other.user.uid
    )
    other.user.tokens = new_tokens
    db_session.add(other.user)
    await db_session.flush()
    return headers.as_response_headers()


async def _page(db_session, account, suffix: str):
    return (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=account,
                name="Pagina",
                channel_type="facebook",
                channel_params={"page_id": f"P{suffix}", "page_access_token": "t"},
            ),
        ).perform()
    ).inbox


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (40, 30), (10, 120, 200, 128)).save(buf, format="PNG")
    return buf.getvalue()


async def _upload(client, account_id, h, *, name="foto.png", data=None, ctype="image/png"):
    return await client.post(
        f"/api/v1/accounts/{account_id}/media",
        headers=h,
        files={"file": (name, data if data is not None else _png(), ctype)},
    )


def _future() -> str:
    return (datetime.now(UTC) + timedelta(hours=2)).isoformat()


async def test_image_is_stored_as_jpeg(client, db_session, store):
    owner, h = await _seed_admin(db_session, "-img")

    r = await _upload(client, owner.account.id, h)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "image"
    assert body["filename"] == "foto.jpg"
    assert body["content_type"] == "image/jpeg"
    assert "/public/media?key=" in body["url"]
    (stored,) = store.values()
    assert stored[:3] == b"\xff\xd8\xff"  # JPEG magic


async def test_video_is_stored_as_is(client, db_session, store):
    owner, h = await _seed_admin(db_session, "-vid")

    r = await _upload(
        client, owner.account.id, h, name="clip.mov", data=b"\x00\x00video", ctype=""
    )

    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "video"
    assert r.json()["filename"] == "clip.mov"
    assert list(store.values()) == [b"\x00\x00video"]


async def test_unreadable_file_is_rejected(client, db_session, store):
    owner, h = await _seed_admin(db_session, "-bad")

    r = await _upload(
        client, owner.account.id, h, name="doc.pdf", data=b"%PDF-1.4", ctype="application/pdf"
    )

    assert r.status_code == 422
    assert store == {}


async def test_oversized_image_is_refused_before_storing(client, db_session, store, monkeypatch):
    owner, h = await _seed_admin(db_session, "-big")
    monkeypatch.setattr(media_svc, "MAX_IMAGE_BYTES", 100)

    r = await _upload(client, owner.account.id, h)

    assert r.status_code == 422
    assert "MB" in r.json()["message"]
    assert store == {}


async def test_boolean_media_id_is_not_an_asset(client, db_session, store):
    owner, h = await _seed_admin(db_session, "-bool")
    page = await _page(db_session, owner.account, "bool")
    await _upload(client, owner.account.id, h)

    r = await client.post(
        f"/api/v1/accounts/{owner.account.id}/publications",
        headers=h,
        json={
            "content": "x",
            "media": [{"media_id": True}],
            "scheduled_for": _future(),
            "targets": [{"channel_id": await channel_id_of(db_session, page)}],
        },
    )
    assert r.status_code == 422


async def test_list_is_scoped_newest_first_and_filters_kind(client, db_session, store):
    owner, h = await _seed_admin(db_session, "-list")
    other, other_h = await _seed_admin(db_session, "-list-other")
    first = (await _upload(client, owner.account.id, h)).json()
    video = (
        await _upload(client, owner.account.id, h, name="a.mp4", data=b"v", ctype="video/mp4")
    ).json()
    await _upload(client, other.account.id, other_h)
    url = f"/api/v1/accounts/{owner.account.id}/media"

    r = await client.get(url, headers=h)
    assert [a["id"] for a in r.json()] == [video["id"], first["id"]]
    r = await client.get(url, headers=h, params={"kind": "image"})
    assert [a["id"] for a in r.json()] == [first["id"]]
    r = await client.get(url, headers=h, params={"kind": "gif"})
    assert r.status_code == 422


async def test_only_admins_delete_and_the_object_goes_too(client, db_session, store):
    owner, h = await _seed_admin(db_session, "-del")
    agent_h = await _seed_agent(db_session, owner.account.id, "-del")
    asset = (await _upload(client, owner.account.id, h)).json()
    url = f"/api/v1/accounts/{owner.account.id}/media/{asset['id']}"

    assert (await client.delete(url, headers=agent_h)).status_code == 401
    assert (await client.delete(url, headers=h)).status_code == 200
    assert store == {}
    assert await db_session.get(MediaAsset, asset["id"]) is None
    assert (await client.delete(url, headers=h)).status_code == 404


async def test_publication_uses_library_media(client, db_session, store):
    owner, h = await _seed_admin(db_session, "-pub")
    other, other_h = await _seed_admin(db_session, "-pub-other")
    page = await _page(db_session, owner.account, "pub")
    asset = (await _upload(client, owner.account.id, h)).json()
    foreign = (await _upload(client, other.account.id, other_h)).json()
    url = f"/api/v1/accounts/{owner.account.id}/publications"

    r = await client.post(
        url,
        headers=h,
        json={
            "content": "con foto",
            "media": [{"media_id": asset["id"]}],
            "scheduled_for": _future(),
            "targets": [{"channel_id": await channel_id_of(db_session, page)}],
        },
    )
    assert r.status_code == 200, r.text
    (item,) = r.json()["media"]
    assert item["media_id"] == asset["id"]
    assert item["type"] == "image"
    assert "/public/media?key=" in item["url"]

    r = await client.post(
        url,
        headers=h,
        json={
            "content": "ajena",
            "media": [{"media_id": foreign["id"]}],
            "scheduled_for": _future(),
            "targets": [{"channel_id": await channel_id_of(db_session, page)}],
        },
    )
    assert r.status_code == 422


async def test_media_in_a_pending_publication_cannot_be_deleted(client, db_session, store):
    owner, h = await _seed_admin(db_session, "-inuse")
    page = await _page(db_session, owner.account, "inuse")
    asset = (await _upload(client, owner.account.id, h)).json()
    created = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/publications",
            headers=h,
            json={
                "content": "x",
                "media": [{"media_id": asset["id"]}],
                "scheduled_for": _future(),
                "targets": [{"channel_id": await channel_id_of(db_session, page)}],
            },
        )
    ).json()
    url = f"/api/v1/accounts/{owner.account.id}/media/{asset['id']}"

    assert (await client.delete(url, headers=h)).status_code == 422

    publication = await db_session.get(Publication, created["id"])
    publication.state = "published"
    db_session.add(publication)
    await db_session.flush()
    assert (await client.delete(url, headers=h)).status_code == 200


@respx.mock
async def test_public_link_streams_the_stored_file(client):
    key = "accounts/1/uploads/k1/clip.mp4"
    respx.get(url__startswith=get_settings().s3_endpoint_url.rstrip("/")).mock(
        return_value=httpx.Response(
            200, content=b"video-bytes", headers={"content-length": "11"}
        )
    )
    link = public_media_url(key).split("/public/media", 1)[1]

    r = await client.get(f"/public/media{link}")

    assert r.status_code == 200
    assert r.content == b"video-bytes"
    assert r.headers["content-type"] == "video/mp4"

    r = await client.get(f"/public/media{link[:-4]}xxxx")
    assert r.status_code == 404


@respx.mock
async def test_public_link_to_a_missing_object_is_404(client):
    respx.get(url__startswith=get_settings().s3_endpoint_url.rstrip("/")).mock(
        return_value=httpx.Response(404)
    )
    link = public_media_url("accounts/1/uploads/k2/x.jpg").split("/public/media", 1)[1]

    r = await client.get(f"/public/media{link}")

    assert r.status_code == 404


async def test_links_are_signed_again_when_publishing(db_session, store, monkeypatch):
    owner, _ = await _seed_admin(db_session, "-fresh")
    page = await _page(db_session, owner.account, "fresh")
    asset = await media_svc.upload_asset(
        db_session, account_id=owner.account.id, filename="a.png",
        content_type="image/png", data=_png(),
    )
    publication = await pub_svc.create_publication(
        db_session,
        account_id=owner.account.id,
        payload={
            "content": "x",
            "media": [{"media_id": asset.id}],
            "scheduled_for": datetime.now(UTC) + timedelta(hours=1),
            "targets": [{"channel_id": await channel_id_of(db_session, page)}],
        },
    )
    publication.scheduled_for = datetime.now(UTC) - timedelta(minutes=1)
    db_session.add(publication)
    await db_session.flush()
    assert await pub_svc.start_publishing(db_session, publication_id=publication.id)

    seen: list[str] = []

    async def _publish(self, session, publication, target):
        seen.append(publication.media[0]["url"])
        return PublishResult(ok=True, external_id="P_1")

    monkeypatch.setattr(FacebookPageAdapter, "publish", _publish)
    monkeypatch.setattr(media_svc, "asset_public_url", lambda a: f"https://fresh/{a.key}")

    await pub_svc.publish_pending_targets(db_session, publication_id=publication.id)

    assert seen == [f"https://fresh/{asset.key}"]


async def test_deleted_media_fails_the_publication(db_session, store, monkeypatch):
    owner, _ = await _seed_admin(db_session, "-gone")
    page = await _page(db_session, owner.account, "gone")
    asset = await media_svc.upload_asset(
        db_session, account_id=owner.account.id, filename="a.png",
        content_type="image/png", data=_png(),
    )
    publication = await pub_svc.create_publication(
        db_session,
        account_id=owner.account.id,
        payload={
            "content": "x",
            "media": [{"media_id": asset.id}],
            "scheduled_for": datetime.now(UTC) + timedelta(hours=1),
            "targets": [{"channel_id": await channel_id_of(db_session, page)}],
        },
    )
    publication.scheduled_for = datetime.now(UTC) - timedelta(minutes=1)
    db_session.add(publication)
    await db_session.delete(asset)  # gone behind the in-use check's back
    await db_session.flush()
    assert await pub_svc.start_publishing(db_session, publication_id=publication.id)
    calls: list[int] = []

    async def _publish(self, session, publication, target):
        calls.append(target.id)
        return PublishResult(ok=True)

    monkeypatch.setattr(FacebookPageAdapter, "publish", _publish)

    await pub_svc.publish_pending_targets(db_session, publication_id=publication.id)

    await db_session.refresh(publication)
    assert publication.state == "failed"
    assert calls == []
    (target,) = (
        await pub_svc.targets_by_publication(db_session, publication_ids=[publication.id])
    )[publication.id]
    assert target.error_code == "missing_media"
