"""Integration tests for the Instagram publish orchestration (I.2).

Exercises ``publishing_service.publish_post`` end-to-end with respx
mocking Meta's Graph API. The state machine
(pending → publishing → published / failed) is driven by the mocked
container-create / poll / publish responses.

No real Meta calls; no ARQ worker — ``publish_post`` takes the
session directly and a ``sleep_fn`` that returns instantly so the
poller loop doesn't actually wait.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.inboxes.models import InstagramChannel
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram import publisher as pub
from app.domains.instagram import publishing_service as svc
from app.domains.teams import models as _teams  # noqa: F401  (mapper)

pytestmark = pytest.mark.integration

GRAPH = "https://graph.facebook.com/v23.0"


async def _instant_sleep(_seconds: float) -> None:
    """Drop-in for asyncio.sleep so the poller loop runs instantly."""
    return None


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@igpub.example.com",
            account_name=f"IGPub{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"IG{suffix}",
            channel_type="instagram",
            channel_params={
                "instagram_id": f"17841400000000{abs(hash(suffix)) % 1000}",
                "access_token": "PAGE-TOKEN-test",
                "expires_at": (
                    datetime.now(UTC) + timedelta(days=60)
                ).isoformat(),
            },
        ),
    ).perform()
    assert isinstance(result.channel, InstagramChannel)
    return owner, result.inbox, result.channel


async def _make_image_post(db_session, owner, inbox, channel):
    return await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="IMAGE",
        source={"image_url": "https://cdn.example.com/p.jpg"},
        caption="hello world",
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
@respx.mock
async def test_publish_image_happy_path(db_session):
    owner, inbox, channel = await _seed(db_session, "-ok")
    post = await _make_image_post(db_session, owner, inbox, channel)
    igid = channel.instagram_id

    create_route = respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "CONTAINER_1"})
    )
    poll_route = respx.get(f"{GRAPH}/CONTAINER_1").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    publish_route = respx.post(f"{GRAPH}/{igid}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "IG_MEDIA_99"})
    )
    permalink_route = respx.get(f"{GRAPH}/IG_MEDIA_99").mock(
        return_value=httpx.Response(
            200,
            json={"permalink": "https://www.instagram.com/p/abc/"},
        )
    )

    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )

    assert create_route.called
    assert poll_route.called
    assert publish_route.called
    assert permalink_route.called
    assert result.state == "published"
    assert result.ig_media_id == "IG_MEDIA_99"
    assert result.ig_permalink == "https://www.instagram.com/p/abc/"
    assert result.published_at is not None

    # Verify the container body carried image_url + caption + token.
    body = create_route.calls.last.request.content.decode()
    assert "image_url" in body
    assert "caption" in body
    assert "access_token" in body


@respx.mock
async def test_publish_records_container_status(db_session):
    owner, inbox, channel = await _seed(db_session, "-cont")
    post = await _make_image_post(db_session, owner, inbox, channel)
    igid = channel.instagram_id
    respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "C2"})
    )
    respx.get(f"{GRAPH}/C2").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.post(f"{GRAPH}/{igid}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "M2"})
    )
    respx.get(f"{GRAPH}/M2").mock(
        return_value=httpx.Response(200, json={"permalink": "x"})
    )
    await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    containers = await svc.list_containers(db_session, post_id=post.id)
    assert len(containers) == 1
    assert containers[0].ig_container_id == "C2"
    assert containers[0].status_code == "FINISHED"


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------
@respx.mock
async def test_publish_fails_on_container_api_error(db_session):
    owner, inbox, channel = await _seed(db_session, "-cerr")
    post = await _make_image_post(db_session, owner, inbox, channel)
    igid = channel.instagram_id
    respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(
            400,
            json={
                "error": {
                    "message": "Invalid image URL",
                    "code": 9004,
                    "error_subcode": 2207052,
                }
            },
        )
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "failed"
    assert result.error_code == "9004"
    assert "Invalid image URL" in result.error_message
    assert "subcode 2207052" in result.error_message


@respx.mock
async def test_publish_fails_when_container_errors(db_session):
    owner, inbox, channel = await _seed(db_session, "-perr")
    post = await _make_image_post(db_session, owner, inbox, channel)
    igid = channel.instagram_id
    respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "C3"})
    )
    respx.get(f"{GRAPH}/C3").mock(
        return_value=httpx.Response(200, json={"status_code": "ERROR"})
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "failed"
    assert result.error_code == "ERROR"


@respx.mock
async def test_publish_fails_on_poll_timeout(db_session):
    """Container never leaves IN_PROGRESS → poller exhausts attempts."""
    owner, inbox, channel = await _seed(db_session, "-timeout")
    post = await _make_image_post(db_session, owner, inbox, channel)
    igid = channel.instagram_id
    respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "C4"})
    )
    respx.get(f"{GRAPH}/C4").mock(
        return_value=httpx.Response(
            200, json={"status_code": "IN_PROGRESS"}
        )
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "failed"
    assert result.error_code == "timeout"


@respx.mock
async def test_publish_fails_on_media_publish_error(db_session):
    owner, inbox, channel = await _seed(db_session, "-mperr")
    post = await _make_image_post(db_session, owner, inbox, channel)
    igid = channel.instagram_id
    respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "C5"})
    )
    respx.get(f"{GRAPH}/C5").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.post(f"{GRAPH}/{igid}/media_publish").mock(
        return_value=httpx.Response(
            400,
            json={
                "error": {
                    "message": "Application request limit reached",
                    "code": 80002,
                }
            },
        )
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "failed"
    assert result.error_code == "80002"


# ---------------------------------------------------------------------------
# Video + Reels (I.3)
# ---------------------------------------------------------------------------
@respx.mock
async def test_publish_video_happy_path(db_session):
    owner, inbox, channel = await _seed(db_session, "-vidok")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="VIDEO",
        source={"video_url": "https://cdn.example.com/v.mp4"},
        caption="a clip",
    )
    igid = channel.instagram_id
    create_route = respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "VC1"})
    )
    respx.get(f"{GRAPH}/VC1").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.post(f"{GRAPH}/{igid}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "VM1"})
    )
    respx.get(f"{GRAPH}/VM1").mock(
        return_value=httpx.Response(
            200, json={"permalink": "https://www.instagram.com/p/vid/"}
        )
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "published"
    assert result.ig_media_id == "VM1"
    # A caller-supplied VIDEO is folded to REELS on the way out: Meta
    # deprecated single feed videos and now 400s with subcode 2207067
    # ("El valor VIDEO para media_type es obsoleto. Usa REELS"). Accepting
    # VIDEO at the edge keeps older API callers working, so the container
    # body must say REELS and never VIDEO.
    body = create_route.calls.last.request.content.decode()
    assert "media_type=REELS" in body
    assert "VIDEO" not in body
    assert "video_url" in body


@respx.mock
async def test_publish_reels_carries_reel_params(db_session):
    owner, inbox, channel = await _seed(db_session, "-reel")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="REELS",
        source={
            "video_url": "https://cdn.example.com/r.mp4",
            "cover_url": "https://cdn.example.com/cover.jpg",
            "share_to_feed": True,
        },
        caption="a reel",
    )
    igid = channel.instagram_id
    create_route = respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "RC1"})
    )
    respx.get(f"{GRAPH}/RC1").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.post(f"{GRAPH}/{igid}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "RM1"})
    )
    respx.get(f"{GRAPH}/RM1").mock(
        return_value=httpx.Response(200, json={"permalink": "x"})
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "published"
    body = create_route.calls.last.request.content.decode()
    assert "REELS" in body
    assert "cover_url" in body
    assert "share_to_feed" in body


@respx.mock
async def test_publish_video_polls_until_finished(db_session):
    """Videos transcode slowly — the container sits IN_PROGRESS for a
    poll or two before flipping to FINISHED. Exercises the real loop."""
    owner, inbox, channel = await _seed(db_session, "-vpoll")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="VIDEO",
        source={"video_url": "https://cdn.example.com/v.mp4"},
    )
    igid = channel.instagram_id
    respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "VP1"})
    )
    poll_route = respx.get(f"{GRAPH}/VP1").mock(
        side_effect=[
            httpx.Response(200, json={"status_code": "IN_PROGRESS"}),
            httpx.Response(200, json={"status_code": "IN_PROGRESS"}),
            httpx.Response(200, json={"status_code": "FINISHED"}),
        ]
    )
    respx.post(f"{GRAPH}/{igid}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "VPM1"})
    )
    respx.get(f"{GRAPH}/VPM1").mock(
        return_value=httpx.Response(200, json={"permalink": "x"})
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "published"
    assert poll_route.call_count == 3
    containers = await svc.list_containers(db_session, post_id=post.id)
    assert containers[0].status_code == "FINISHED"


@respx.mock
async def test_publish_video_fails_on_expired_container(db_session):
    owner, inbox, channel = await _seed(db_session, "-vexp")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="VIDEO",
        source={"video_url": "https://cdn.example.com/v.mp4"},
    )
    igid = channel.instagram_id
    respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "VE1"})
    )
    respx.get(f"{GRAPH}/VE1").mock(
        return_value=httpx.Response(200, json={"status_code": "EXPIRED"})
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "failed"
    assert result.error_code == "EXPIRED"


async def test_publish_video_without_url_fails(db_session):
    """create_post enforces video_url, but a row mutated to drop it
    fails cleanly at publish time rather than crashing the worker."""
    owner, inbox, channel = await _seed(db_session, "-vnourl")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="VIDEO",
        source={"video_url": "https://cdn.example.com/v.mp4"},
    )
    # Simulate a malformed row reaching the worker.
    post.source = {}
    db_session.add(post)
    await db_session.flush()
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "failed"
    assert result.error_code == "missing_video_url"


# ---------------------------------------------------------------------------
# Carousel (I.4)
# ---------------------------------------------------------------------------
async def _make_carousel_post(db_session, owner, inbox, channel, children):
    return await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="CAROUSEL",
        source={"children": children},
        caption="a carousel",
    )


@respx.mock
async def test_publish_carousel_happy_path(db_session):
    owner, inbox, channel = await _seed(db_session, "-car")
    post = await _make_carousel_post(
        db_session,
        owner,
        inbox,
        channel,
        [
            {"image_url": "https://cdn.example.com/1.jpg"},
            {"image_url": "https://cdn.example.com/2.jpg"},
        ],
    )
    igid = channel.instagram_id
    # 3 POSTs to /media: child1, child2, then the parent.
    create_route = respx.post(f"{GRAPH}/{igid}/media").mock(
        side_effect=[
            httpx.Response(200, json={"id": "CC1"}),
            httpx.Response(200, json={"id": "CC2"}),
            httpx.Response(200, json={"id": "CPAR"}),
        ]
    )
    respx.get(f"{GRAPH}/CC1").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.get(f"{GRAPH}/CC2").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.get(f"{GRAPH}/CPAR").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.post(f"{GRAPH}/{igid}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "CMID"})
    )
    respx.get(f"{GRAPH}/CMID").mock(
        return_value=httpx.Response(200, json={"permalink": "x"})
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "published"
    assert result.ig_media_id == "CMID"
    assert create_route.call_count == 3
    # Parent body (3rd create call) carries CAROUSEL + the child ids.
    parent_body = create_route.calls[2].request.content.decode()
    assert "CAROUSEL" in parent_body
    assert "children" in parent_body
    assert "CC1" in parent_body
    assert "CC2" in parent_body
    # Container rows: parent at position 0, children at 1 + 2.
    containers = await svc.list_containers(db_session, post_id=post.id)
    assert [c.position for c in containers] == [0, 1, 2]
    assert {c.ig_container_id for c in containers} == {"CPAR", "CC1", "CC2"}


@respx.mock
async def test_publish_carousel_mixed_image_video(db_session):
    owner, inbox, channel = await _seed(db_session, "-carmix")
    post = await _make_carousel_post(
        db_session,
        owner,
        inbox,
        channel,
        [
            {"image_url": "https://cdn.example.com/1.jpg"},
            {"video_url": "https://cdn.example.com/2.mp4"},
        ],
    )
    igid = channel.instagram_id
    create_route = respx.post(f"{GRAPH}/{igid}/media").mock(
        side_effect=[
            httpx.Response(200, json={"id": "MC1"}),
            httpx.Response(200, json={"id": "MC2"}),
            httpx.Response(200, json={"id": "MPAR"}),
        ]
    )
    for cid in ("MC1", "MC2", "MPAR"):
        respx.get(f"{GRAPH}/{cid}").mock(
            return_value=httpx.Response(
                200, json={"status_code": "FINISHED"}
            )
        )
    respx.post(f"{GRAPH}/{igid}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "MMID"})
    )
    respx.get(f"{GRAPH}/MMID").mock(
        return_value=httpx.Response(200, json={"permalink": "x"})
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "published"
    # First child = image, second child = video w/ is_carousel_item.
    child1 = create_route.calls[0].request.content.decode()
    child2 = create_route.calls[1].request.content.decode()
    assert "image_url" in child1
    assert "is_carousel_item" in child1
    assert "video_url" in child2
    assert "VIDEO" in child2
    assert "is_carousel_item" in child2


@respx.mock
async def test_publish_carousel_fails_when_child_errors(db_session):
    """A child stuck in ERROR fails the whole post; the parent is
    never created."""
    owner, inbox, channel = await _seed(db_session, "-carcerr")
    post = await _make_carousel_post(
        db_session,
        owner,
        inbox,
        channel,
        [
            {"image_url": "https://cdn.example.com/1.jpg"},
            {"image_url": "https://cdn.example.com/2.jpg"},
        ],
    )
    igid = channel.instagram_id
    create_route = respx.post(f"{GRAPH}/{igid}/media").mock(
        side_effect=[
            httpx.Response(200, json={"id": "EC1"}),
            httpx.Response(200, json={"id": "EC2"}),
        ]
    )
    respx.get(f"{GRAPH}/EC1").mock(
        return_value=httpx.Response(200, json={"status_code": "ERROR"})
    )
    respx.get(f"{GRAPH}/EC2").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "failed"
    assert result.error_code == "ERROR"
    # Both children created, but no parent (only 2 create calls).
    assert create_route.call_count == 2


@respx.mock
async def test_publish_carousel_fails_on_child_create_error(db_session):
    owner, inbox, channel = await _seed(db_session, "-carcreate")
    post = await _make_carousel_post(
        db_session,
        owner,
        inbox,
        channel,
        [
            {"image_url": "https://cdn.example.com/1.jpg"},
            {"image_url": "https://cdn.example.com/2.jpg"},
        ],
    )
    igid = channel.instagram_id
    create_route = respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(
            400,
            json={"error": {"message": "Invalid image URL", "code": 9004}},
        )
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "failed"
    assert result.error_code == "9004"
    # Bailed on the first child — no second child, no parent.
    assert create_route.call_count == 1


# ---------------------------------------------------------------------------
# Stories (I.5)
# ---------------------------------------------------------------------------
@respx.mock
async def test_publish_image_story_happy_path(db_session):
    owner, inbox, channel = await _seed(db_session, "-istory")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="STORIES",
        source={"image_url": "https://cdn.example.com/s.jpg"},
    )
    igid = channel.instagram_id
    create_route = respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "SC1"})
    )
    respx.get(f"{GRAPH}/SC1").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.post(f"{GRAPH}/{igid}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "SM1"})
    )
    respx.get(f"{GRAPH}/SM1").mock(
        return_value=httpx.Response(200, json={"permalink": "x"})
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "published"
    assert result.ig_media_id == "SM1"
    body = create_route.calls.last.request.content.decode()
    assert "STORIES" in body
    assert "image_url" in body


@respx.mock
async def test_publish_video_story_happy_path(db_session):
    owner, inbox, channel = await _seed(db_session, "-vstory")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="STORIES",
        source={"video_url": "https://cdn.example.com/s.mp4"},
    )
    igid = channel.instagram_id
    create_route = respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "VS1"})
    )
    respx.get(f"{GRAPH}/VS1").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.post(f"{GRAPH}/{igid}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "VSM1"})
    )
    respx.get(f"{GRAPH}/VSM1").mock(
        return_value=httpx.Response(200, json={"permalink": "x"})
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "published"
    body = create_route.calls.last.request.content.decode()
    assert "STORIES" in body
    assert "video_url" in body


async def test_publish_story_without_source_fails(db_session):
    owner, inbox, channel = await _seed(db_session, "-snourl")
    post = await svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox.id,
        channel_instagram_id=channel.id,
        media_type="STORIES",
        source={"image_url": "https://cdn.example.com/s.jpg"},
    )
    # Simulate a malformed row reaching the worker.
    post.source = {}
    db_session.add(post)
    await db_session.flush()
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "failed"
    assert result.error_code == "missing_story_source"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------
@respx.mock
async def test_publish_is_idempotent_on_non_pending(db_session):
    """A double-enqueue (REST + scheduler racing) finds the post
    already published and no-ops without a second Meta call."""
    owner, inbox, channel = await _seed(db_session, "-idem")
    post = await _make_image_post(db_session, owner, inbox, channel)
    igid = channel.instagram_id
    create_route = respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "C6"})
    )
    respx.get(f"{GRAPH}/C6").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.post(f"{GRAPH}/{igid}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "M6"})
    )
    respx.get(f"{GRAPH}/M6").mock(
        return_value=httpx.Response(200, json={"permalink": "x"})
    )
    # First run publishes.
    await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    call_count_after_first = create_route.call_count
    # Second run no-ops.
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "published"
    assert create_route.call_count == call_count_after_first


# ---------------------------------------------------------------------------
# Delete media (I.6)
# ---------------------------------------------------------------------------
async def _make_published_post(db_session, owner, inbox, channel, igmid):
    """A post already in ``published`` state with an ig_media_id, as
    the worker would leave it after a successful publish."""
    post = await _make_image_post(db_session, owner, inbox, channel)
    post.state = "published"
    post.ig_media_id = igmid
    db_session.add(post)
    await db_session.flush()
    return post


@respx.mock
async def test_delete_published_post_happy_path(db_session):
    owner, inbox, channel = await _seed(db_session, "-del")
    post = await _make_published_post(
        db_session, owner, inbox, channel, "DELME_1"
    )
    del_route = respx.delete(f"{GRAPH}/DELME_1").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    result = await svc.delete_media_on_meta(
        db_session, account_id=owner.account.id, post_id=post.id
    )
    assert del_route.called
    assert result.state == "deleted"


async def test_delete_non_published_rejected(db_session):
    owner, inbox, channel = await _seed(db_session, "-delpend")
    post = await _make_image_post(db_session, owner, inbox, channel)
    # Still pending — nothing on Meta to delete.
    with pytest.raises(ChatwootHTTPException) as exc:
        await svc.delete_media_on_meta(
            db_session, account_id=owner.account.id, post_id=post.id
        )
    assert exc.value.status_code == 422


async def test_delete_unknown_post_404(db_session):
    owner, _, _ = await _seed(db_session, "-delunk")
    with pytest.raises(ChatwootHTTPException) as exc:
        await svc.delete_media_on_meta(
            db_session, account_id=owner.account.id, post_id=99999999
        )
    assert exc.value.status_code == 404


@respx.mock
async def test_delete_meta_error_surfaces_and_stamps(db_session):
    """Meta rejects deleting e.g. a live video — the error surfaces as
    422 and the row keeps its ``published`` state with the error
    stamped for audit."""
    owner, inbox, channel = await _seed(db_session, "-delerr")
    post = await _make_published_post(
        db_session, owner, inbox, channel, "DELERR_1"
    )
    respx.delete(f"{GRAPH}/DELERR_1").mock(
        return_value=httpx.Response(
            400,
            json={
                "error": {
                    "message": "Cannot delete live video",
                    "code": 10,
                }
            },
        )
    )
    with pytest.raises(ChatwootHTTPException) as exc:
        await svc.delete_media_on_meta(
            db_session, account_id=owner.account.id, post_id=post.id
        )
    assert exc.value.status_code == 422
    await db_session.refresh(post)
    assert post.state == "published"  # unchanged
    assert post.error_code == "10"


@respx.mock
async def test_delete_is_idempotent_on_already_deleted(db_session):
    owner, inbox, channel = await _seed(db_session, "-delidem")
    post = await _make_published_post(
        db_session, owner, inbox, channel, "DELIDEM_1"
    )
    del_route = respx.delete(f"{GRAPH}/DELIDEM_1").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    await svc.delete_media_on_meta(
        db_session, account_id=owner.account.id, post_id=post.id
    )
    assert del_route.call_count == 1
    # Second delete no-ops — already deleted, no second Meta call.
    result = await svc.delete_media_on_meta(
        db_session, account_id=owner.account.id, post_id=post.id
    )
    assert result.state == "deleted"
    assert del_route.call_count == 1


# ---------------------------------------------------------------------------
# Rate limit + quota (I.9)
# ---------------------------------------------------------------------------
@pytest.fixture
def quota_check_on():
    settings = get_settings()
    original = settings.meta_check_publishing_quota
    settings.meta_check_publishing_quota = True
    try:
        yield
    finally:
        settings.meta_check_publishing_quota = original


@respx.mock
async def test_fetch_publishing_limit_parses(db_session):
    _owner, _inbox, channel = await _seed(db_session, "-quota")
    igid = channel.instagram_id
    respx.get(f"{GRAPH}/{igid}/content_publishing_limit").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"quota_usage": 7, "config": {"quota_total": 100}}
                ]
            },
        )
    )
    res = await pub.fetch_publishing_limit(channel)
    assert res.ok
    assert res.quota_usage == 7
    assert res.quota_total == 100
    assert res.exceeded is False


@respx.mock
async def test_publish_blocked_when_quota_exceeded(
    db_session, quota_check_on
):
    owner, inbox, channel = await _seed(db_session, "-qexc")
    post = await _make_image_post(db_session, owner, inbox, channel)
    igid = channel.instagram_id
    respx.get(f"{GRAPH}/{igid}/content_publishing_limit").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"quota_usage": 100, "config": {"quota_total": 100}}
                ]
            },
        )
    )
    create_route = respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "SHOULD_NOT_RUN"})
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "failed"
    assert result.error_code == "quota_exceeded"
    # Bailed before any container create.
    assert create_route.call_count == 0


@respx.mock
async def test_publish_proceeds_when_quota_ok(db_session, quota_check_on):
    owner, inbox, channel = await _seed(db_session, "-qok")
    post = await _make_image_post(db_session, owner, inbox, channel)
    igid = channel.instagram_id
    respx.get(f"{GRAPH}/{igid}/content_publishing_limit").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"quota_usage": 5, "config": {"quota_total": 100}}]},
        )
    )
    respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "QC1"})
    )
    respx.get(f"{GRAPH}/QC1").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.post(f"{GRAPH}/{igid}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "QM1"})
    )
    respx.get(f"{GRAPH}/QM1").mock(
        return_value=httpx.Response(200, json={"permalink": "x"})
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "published"


@respx.mock
async def test_publish_quota_check_best_effort_on_error(
    db_session, quota_check_on
):
    """A failed quota call must not block publishing."""
    owner, inbox, channel = await _seed(db_session, "-qbe")
    post = await _make_image_post(db_session, owner, inbox, channel)
    igid = channel.instagram_id
    respx.get(f"{GRAPH}/{igid}/content_publishing_limit").mock(
        return_value=httpx.Response(500, json={"error": {"message": "boom"}})
    )
    respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(200, json={"id": "BE1"})
    )
    respx.get(f"{GRAPH}/BE1").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.post(f"{GRAPH}/{igid}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "BEM1"})
    )
    respx.get(f"{GRAPH}/BEM1").mock(
        return_value=httpx.Response(200, json={"permalink": "x"})
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "published"


@respx.mock
async def test_throttle_error_marks_message(db_session):
    """A throttle code on container create flags the message as
    rate-limited (so the worker's retry path recognises it)."""
    owner, inbox, channel = await _seed(db_session, "-thr")
    post = await _make_image_post(db_session, owner, inbox, channel)
    igid = channel.instagram_id
    respx.post(f"{GRAPH}/{igid}/media").mock(
        return_value=httpx.Response(
            400,
            json={
                "error": {
                    "message": "Application request limit reached",
                    "code": 80002,
                }
            },
            headers={"X-App-Usage": '{"call_count":100}'},
        )
    )
    result = await svc.publish_post(
        db_session, post_id=post.id, sleep_fn=_instant_sleep
    )
    assert result.state == "failed"
    assert result.error_code == "80002"
    assert pub.is_throttle_error(result.error_code)
    assert "[rate-limited]" in result.error_message
    # Usage header was captured for diagnostics.
    assert "X-App-Usage" in result.error_message


async def test_reset_for_retry_flips_failed_to_pending(db_session):
    owner, inbox, channel = await _seed(db_session, "-rst")
    post = await _make_image_post(db_session, owner, inbox, channel)
    post.state = "failed"
    post.error_code = "80002"
    db_session.add(post)
    await db_session.flush()
    out = await svc.reset_for_retry(db_session, post=post)
    assert out.state == "pending"
    # No-op on a non-failed post.
    out2 = await svc.reset_for_retry(db_session, post=out)
    assert out2.state == "pending"
