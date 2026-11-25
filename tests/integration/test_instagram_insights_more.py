"""The fuller Instagram figures: what each kind of post reports, the
account's day split by follows, surface and button, its audience, and how
the summary carries them.

Graph mocked with respx, one route answering by the ``metric`` and
``breakdown`` asked."""

# ruff: noqa: F401, F811  (pytest fixtures imported from the analytics tests)

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
import respx

from app.domains.publishing import analytics
from app.domains.publishing.adapters import adapter_for_inbox
from app.domains.publishing.models import ChannelMetricSnapshot
from tests.integration._publishing import channel_of
from tests.integration.test_publishing_analytics import (
    _graph,
    _published,
    _seed,
    client,
)

pytestmark = pytest.mark.integration


def _total(name: str, value: int) -> dict:
    return {"name": name, "total_value": {"value": value}}


def _split(name: str, dimension: str, values: dict[str, int], timeframe: bool = False) -> dict:
    keys = ["timeframe", dimension] if timeframe else [dimension]
    return {
        "name": name,
        "total_value": {
            "breakdowns": [
                {
                    "dimension_keys": keys,
                    "results": [
                        {
                            "dimension_values": (["THIS_MONTH", k] if timeframe else [k]),
                            "value": v,
                        }
                        for k, v in values.items()
                    ],
                }
            ]
        },
    }


def _account_answer(request: httpx.Request) -> httpx.Response:
    params = request.url.params
    metric, breakdown = params.get("metric"), params.get("breakdown")
    if metric == "follows_and_unfollows":
        data = [_split(metric, "follow_type", {"FOLLOWER": 12, "NON_FOLLOWER": 3})]
    elif metric == "views" and breakdown == "media_product_type":
        data = [_split(metric, "media_product_type", {"REEL": 500, "STORY": 120, "POST": 80})]
    elif metric == "profile_links_taps":
        data = [_split(metric, "contact_button_type", {"CALL": 4, "DIRECTION": 2})]
    elif metric == "follower_demographics":
        values = {
            "country": {"UY": 300, "AR": 120},
            "city": {"Salto, Salto": 200},
            "age": {"25-34": 180, "35-44": 90},
            "gender": {"F": 250, "M": 170},
        }[breakdown]
        data = [_split(metric, breakdown, values, timeframe=True)]
    elif metric == "engaged_audience_demographics":
        # Too few engagements: Meta refuses.
        return httpx.Response(400, json={"error": {"message": "Not enough", "code": 100}})
    else:
        data = [
            _total("views", 700),
            _total("reach", 400),
            _total("total_interactions", 60),
            _total("accounts_engaged", 45),
            _total("likes", 40),
            _total("saves", 5),
            _total("profile_links_taps", 6),
        ]
    return httpx.Response(200, json={"data": data})


@respx.mock
async def test_the_account_day_splits_and_audience(db_session):
    _owner, _page, insta, _ = await _seed(db_session, "-igx1")
    respx.get(url__regex=rf"{_graph()}/1784\w+\?").mock(
        return_value=httpx.Response(200, json={"followers_count": 512})
    )
    respx.get(url__regex=rf"{_graph()}/1784\w+/insights").mock(side_effect=_account_answer)
    day = date(2026, 10, 26)

    result = await adapter_for_inbox(insta).fetch_channel_metrics(
        db_session, await channel_of(db_session, insta), days=[day]
    )

    assert result.ok
    assert result.daily[day] == {
        "views": 700,
        "reach": 400,
        "interactions": 60,
        "accounts_engaged": 45,
        "likes": 40,
        "saves": 5,
        "profile_links_taps": 6,
        "follows": 12,
        "unfollows": 3,
        "views_by_surface": {"reels": 500, "stories": 120, "posts": 80},
        "profile_taps_by_button": {"call": 4, "directions": 2},
    }
    assert result.audience == {
        "followers": {
            "country": {"UY": 300, "AR": 120},
            "city": {"Salto, Salto": 200},
            "age": {"25-34": 180, "35-44": 90},
            "gender": {"F": 250, "M": 170},
        }
    }


@respx.mock
async def test_an_account_without_the_new_metrics_keeps_the_basic_ones(db_session):
    _owner, _page, insta, _ = await _seed(db_session, "-igx2")
    respx.get(url__regex=rf"{_graph()}/1784\w+\?").mock(
        return_value=httpx.Response(200, json={"followers_count": 50})
    )

    def _small(request: httpx.Request) -> httpx.Response:
        metric = request.url.params.get("metric") or ""
        if metric == "views,reach,total_interactions":
            return httpx.Response(200, json={"data": [_total("reach", 9)]})
        return httpx.Response(400, json={"error": {"message": "Invalid metric", "code": 100}})

    respx.get(url__regex=rf"{_graph()}/1784\w+/insights").mock(side_effect=_small)
    day = date(2026, 10, 26)
    result = await adapter_for_inbox(insta).fetch_channel_metrics(
        db_session, await channel_of(db_session, insta), days=[day]
    )
    assert result.ok
    assert result.daily == {day: {"reach": 9}}
    assert result.audience == {}


@respx.mock
@pytest.mark.parametrize(
    ("post_type", "asked", "answer", "expected"),
    [
        (
            "feed",
            {"profile_visits", "follows", "reposts", "saved"},
            [("views", 10), ("profile_visits", 3), ("follows", 1)],
            {"views": 10, "profile_visits": 3, "follows": 1},
        ),
        (
            "reels",
            {"ig_reels_avg_watch_time", "ig_reels_video_view_total_time"},
            [("views", 50), ("ig_reels_avg_watch_time", 7300)],
            {"views": 50, "avg_watch_time_ms": 7300},
        ),
        (
            "story",
            {"replies", "navigation"},
            [("reach", 20), ("replies", 2), ("navigation", 14)],
            {"reach": 20, "replies": 2, "navigation": 14},
        ),
    ],
)
async def test_each_kind_of_post_asks_for_its_own_metrics(
    db_session, post_type, asked, answer, expected
):
    owner, _page, insta, _ = await _seed(db_session, f"-igp{post_type[:2]}")
    _pub, target = await _published(
        db_session,
        owner.account,
        insta,
        external_id=f"M{post_type}",
        media_type="video" if post_type == "reels" else "image",
        settings={"post_type": post_type},
        when=datetime.now(UTC) - timedelta(hours=2),
    )
    route = respx.get(f"{_graph()}/M{post_type}/insights").mock(
        return_value=httpx.Response(
            200, json={"data": [{"name": n, "values": [{"value": v}]} for n, v in answer]}
        )
    )
    assert await analytics.refresh_target_metrics(db_session, target)
    metrics = set(route.calls[0].request.url.params["metric"].split(","))
    assert asked <= metrics
    if post_type == "story":
        assert "likes" not in metrics
    assert target.metrics == expected


@respx.mock
async def test_a_post_that_refuses_a_metric_falls_back_to_the_basic_set(db_session):
    owner, _page, insta, _ = await _seed(db_session, "-igfb")
    _pub, target = await _published(db_session, owner.account, insta, external_id="MOLD")

    def _old_post(request: httpx.Request) -> httpx.Response:
        if "profile_visits" in request.url.params["metric"]:
            return httpx.Response(400, json={"error": {"message": "Unsupported", "code": 100}})
        return httpx.Response(200, json={"data": [{"name": "likes", "values": [{"value": 8}]}]})

    route = respx.get(f"{_graph()}/MOLD/insights").mock(side_effect=_old_post)
    assert await analytics.refresh_target_metrics(db_session, target)
    assert route.call_count == 2
    assert target.metrics == {"likes": 8}


async def test_the_summary_adds_activity_splits_and_audience(client, db_session):
    owner, _page, insta, headers = await _seed(db_session, "-igsum")
    channel = await channel_of(db_session, insta)
    audience = {"followers": {"country": {"UY": 30}}}
    for day, figures in (
        (
            date(2026, 10, 1),
            {
                "followers": 100,
                "views": 70,
                "reach": 40,
                "follows": 5,
                "views_by_surface": {"reels": 50, "posts": 20},
            },
        ),
        (
            date(2026, 10, 2),
            {
                "followers": 104,
                "views": 30,
                "reach": 25,
                "follows": 2,
                "unfollows": 1,
                "views_by_surface": {"reels": 10},
                "profile_taps_by_button": {"call": 3},
                "audience": audience,
            },
        ),
    ):
        db_session.add(
            ChannelMetricSnapshot(
                account_id=owner.account.id,
                channel_id=channel.id,
                network="instagram",
                date=day,
                metrics=figures,
            )
        )
    await db_session.flush()

    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/publications/analytics",
        params={"from": "2026-10-01T00:00:00Z", "to": "2026-10-03T00:00:00Z"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    entry = next(c for c in resp.json()["channels"] if c["channel"]["id"] == channel.id)
    assert entry["activity"] == {"views": 100, "follows": 7, "unfollows": 1}
    assert entry["breakdowns"] == {
        "views_by_surface": {"reels": 60, "posts": 20},
        "profile_taps_by_button": {"call": 3},
    }
    assert entry["audience"] == audience
    # The daily series stays numbers only.
    assert all(not isinstance(v, dict) for point in entry["series"] for v in point.values())
