"""Integration tests for Milestone I.1 — Instagram publishing
schema + service skeletons.

Scope: model persistence, FK cascades, state-machine transitions,
``source`` JSONB shape validation, comment upsert idempotency.

NO Meta API calls — those land in I.2+. The stub functions in
``publishing_service`` raise ``NotImplementedError`` for now and we
verify that contract here too so a future regression catches the
day we promote them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

from app.core.errors import ChatwootHTTPException
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.models import InstagramChannel
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram import publishing_service as svc
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.conversations import models as _conversations  # noqa: F401  (mapper)
from app.domains.instagram.models import (
    InstagramComment,
    InstagramPost,
    InstagramPostContainer,
)
from app.domains.teams import models as _teams  # noqa: F401  (mapper)

pytestmark = pytest.mark.integration


async def _seed_channel(db_session, suffix: str):
    """Seed an account + IG inbox + channel row that posts can FK into."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@ig.example.com",
            account_name=f"IG{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"IG Inbox{suffix}",
            channel_type="instagram",
            channel_params={
                "instagram_id": f"ig-id-{suffix}",
                "access_token": "test-token-not-real",
                "expires_at": (
                    datetime.now(UTC) + timedelta(days=60)
                ).isoformat(),
            },
        ),
    ).perform()
    assert isinstance(result.channel, InstagramChannel)
    return owner, result.inbox, result.channel


# ---------------------------------------------------------------------------
# create_post — validation + round-trip
# ---------------------------------------------------------------------------
async def test_create_post_image_happy_path(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-img")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="IMAGE",
        source={"image_url": "https://cdn.example.com/p.jpg"},
        caption="My first post",
    )
    assert post.id is not None
    assert post.state == "pending"
    assert post.media_type == "IMAGE"
    assert post.source == {"image_url": "https://cdn.example.com/p.jpg"}
    assert post.caption == "My first post"
    assert post.published_at is None


async def test_create_post_rejects_unknown_media_type(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-bm")
    with pytest.raises(ChatwootHTTPException) as exc:
        await svc.create_post(
            db_session,
            account_id=owner.account.id,
            inbox_id=inbox.id,
            channel_instagram_id=channel.id,
            media_type="FROBNICATE",
            source={"image_url": "https://x.example.com/p.jpg"},
        )
    assert exc.value.status_code == 422


async def test_create_post_image_requires_image_url(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-noimg")
    with pytest.raises(ChatwootHTTPException) as exc:
        await svc.create_post(
            db_session,
            account_id=owner.account.id,
            inbox_id=inbox.id,
            channel_instagram_id=channel.id,
            media_type="IMAGE",
            source={"caption": "no url"},  # missing image_url
        )
    assert exc.value.status_code == 422
    assert "image_url" in exc.value.detail["message"]


async def test_create_post_video_requires_video_url(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-novid")
    with pytest.raises(ChatwootHTTPException) as exc:
        await svc.create_post(
            db_session,
            account_id=owner.account.id,
            inbox_id=inbox.id,
            channel_instagram_id=channel.id,
            media_type="VIDEO",
            source={},
        )
    assert exc.value.status_code == 422


async def test_create_post_reel_happy_path(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-reel")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="REELS",
        source={
            "video_url": "https://cdn.example.com/v.mp4",
            "share_to_feed": True,
            "cover_url": "https://cdn.example.com/cover.jpg",
        },
        caption="Reel test",
    )
    assert post.media_type == "REELS"
    assert post.source["share_to_feed"] is True


async def test_create_post_carousel_happy_path(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-car")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="CAROUSEL",
        source={
            "children": [
                {"image_url": "https://x.example.com/1.jpg"},
                {"image_url": "https://x.example.com/2.jpg"},
                {"video_url": "https://x.example.com/3.mp4"},
            ]
        },
    )
    assert post.media_type == "CAROUSEL"
    assert len(post.source["children"]) == 3


async def test_create_post_carousel_rejects_empty_children(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-car-empty")
    with pytest.raises(ChatwootHTTPException) as exc:
        await svc.create_post(
            db_session,
            account_id=owner.account.id,
            inbox_id=inbox.id,
            channel_instagram_id=channel.id,
            media_type="CAROUSEL",
            source={"children": []},
        )
    assert exc.value.status_code == 422


async def test_create_post_carousel_caps_at_10_children(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-car-11")
    eleven = [
        {"image_url": f"https://x.example.com/{i}.jpg"} for i in range(11)
    ]
    with pytest.raises(ChatwootHTTPException) as exc:
        await svc.create_post(
            db_session,
            account_id=owner.account.id,
            inbox_id=inbox.id,
            channel_instagram_id=channel.id,
            media_type="CAROUSEL",
            source={"children": eleven},
        )
    assert exc.value.status_code == 422


async def test_create_post_stories_accepts_image_or_video(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-st")
    img = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="STORIES",
        source={"image_url": "https://x.example.com/s.jpg"},
    )
    assert img.media_type == "STORIES"
    vid = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="STORIES",
        source={"video_url": "https://x.example.com/s.mp4"},
    )
    assert vid.media_type == "STORIES"


async def test_caption_caps_at_2200_chars(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-cap")
    with pytest.raises(ChatwootHTTPException) as exc:
        await svc.create_post(
            db_session,
            account_id=owner.account.id,
            inbox_id=inbox.id,
            channel_instagram_id=channel.id,
            media_type="IMAGE",
            source={"image_url": "https://x.example.com/x.jpg"},
            caption="x" * 2201,
        )
    assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------
async def test_transition_pending_to_publishing(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-sm1")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="IMAGE",
        source={"image_url": "https://x.example.com/x.jpg"},
    )
    await svc.transition_post_state(
        db_session, post=post, new_state="publishing"
    )
    await db_session.refresh(post)
    assert post.state == "publishing"


async def test_transition_publishing_to_published_stamps_ids(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-sm2")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="IMAGE",
        source={"image_url": "https://x.example.com/x.jpg"},
    )
    await svc.transition_post_state(
        db_session, post=post, new_state="publishing"
    )
    now = datetime.now(UTC)
    await svc.transition_post_state(
        db_session,
        post=post,
        new_state="published",
        ig_media_id="17841234567890123",
        ig_permalink="https://www.instagram.com/p/abc123/",
        published_at=now,
    )
    await db_session.refresh(post)
    assert post.state == "published"
    assert post.ig_media_id == "17841234567890123"
    assert post.published_at is not None


async def test_transition_rejects_illegal_jump(db_session):
    """pending → published is not allowed (must go through publishing)."""
    owner, inbox, channel = await _seed_channel(db_session, "-illegal")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="IMAGE",
        source={"image_url": "https://x.example.com/x.jpg"},
    )
    with pytest.raises(ChatwootHTTPException) as exc:
        await svc.transition_post_state(
            db_session, post=post, new_state="published"
        )
    assert exc.value.status_code == 422


async def test_transition_failed_to_pending_for_retry(db_session):
    """Operator-driven retry path."""
    owner, inbox, channel = await _seed_channel(db_session, "-retry")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="IMAGE",
        source={"image_url": "https://x.example.com/x.jpg"},
    )
    await svc.transition_post_state(
        db_session,
        post=post,
        new_state="failed",
        error_code="80002",
        error_message="rate limited",
    )
    await db_session.refresh(post)
    assert post.error_code == "80002"
    # Operator retries.
    await svc.transition_post_state(
        db_session, post=post, new_state="pending"
    )
    await db_session.refresh(post)
    assert post.state == "pending"


# ---------------------------------------------------------------------------
# Containers + cascade
# ---------------------------------------------------------------------------
async def test_containers_cascade_on_post_delete(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-cas")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="CAROUSEL",
        source={
            "children": [
                {"image_url": "https://x.example.com/1.jpg"},
                {"image_url": "https://x.example.com/2.jpg"},
            ]
        },
    )
    await svc.add_container(
        db_session, post=post, ig_container_id="c1", position=1
    )
    await svc.add_container(
        db_session, post=post, ig_container_id="c2", position=2
    )
    # ORM-side delete fires the FK ondelete=CASCADE.
    await db_session.delete(post)
    await db_session.flush()
    remaining = list(
        (
            await db_session.exec(
                select(InstagramPostContainer).where(
                    InstagramPostContainer.post_id == post.id
                )
            )
        ).all()
    )
    assert remaining == []


async def test_containers_unique_per_position(db_session):
    """Two containers can't share (post_id, position) — the unique
    constraint protects against ARQ task replaying twice."""
    from sqlalchemy.exc import IntegrityError

    owner, inbox, channel = await _seed_channel(db_session, "-uniq")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="IMAGE",
        source={"image_url": "https://x.example.com/x.jpg"},
    )
    await svc.add_container(
        db_session, post=post, ig_container_id="c1", position=0
    )
    with pytest.raises(IntegrityError):
        await svc.add_container(
            db_session, post=post, ig_container_id="c2", position=0
        )


async def test_list_containers_orders_by_position(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-list")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="CAROUSEL",
        source={
            "children": [
                {"image_url": "https://x.example.com/1.jpg"},
                {"image_url": "https://x.example.com/2.jpg"},
            ]
        },
    )
    await svc.add_container(
        db_session, post=post, ig_container_id="parent", position=0
    )
    await svc.add_container(
        db_session, post=post, ig_container_id="child2", position=2
    )
    await svc.add_container(
        db_session, post=post, ig_container_id="child1", position=1
    )
    containers = await svc.list_containers(db_session, post_id=post.id)
    assert [c.position for c in containers] == [0, 1, 2]


# ---------------------------------------------------------------------------
# list_posts + get_post
# ---------------------------------------------------------------------------
async def test_list_posts_filters_by_state(db_session):
    owner, inbox, channel = await _seed_channel(db_session, "-ls")
    for _ in range(3):
        await svc.create_post(
            db_session,
            account_id=owner.account.id,
            inbox_id=inbox.id,
            channel_instagram_id=channel.id,
            media_type="IMAGE",
            source={"image_url": "https://x.example.com/x.jpg"},
        )
    # Flip one to publishing.
    rows = await svc.list_posts(
        db_session, account_id=owner.account.id
    )
    await svc.transition_post_state(
        db_session, post=rows[0], new_state="publishing"
    )

    pending = await svc.list_posts(
        db_session, account_id=owner.account.id, state="pending"
    )
    publishing = await svc.list_posts(
        db_session, account_id=owner.account.id, state="publishing"
    )
    assert len(pending) == 2
    assert len(publishing) == 1


async def test_get_post_account_scope(db_session):
    """A post on Account B isn't visible from Account A's scope."""
    owner_a, inbox_a, channel_a = await _seed_channel(db_session, "-a")
    owner_b, inbox_b, channel_b = await _seed_channel(db_session, "-b")
    post_b = await svc.create_post(
        db_session,
        account_id=owner_b.account.id,
        inbox_id=inbox_b.id,
        channel_instagram_id=channel_b.id,
        media_type="IMAGE",
        source={"image_url": "https://x.example.com/x.jpg"},
    )
    # Right account — found.
    found = await svc.get_post(
        db_session, account_id=owner_b.account.id, post_id=post_b.id
    )
    assert found is not None
    # Wrong account — None.
    spied = await svc.get_post(
        db_session, account_id=owner_a.account.id, post_id=post_b.id
    )
    assert spied is None


# ---------------------------------------------------------------------------
# Comments — upsert idempotency
# ---------------------------------------------------------------------------
async def test_upsert_comment_inserts_then_updates(db_session):
    owner, _inbox, channel = await _seed_channel(db_session, "-cmt")
    first = await svc.upsert_comment(
        db_session,
        account_id=owner.account.id,
        channel_instagram_id=channel.id,
        ig_comment_id="ig_comment_123",
        ig_media_id="ig_media_xyz",
        from_username="dianashopper",
        from_id="ig_user_999",
        text="Loved this!",
    )
    assert first.id is not None
    assert first.hidden is False

    # Second upsert (e.g. webhook re-delivery) — text update + hide.
    second = await svc.upsert_comment(
        db_session,
        account_id=owner.account.id,
        channel_instagram_id=channel.id,
        ig_comment_id="ig_comment_123",
        ig_media_id="ig_media_xyz",
        text="Loved this! (edited)",
        hidden=True,
    )
    assert second.id == first.id  # same row
    assert second.text == "Loved this! (edited)"
    assert second.hidden is True

    # Confirm only one row in the DB.
    rows = list(
        (
            await db_session.exec(
                select(InstagramComment).where(
                    InstagramComment.ig_comment_id == "ig_comment_123"
                )
            )
        ).all()
    )
    assert len(rows) == 1


async def test_list_comments_hides_hidden_by_default(db_session):
    owner, _inbox, channel = await _seed_channel(db_session, "-vis")
    await svc.upsert_comment(
        db_session,
        account_id=owner.account.id,
        channel_instagram_id=channel.id,
        ig_comment_id="visible-1",
        ig_media_id="media-1",
        text="visible",
    )
    await svc.upsert_comment(
        db_session,
        account_id=owner.account.id,
        channel_instagram_id=channel.id,
        ig_comment_id="hidden-1",
        ig_media_id="media-1",
        text="hidden",
        hidden=True,
    )
    visible_only = await svc.list_comments_for_media(
        db_session,
        account_id=owner.account.id,
        ig_media_id="media-1",
    )
    assert len(visible_only) == 1
    assert visible_only[0].ig_comment_id == "visible-1"

    all_of_them = await svc.list_comments_for_media(
        db_session,
        account_id=owner.account.id,
        ig_media_id="media-1",
        include_hidden=True,
    )
    assert len(all_of_them) == 2


# ---------------------------------------------------------------------------
# Stub contract — Meta-side callers must still raise NotImplementedError
# ---------------------------------------------------------------------------
async def test_meta_side_stubs_raise_until_wired():
    """The remaining Meta-side comment stubs raise until I.7 wires
    them. ``publish_post`` was promoted in I.2 and
    ``delete_media_on_meta`` in I.6, so they're no longer in this
    list."""
    with pytest.raises(NotImplementedError, match="Milestone I.7"):
        await svc.post_comment_on_meta(
            None,  # type: ignore[arg-type]
            ig_media_id="x",
            message="y",
        )
