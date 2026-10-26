"""Instagram adapter: maps a publication onto the existing Instagram post
flow (``create_post`` + ``publish_post``)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

from app.core.models_registry import import_all_models
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram import publishing_service as ig
from app.domains.instagram.models import InstagramPost
from app.domains.publishing import service as svc
from app.domains.publishing.adapters.instagram import (
    InstagramAdapter,
    build_instagram_post,
)

import_all_models()

pytestmark = pytest.mark.integration

IMG_A = {"type": "image", "url": "https://cdn.example.com/a.jpg"}
IMG_B = {"type": "image", "url": "https://cdn.example.com/b.jpg"}
VIDEO = {"type": "video", "url": "https://cdn.example.com/v.mp4"}


async def _target(db_session, suffix: str, *, media: list, settings=None):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@pubig.example.com",
            account_name=f"PUBIG{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    inbox = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Insta",
                channel_type="instagram",
                channel_params={
                    "instagram_id": f"1784{abs(hash(suffix)) % 10_000_000}",
                    "access_token": "t",
                },
            ),
        ).perform()
    ).inbox
    publication = await svc.create_publication(
        db_session,
        account_id=owner.account.id,
        payload={
            "content": "Hola Instagram",
            "media": media,
            "scheduled_for": datetime.now(UTC) + timedelta(hours=1),
            "targets": [{"inbox_id": inbox.id, "settings": settings or {}}],
        },
    )
    (target,) = (
        await svc.targets_by_publication(db_session, publication_ids=[publication.id])
    )[publication.id]
    return publication, target, inbox


def _fake_publish(monkeypatch, *, state: str, error_code: str | None = None):
    calls: list[int] = []

    async def _publish(session, *, post_id, sleep_fn=None):
        calls.append(post_id)
        post = await session.get(InstagramPost, post_id)
        post.state = state
        if state == "published":
            post.ig_media_id = "IGMEDIA1"
            post.ig_permalink = "https://instagram.com/p/abc"
        else:
            post.error_code = error_code
            post.error_message = "falló en Meta"
        session.add(post)
        await session.flush()
        return post

    monkeypatch.setattr(ig, "publish_post", _publish)
    return calls


@pytest.mark.parametrize(
    ("media", "settings", "expected"),
    [
        ([IMG_A], {}, ("IMAGE", {"image_url": IMG_A["url"]})),
        ([VIDEO], {}, ("REELS", {"video_url": VIDEO["url"], "share_to_feed": True})),
        (
            [IMG_A, VIDEO],
            {},
            (
                "CAROUSEL",
                {"children": [{"image_url": IMG_A["url"]}, {"video_url": VIDEO["url"]}]},
            ),
        ),
        ([VIDEO], {"post_type": "reels"}, ("REELS", {"video_url": VIDEO["url"]})),
        ([IMG_B], {"post_type": "story"}, ("STORIES", {"image_url": IMG_B["url"]})),
    ],
)
async def test_maps_media_to_instagram_post_shape(db_session, media, settings, expected):
    publication, target, _ = await _target(
        db_session, f"-map{len(media)}{settings.get('post_type', '')}",
        media=media, settings=settings,
    )
    assert build_instagram_post(publication, target) == expected


async def test_validate_rules(db_session):
    publication, target, _ = await _target(db_session, "-val", media=[IMG_A])
    adapter = InstagramAdapter()

    target.settings = {"post_type": "reels"}
    assert any("reel" in e for e in adapter.validate(publication, target))

    target.settings = {"post_type": "story"}
    publication.media = [IMG_A, IMG_B]
    assert any("historia" in e for e in adapter.validate(publication, target))

    target.settings = {"post_type": "carrusel"}
    assert any("inválido" in e for e in adapter.validate(publication, target))

    target.settings = {}
    publication.media = [IMG_A] * 11
    assert any("hasta 10" in e for e in adapter.validate(publication, target))

    publication.media = [IMG_A]
    publication.content = "x" * 2201
    assert any("2200" in e for e in adapter.validate(publication, target))


async def test_publish_creates_and_publishes_an_instagram_post(db_session, monkeypatch):
    publication, target, inbox = await _target(db_session, "-pub", media=[IMG_A])
    calls = _fake_publish(monkeypatch, state="published")

    result = await InstagramAdapter().publish(db_session, publication, target)

    assert result.ok
    assert result.external_id == "IGMEDIA1"
    assert result.permalink == "https://instagram.com/p/abc"
    post = await db_session.get(InstagramPost, result.extra["instagram_post_id"])
    assert post.inbox_id == inbox.id
    assert post.media_type == "IMAGE"
    assert post.caption == "Hola Instagram"
    assert post.scheduled_for is None
    assert calls == [post.id]


async def test_throttle_is_retryable_and_retry_reuses_the_post(db_session, monkeypatch):
    publication, target, _ = await _target(db_session, "-thr", media=[IMG_A])
    _fake_publish(monkeypatch, state="failed", error_code="4")
    adapter = InstagramAdapter()

    first = await adapter.publish(db_session, publication, target)
    assert not first.ok
    assert first.retryable
    target.extra = first.extra

    calls = _fake_publish(monkeypatch, state="published")
    second = await adapter.publish(db_session, publication, target)

    assert second.ok
    assert second.extra == first.extra
    posts = (
        await db_session.exec(
            select(InstagramPost).where(InstagramPost.account_id == target.account_id)
        )
    ).all()
    assert len(posts) == 1
    assert calls == [posts[0].id]


async def test_other_failures_are_final(db_session, monkeypatch):
    publication, target, _ = await _target(db_session, "-fail", media=[IMG_A])
    _fake_publish(monkeypatch, state="failed", error_code="100")

    result = await InstagramAdapter().publish(db_session, publication, target)

    assert not result.ok
    assert not result.retryable
    assert result.error_message == "falló en Meta"
