"""Publishing analytics: post and channel metrics from Instagram and
Facebook (Graph mocked with respx), the hourly post sync, the daily channel
snapshot, and the summary."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram.models import InstagramPost
from app.domains.publishing import analytics
from app.domains.publishing import service as svc
from app.domains.publishing.adapters import MetricsResult
from app.domains.publishing.adapters.facebook_page import FacebookPageAdapter
from app.domains.publishing.adapters.instagram import InstagramAdapter
from app.domains.publishing.models import ChannelMetricSnapshot, PublicationTarget
from app.domains.teams import models as _teams  # noqa: F401
from app.main import app

pytestmark = pytest.mark.integration

PAGE_ID = "PAGEAN"


def _graph() -> str:
    return f"https://graph.facebook.com/{get_settings().meta_graph_api_version}"


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
            email=f"admin{suffix}@stats.example.com",
            account_name=f"STATS{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    page = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Pagina",
                channel_type="facebook",
                channel_params={"page_id": PAGE_ID, "page_access_token": "t"},
            ),
        ).perform()
    ).inbox
    insta = (
        await InboxBuilder(
            db_session,
            InboxBuilderParams(
                account=owner.account,
                name="Insta",
                channel_type="instagram",
                channel_params={"instagram_id": f"1784{suffix[-3:]}9", "access_token": "ig"},
            ),
        ).perform()
    ).inbox
    headers, tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, page, insta, headers.as_response_headers()


async def _published(
    db_session, account, inbox, *, external_id: str, when=None, media_type="image", settings=None
):
    """A publication already out on ``inbox`` (as the publish loop leaves it)."""
    publication = await svc.create_publication(
        db_session,
        account_id=account.id,
        payload={
            "content": f"post {external_id}",
            "media": [{"type": media_type, "url": f"https://cdn.example.com/a.{media_type}"}],
            "scheduled_for": datetime.now(UTC) + timedelta(hours=1),
            "targets": [{"inbox_id": inbox.id, "settings": settings or {}}],
        },
    )
    publication.state = "published"
    (target,) = (
        await svc.targets_by_publication(db_session, publication_ids=[publication.id])
    )[publication.id]
    target.state = "published"
    target.external_id = external_id
    target.published_at = when or datetime.now(UTC) - timedelta(days=1)
    db_session.add_all([publication, target])
    await db_session.flush()
    return publication, target


@respx.mock
async def test_facebook_post_and_page_metrics(db_session):
    owner, page, _insta, _ = await _seed(db_session, "-fb1")
    _pub, target = await _published(db_session, owner.account, page, external_id=f"{PAGE_ID}_1")
    respx.get(f"{_graph()}/{PAGE_ID}_1").mock(
        return_value=httpx.Response(
            200,
            json={
                "shares": {"count": 3},
                "comments": {"summary": {"total_count": 5}},
                "reactions": {"summary": {"total_count": 40}},
            },
        )
    )
    respx.get(f"{_graph()}/{PAGE_ID}_1/insights").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"name": "post_media_view", "values": [{"value": 900}]},
                    {"name": "post_total_media_view_unique", "values": [{"value": 600}]},
                ]
            },
        )
    )
    respx.get(f"{_graph()}/{PAGE_ID}").mock(
        return_value=httpx.Response(200, json={"followers_count": 1234})
    )

    assert await analytics.refresh_target_metrics(db_session, target)
    channel = await FacebookPageAdapter().fetch_channel_metrics(
        db_session, page, days=[date(2026, 10, 26)]
    )

    assert target.metrics == {
        "likes": 40,
        "comments": 5,
        "shares": 3,
        "interactions": 48,
        "views": 900,
        "reach": 600,
    }
    assert target.metrics_error is None
    assert target.metrics_updated_at is not None
    assert channel == MetricsResult(ok=True, metrics={"followers": 1234})


@respx.mock
async def test_missing_insights_permission_keeps_engagement(db_session):
    owner, page, _insta, _ = await _seed(db_session, "-fb2")
    _pub, target = await _published(db_session, owner.account, page, external_id=f"{PAGE_ID}_2")
    respx.get(f"{_graph()}/{PAGE_ID}_2").mock(
        return_value=httpx.Response(
            200, json={"comments": {"summary": {"total_count": 1}}, "reactions": {"summary": {"total_count": 2}}}
        )
    )
    respx.get(f"{_graph()}/{PAGE_ID}_2/insights").mock(
        return_value=httpx.Response(400, json={"error": {"code": 10, "message": "no perm"}})
    )

    assert await analytics.refresh_target_metrics(db_session, target)
    assert target.metrics == {"likes": 2, "comments": 1, "shares": 0, "interactions": 3}


@respx.mock
async def test_a_failed_refresh_keeps_the_last_figures(db_session):
    owner, page, _insta, _ = await _seed(db_session, "-fb3")
    _pub, target = await _published(db_session, owner.account, page, external_id=f"{PAGE_ID}_3")
    target.metrics = {"likes": 7}
    respx.get(f"{_graph()}/{PAGE_ID}_3").mock(
        return_value=httpx.Response(400, json={"error": {"code": 200, "message": "x"}})
    )

    assert not await analytics.refresh_target_metrics(db_session, target)
    assert target.metrics == {"likes": 7}
    assert "leer estadísticas" in target.metrics_error
    assert target.metrics_updated_at is not None


@respx.mock
async def test_facebook_video_skips_post_insights(db_session):
    owner, page, _insta, _ = await _seed(db_session, "-fbv")
    _pub, target = await _published(
        db_session, owner.account, page, external_id="VID1", media_type="video"
    )

    def _video(request):
        if "shares" in request.url.params["fields"]:
            return httpx.Response(400, json={"error": {"code": 100, "message": "no shares"}})
        return httpx.Response(200, json={"reactions": {"summary": {"total_count": 9}}})

    respx.get(f"{_graph()}/VID1").mock(side_effect=_video)
    insights = respx.get(f"{_graph()}/VID1/insights").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    assert await analytics.refresh_target_metrics(db_session, target)
    assert target.metrics == {"likes": 9, "interactions": 9}
    assert not insights.called


@respx.mock
async def test_facebook_other_errors_are_not_retried_without_shares(db_session):
    owner, page, _insta, _ = await _seed(db_session, "-fbe")
    _pub, target = await _published(db_session, owner.account, page, external_id="E1")
    route = respx.get(f"{_graph()}/E1").mock(
        return_value=httpx.Response(400, json={"error": {"code": 803, "message": "boom"}})
    )

    assert not await analytics.refresh_target_metrics(db_session, target)
    assert route.call_count == 1
    assert target.metrics_error == "Facebook no devolvió estadísticas: boom"


async def test_empty_or_missing_reads_keep_figures_and_stamp(db_session, monkeypatch):
    owner, page, _insta, _ = await _seed(db_session, "-empty")
    _pub, target = await _published(db_session, owner.account, page, external_id="M1")
    target.metrics = {"likes": 4}
    replies = [MetricsResult(ok=True), None]

    async def _fake(self, session, target):
        return replies.pop(0)

    monkeypatch.setattr(FacebookPageAdapter, "fetch_post_metrics", _fake)

    for _ in range(2):
        target.metrics_updated_at = None
        await analytics.refresh_target_metrics(db_session, target)
        assert target.metrics == {"likes": 4}
        assert target.metrics_updated_at is not None


@respx.mock
async def test_instagram_media_and_account_metrics(db_session):
    owner, _page, insta, _ = await _seed(db_session, "-ig1")
    _pub, target = await _published(db_session, owner.account, insta, external_id="IGM1")
    respx.get(f"{_graph()}/IGM1/insights").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"name": "views", "values": [{"value": 300}]},
                    {"name": "reach", "values": [{"value": 200}]},
                    {"name": "likes", "values": [{"value": 30}]},
                    {"name": "saved", "values": [{"value": 4}]},
                    {"name": "total_interactions", "values": [{"value": 41}]},
                ]
            },
        )
    )
    adapter = analytics.adapter_for_inbox(insta)
    ig_user = respx.get(url__regex=rf"{_graph()}/1784\w+\?").mock(
        return_value=httpx.Response(200, json={"followers_count": 512})
    )
    account_insights = respx.get(url__regex=rf"{_graph()}/1784\w+/insights").mock(
        return_value=httpx.Response(
            200, json={"data": [{"name": "reach", "total_value": {"value": 77}}]}
        )
    )
    days = [date(2026, 10, 26), date(2026, 10, 25)]

    assert await analytics.refresh_target_metrics(db_session, target)
    result = await adapter.fetch_channel_metrics(db_session, insta, days=days)

    assert target.metrics == {
        "views": 300,
        "reach": 200,
        "likes": 30,
        "saves": 4,
        "interactions": 41,
    }
    assert ig_user.called
    assert result.metrics == {"followers": 512}
    assert result.daily == {day: {"reach": 77} for day in days}
    first = account_insights.calls[0].request.url.params
    assert first["since"] == str(int(datetime(2026, 10, 26, tzinfo=UTC).timestamp()))
    assert first["until"] == str(int(datetime(2026, 10, 27, tzinfo=UTC).timestamp()))


@respx.mock
async def test_expired_story_uses_the_webhook_figures(db_session):
    owner, _page, insta, _ = await _seed(db_session, "-story")
    _pub, target = await _published(
        db_session, owner.account, insta, external_id="IGS1",
        when=datetime.now(UTC) - timedelta(hours=30), settings={"post_type": "story"},
    )
    post = InstagramPost(
        account_id=owner.account.id,
        inbox_id=insta.id,
        channel_instagram_id=insta.channel_id,
        state="published",
        media_type="STORIES",
        ig_media_id="IGS1",
        insights={"impressions": 80, "reach": 60, "replies": 2, "exits": 5},
    )
    db_session.add(post)
    await db_session.flush()
    target.extra = {**(target.extra or {}), "instagram_post_id": post.id}
    graph = respx.get(f"{_graph()}/IGS1/insights")

    assert await analytics.refresh_target_metrics(db_session, target)
    assert target.metrics == {"views": 80, "reach": 60, "comments": 2}
    assert not graph.called


async def test_sync_refreshes_recent_stale_posts_only(db_session, monkeypatch):
    owner, page, _insta, _ = await _seed(db_session, "-sync")
    now = datetime.now(UTC)
    _p1, recent = await _published(db_session, owner.account, page, external_id="R1")
    _p2, fresh = await _published(db_session, owner.account, page, external_id="F1")
    fresh.metrics_updated_at = now - timedelta(minutes=10)
    _p3, old = await _published(
        db_session, owner.account, page, external_id="O1",
        when=now - timedelta(days=45),
    )
    # Read 10 h ago: due when it's a day old, not yet when it's a week old.
    _p4, new_read = await _published(db_session, owner.account, page, external_id="N1")
    new_read.metrics_updated_at = now - timedelta(hours=10)
    _p5, week_read = await _published(
        db_session, owner.account, page, external_id="W1", when=now - timedelta(days=7)
    )
    week_read.metrics_updated_at = now - timedelta(hours=10)
    db_session.add_all([fresh, new_read, week_read])
    await db_session.flush()
    seen: list[str] = []

    async def _fake(self, session, target):
        seen.append(target.external_id)
        return MetricsResult(ok=True, metrics={"likes": 1})

    monkeypatch.setattr(FacebookPageAdapter, "fetch_post_metrics", _fake)

    refreshed = await analytics.sync_post_metrics(db_session)

    assert "R1" in seen and "N1" in seen
    assert "F1" not in seen and "O1" not in seen and "W1" not in seen
    assert refreshed >= 1
    assert recent.metrics == {"likes": 1}
    assert old.metrics == {}


async def test_one_snapshot_per_channel_per_day(db_session, monkeypatch):
    owner, page, insta, _ = await _seed(db_session, "-snap")

    async def _fb(self, session, inbox, *, days):
        return MetricsResult(ok=True, metrics={"followers": 100})

    monkeypatch.setattr(FacebookPageAdapter, "fetch_channel_metrics", _fb)

    async def _ig(self, session, inbox, *, days):
        return MetricsResult(ok=False, error_message="sin permiso")

    monkeypatch.setattr(InstagramAdapter, "fetch_channel_metrics", _ig)
    today = date(2026, 10, 27)

    await analytics.snapshot_channels(db_session, today=today)
    await analytics.snapshot_channels(db_session, today=today)

    from sqlmodel import select

    rows = (
        await db_session.exec(
            select(ChannelMetricSnapshot).where(
                ChannelMetricSnapshot.account_id == owner.account.id
            )
        )
    ).all()
    assert [(r.inbox_id, r.metrics) for r in rows] == [(page.id, {"followers": 100})]
    assert insta.id not in [r.inbox_id for r in rows]


async def test_snapshot_merges_the_last_days_figures(db_session, monkeypatch):
    owner, _page, insta, _ = await _seed(db_session, "-merge")
    today = date(2026, 10, 27)
    yesterday = today - timedelta(days=1)
    # Yesterday's run stored that day's follower count.
    db_session.add(
        ChannelMetricSnapshot(
            account_id=owner.account.id, inbox_id=insta.id, network="instagram",
            date=yesterday, metrics={"followers": 500},
        )
    )
    await db_session.flush()
    asked: list[list[date]] = []

    async def _ig(self, session, inbox, *, days):
        asked.append(days)
        return MetricsResult(
            ok=True,
            metrics={"followers": 510},
            daily={yesterday: {"reach": 70}, today - timedelta(days=2): {"reach": 40}},
        )

    async def _fb(self, session, inbox, *, days):
        return None

    monkeypatch.setattr(InstagramAdapter, "fetch_channel_metrics", _ig)
    monkeypatch.setattr(FacebookPageAdapter, "fetch_channel_metrics", _fb)

    assert await analytics.snapshot_channels(db_session, today=today) == 1

    from sqlmodel import select

    rows = (
        await db_session.exec(
            select(ChannelMetricSnapshot)
            .where(ChannelMetricSnapshot.inbox_id == insta.id)
            .order_by(ChannelMetricSnapshot.date)
            .execution_options(populate_existing=True)
        )
    ).all()
    assert asked == [[yesterday, today - timedelta(days=2), today - timedelta(days=3)]]
    assert [(r.date, r.metrics) for r in rows] == [
        (today - timedelta(days=2), {"reach": 40}),
        (yesterday, {"followers": 500, "reach": 70}),
        (today, {"followers": 510}),
    ]


async def test_summary_endpoint(client, db_session):
    owner, page, insta, h = await _seed(db_session, "-sum")
    _a, fb_post = await _published(db_session, owner.account, page, external_id="S1")
    fb_post.metrics = {"likes": 10, "comments": 2, "interactions": 12, "reach": 100}
    _b, ig_post = await _published(db_session, owner.account, insta, external_id="S2")
    ig_post.metrics = {"likes": 50, "interactions": 70, "reach": 400, "saves": 5}
    _c, outside = await _published(
        db_session, owner.account, page, external_id="S3",
        when=datetime.now(UTC) - timedelta(days=60),
    )
    outside.metrics = {"likes": 999}
    db_session.add_all([fb_post, ig_post, outside])
    for day, followers in ((date.today() - timedelta(days=3), 90), (date.today(), 100)):
        db_session.add(
            ChannelMetricSnapshot(
                account_id=owner.account.id, inbox_id=page.id, network="facebook_page",
                date=day, metrics={"followers": followers},
            )
        )
    await db_session.flush()

    r = await client.get(
        f"/api/v1/accounts/{owner.account.id}/publications/analytics", headers=h
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["totals"]["posts"] == 2
    assert body["totals"]["likes"] == 60
    assert body["totals"]["reach"] == 500
    by_inbox = {c["channel"]["inbox_id"]: c for c in body["channels"]}
    assert by_inbox[page.id]["posts"] == 1
    assert by_inbox[page.id]["followers"] == 100
    assert by_inbox[page.id]["followers_change"] == 10
    assert [p["target_id"] for p in body["top_posts"]] == [ig_post.id, fb_post.id]

    r = await client.get(
        f"/api/v1/accounts/{owner.account.id}/publications/analytics",
        headers=h,
        params={"inbox_id": insta.id},
    )
    assert r.json()["totals"]["posts"] == 1

    r = await client.get(
        f"/api/v1/accounts/{owner.account.id}/publications/analytics",
        headers=h,
        params={"from": "2025-01-01T00:00:00Z", "to": "2026-10-01T00:00:00Z"},
    )
    assert r.status_code == 422


async def test_refresh_metrics_endpoint_and_presenter(client, db_session, monkeypatch):
    owner, page, _insta, h = await _seed(db_session, "-ref")
    publication, _target = await _published(db_session, owner.account, page, external_id="X1")
    calls: list[int] = []

    async def _fake(self, session, target):
        calls.append(target.id)
        return MetricsResult(ok=True, metrics={"likes": 3, "interactions": 3})

    monkeypatch.setattr(FacebookPageAdapter, "fetch_post_metrics", _fake)

    r = await client.post(
        f"/api/v1/accounts/{owner.account.id}/publications/{publication.id}/refresh_metrics",
        headers=h,
    )

    assert r.status_code == 200, r.text
    (target,) = r.json()["targets"]
    assert target["metrics"] == {"likes": 3, "interactions": 3}
    assert target["metrics_updated_at"] is not None
    assert target["metrics_error"] is None
    assert isinstance(_target, PublicationTarget)

    # A second click right away keeps the figures just read.
    r = await client.post(
        f"/api/v1/accounts/{owner.account.id}/publications/{publication.id}/refresh_metrics",
        headers=h,
    )
    assert r.status_code == 200
    assert calls == [_target.id]
