"""Instagram Graph insights for analytics — published media and the account.

Written from Meta's Instagram Media Insights and Instagram User Insights
references (2025 metric set: ``views`` replaced ``impressions``/``plays``):

  * ``GET /{ig-media-id}/insights?metric=…`` — lifetime figures of a post.
    Each kind (feed post, reel, story) accepts its own set: a metric that
    doesn't apply fails the whole call, so each kind asks for its own, and
    falls back to the basic set if Meta still refuses one. Stories answer
    only while they are live (24 h); after that the ``story_insights``
    webhook has stored their figures.
  * ``GET /{ig-user-id}?fields=followers_count`` for the follower count.
  * ``GET /{ig-user-id}/insights?period=day&metric_type=total_value`` once
    per requested day: the day's figures, then three split ones (follows
    and unfollows, views by surface, profile button taps by button).
  * The same endpoint with ``period=lifetime&timeframe=this_month`` for the
    audience: country, city, age and gender of the followers and of the
    accounts that engaged (Meta answers only past 100 followers).

Needs ``instagram_manage_insights`` (Facebook Login) or
``instagram_business_manage_insights`` (Instagram Login); the follower count
only needs basic access. Like the publisher, nothing here raises on a
Meta-side failure: a failure comes back as a message for the dashboard.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.inboxes.models import InstagramChannel
from app.domains.instagram import graph
from app.domains.instagram.publisher import _extract_error
from app.domains.instagram.publishing_service import _graph_host_for_channel

log = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(20.0, connect=10.0)

# Meta's metric name → the normalised analytics key.
_MEDIA_METRICS = {
    "views": "views",
    "reach": "reach",
    "likes": "likes",
    "comments": "comments",
    "shares": "shares",
    "saved": "saves",
    "total_interactions": "interactions",
    "reposts": "reposts",
    "profile_visits": "profile_visits",
    "profile_activity": "profile_activity",
    "follows": "follows",
    "replies": "replies",
    "navigation": "navigation",
    "link_clicks": "link_clicks",
    "ig_reels_avg_watch_time": "avg_watch_time_ms",
    "ig_reels_video_view_total_time": "watch_time_ms",
}
# What each kind of media accepts (Meta's table, by media product type).
_BASIC_MEDIA = ("views", "reach", "likes", "comments", "shares", "saved", "total_interactions")
_MEDIA_BY_TYPE: dict[str, tuple[str, ...]] = {
    "feed": (*_BASIC_MEDIA, "reposts", "profile_visits", "profile_activity", "follows"),
    "reels": (
        *_BASIC_MEDIA,
        "reposts",
        "ig_reels_avg_watch_time",
        "ig_reels_video_view_total_time",
    ),
    "story": (
        "views",
        "reach",
        "shares",
        "total_interactions",
        "replies",
        "navigation",
        "profile_visits",
        "follows",
    ),
}
_BASIC_BY_TYPE: dict[str, tuple[str, ...]] = {
    "feed": _BASIC_MEDIA,
    "reels": _BASIC_MEDIA,
    "story": ("views", "reach", "shares", "total_interactions"),
}
_ACCOUNT_METRICS = {
    "views": "views",
    "reach": "reach",
    "total_interactions": "interactions",
    "accounts_engaged": "accounts_engaged",
    "likes": "likes",
    "comments": "comments",
    "shares": "shares",
    "saves": "saves",
    "reposts": "reposts",
    "replies": "replies",
    "profile_links_taps": "profile_links_taps",
}
_BASIC_ACCOUNT = ("views", "reach", "total_interactions")
# Split figures of a day: (metric, breakdown, how to name its values).
_FOLLOW_TYPES = {"FOLLOWER": "follows", "NON_FOLLOWER": "unfollows"}
_SURFACES = {
    "REEL": "reels",
    "REELS": "reels",
    "STORY": "stories",
    "POST": "posts",
    "CAROUSEL_CONTAINER": "posts",
    "FEED": "posts",
    "AD": "ads",
}
_BUTTONS = {
    "CALL": "call",
    "EMAIL": "email",
    "DIRECTION": "directions",
    "TEXT": "message",
    "BOOK_NOW": "book",
    "INSTANT_EXPERIENCE": "instant_experience",
}
_AUDIENCE_METRICS = {
    "follower_demographics": "followers",
    "engaged_audience_demographics": "engaged",
}
_AUDIENCE_DIMENSIONS = ("country", "city", "age", "gender")
# Meta returns up to 45 values per dimension; the dashboard shows the top.
_AUDIENCE_TOP = 10
# What the ``story_insights`` webhook stores (older payloads say
# ``impressions`` where newer ones say ``views``).
_STORY_WEBHOOK_METRICS = {
    "views": "views",
    "impressions": "views",
    "reach": "reach",
    "replies": "comments",
}

_TOKEN_CODES = {"190"}
_PERMISSION_CODES = {"10"} | {str(c) for c in range(200, 300)}
_RATE_LIMIT_CODES = {"4", "17", "32", "613", "80001", "80002"}


class _InsightsError(Exception):
    def __init__(self, code: str | None, message: str | None) -> None:
        super().__init__(message or "")
        self.code = code

    @property
    def is_refusal(self) -> bool:
        """The token, the permission or the rate limit: asking for less
        won't help, unlike a metric this media or account doesn't have."""
        return self.code in _TOKEN_CODES | _PERMISSION_CODES | _RATE_LIMIT_CODES


def _value(item: dict[str, Any]) -> int | None:
    """Media insights carry ``values[0].value``; ``total_value`` metrics
    carry ``total_value.value``."""
    total = item.get("total_value")
    if isinstance(total, dict) and isinstance(total.get("value"), int):
        return total["value"]
    values = item.get("values")
    if isinstance(values, list) and values and isinstance(values[0], dict):
        value = values[0].get("value")
        return value if isinstance(value, int) else None
    return None


def _collect(payload: dict[str, Any], names: dict[str, str]) -> dict[str, int]:
    metrics: dict[str, int] = {}
    for item in payload.get("data") or []:
        key = names.get(item.get("name")) if isinstance(item, dict) else None
        value = _value(item) if key else None
        if key and value is not None:
            metrics[key] = value
    return metrics


def _split(payload: dict[str, Any], rename: dict[str, str] | None = None) -> dict[str, int]:
    """``{dimension value: n}`` of the first metric's first breakdown. The
    last dimension is the one asked for (demographics put ``timeframe``
    first). Unknown values keep their name, lowercased."""
    out: dict[str, int] = {}
    for item in payload.get("data") or []:
        breakdowns = ((item or {}).get("total_value") or {}).get("breakdowns") or []
        for result in (breakdowns[0] if breakdowns else {}).get("results") or []:
            values = result.get("dimension_values") or []
            value = result.get("value")
            if not values or not isinstance(value, int):
                continue
            raw = str(values[-1])
            name = (rename or {}).get(raw.upper(), raw if rename is None else raw.lower())
            out[name] = out.get(name, 0) + value
        break
    return out


def _spanish_error(exc: _InsightsError) -> str:
    if exc.code in _TOKEN_CODES:
        return "La conexión con Instagram venció. Volvé a conectar la cuenta."
    if exc.code in _PERMISSION_CODES:
        return (
            "Instagram no dio permiso para leer estadísticas (instagram_manage_insights "
            "o instagram_business_manage_insights)."
        )
    if exc.code in _RATE_LIMIT_CODES:
        return "Instagram limitó las consultas por ahora; se reintenta más tarde."
    return f"Instagram no devolvió estadísticas: {exc}".strip()


async def _get(
    client: httpx.AsyncClient, url: str, params: dict[str, Any], token: str
) -> dict[str, Any]:
    resp = await client.get(url, params={**params, "access_token": token})
    try:
        payload = resp.json()
    except ValueError:
        payload = None
    if resp.status_code >= 400 or (isinstance(payload, dict) and "error" in payload):
        raise _InsightsError(*_extract_error(resp))
    return payload if isinstance(payload, dict) else {}


async def _get_metrics(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any],
    token: str,
    *,
    wanted: tuple[str, ...],
    basic: tuple[str, ...],
) -> dict[str, Any]:
    """Ask for ``wanted``; if Meta refuses one of them (it doesn't apply to
    this media, or the account is too small), ask again for ``basic``."""
    try:
        return await _get(client, url, {**params, "metric": ",".join(wanted)}, token)
    except _InsightsError as exc:
        if exc.is_refusal or wanted == basic:
            raise
        log.info("instagram.insights.narrowed url=%s err=%s", url, exc)
        return await _get(client, url, {**params, "metric": ",".join(basic)}, token)


async def _optional(
    client: httpx.AsyncClient, url: str, params: dict[str, Any], token: str
) -> dict[str, Any]:
    """A figure the account may not have (fewer than 100 followers, too
    few engagements): an error just leaves it out."""
    try:
        return await _get(client, url, params, token)
    except _InsightsError as exc:
        if exc.code in _TOKEN_CODES:
            raise
        log.info("instagram.insights.optional_unavailable url=%s err=%s", url, exc)
        return {}


def story_metrics_from_webhook(stored: dict[str, Any] | None) -> dict[str, int]:
    """Normalise the figures the ``story_insights`` webhook stored."""
    metrics: dict[str, int] = {}
    for name, key in _STORY_WEBHOOK_METRICS.items():
        value = (stored or {}).get(name)
        if isinstance(value, int) and key not in metrics:
            metrics[key] = value
    return metrics


async def fetch_media_metrics(
    session: AsyncSession,
    channel: InstagramChannel,
    *,
    ig_media_id: str,
    post_type: str = "feed",
) -> tuple[dict[str, int] | None, str | None]:
    """``(metrics, error)`` for one published media of ``post_type``
    (``feed``, ``reels`` or ``story``)."""
    if not channel.access_token:
        return None, "La cuenta de Instagram no tiene token."
    kind = post_type if post_type in _MEDIA_BY_TYPE else "feed"
    with graph.graph_host(await _graph_host_for_channel(session, channel)):
        base = graph.graph_base()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                payload = await _get_metrics(
                    client,
                    f"{base}/{ig_media_id}/insights",
                    {},
                    channel.access_token,
                    wanted=_MEDIA_BY_TYPE[kind],
                    basic=_BASIC_BY_TYPE[kind],
                )
        except _InsightsError as exc:
            return None, _spanish_error(exc)
        except httpx.HTTPError as exc:
            log.warning("instagram.insights.media_transport media=%s err=%s", ig_media_id, exc)
            return None, "No se pudo conectar con Instagram."
    return _collect(payload, _MEDIA_METRICS), None


async def _day_figures(
    client: httpx.AsyncClient, url: str, token: str, day: date
) -> dict[str, Any]:
    start = datetime.combine(day, time.min, tzinfo=UTC)
    window = {
        "period": "day",
        "metric_type": "total_value",
        "since": int(start.timestamp()),
        "until": int((start + timedelta(days=1)).timestamp()),
    }
    figures: dict[str, Any] = _collect(
        await _get_metrics(
            client, url, window, token, wanted=tuple(_ACCOUNT_METRICS), basic=_BASIC_ACCOUNT
        ),
        _ACCOUNT_METRICS,
    )
    follows = _split(
        await _optional(
            client,
            url,
            {**window, "metric": "follows_and_unfollows", "breakdown": "follow_type"},
            token,
        ),
        _FOLLOW_TYPES,
    )
    figures.update({k: v for k, v in follows.items() if k in ("follows", "unfollows")})
    by_surface = _split(
        await _optional(
            client, url, {**window, "metric": "views", "breakdown": "media_product_type"}, token
        ),
        _SURFACES,
    )
    if by_surface:
        figures["views_by_surface"] = by_surface
    by_button = _split(
        await _optional(
            client,
            url,
            {**window, "metric": "profile_links_taps", "breakdown": "contact_button_type"},
            token,
        ),
        _BUTTONS,
    )
    if by_button:
        figures["profile_taps_by_button"] = by_button
    return figures


async def _audience(client: httpx.AsyncClient, url: str, token: str) -> dict[str, Any]:
    """``{"followers"|"engaged": {dimension: {value: n}}}``, the top values
    of each; empty when Meta has none for this account."""
    out: dict[str, Any] = {}
    for metric, who in _AUDIENCE_METRICS.items():
        for dimension in _AUDIENCE_DIMENSIONS:
            split = _split(
                await _optional(
                    client,
                    url,
                    {
                        "metric": metric,
                        "period": "lifetime",
                        "timeframe": "this_month",
                        "metric_type": "total_value",
                        "breakdown": dimension,
                    },
                    token,
                )
            )
            if split:
                top = sorted(split.items(), key=lambda kv: kv[1], reverse=True)[:_AUDIENCE_TOP]
                out.setdefault(who, {})[dimension] = dict(top)
    return out


async def fetch_account_metrics(
    session: AsyncSession,
    channel: InstagramChannel,
    *,
    days: list[date],
) -> tuple[dict[str, int] | None, dict[date, dict[str, Any]], dict[str, Any], str | None]:
    """``(current, daily, audience, error)``: followers now; the figures of
    each of ``days`` when the insights permission allows it (a day Meta
    can't give is left out); and the current audience."""
    if not channel.access_token:
        return None, {}, {}, "La cuenta de Instagram no tiene token."
    if not channel.instagram_id:
        return None, {}, {}, "La cuenta de Instagram no tiene identificador."
    current: dict[str, int] = {}
    daily: dict[date, dict[str, Any]] = {}
    audience: dict[str, Any] = {}
    with graph.graph_host(await _graph_host_for_channel(session, channel)):
        base = graph.graph_base()
        url = f"{base}/{channel.instagram_id}/insights"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                profile = await _get(
                    client,
                    f"{base}/{channel.instagram_id}",
                    {"fields": "followers_count"},
                    channel.access_token,
                )
                if isinstance(profile.get("followers_count"), int):
                    current["followers"] = profile["followers_count"]
                for day in days:
                    try:
                        figures = await _day_figures(client, url, channel.access_token, day)
                    except _InsightsError as exc:
                        # The follower count alone is still worth keeping.
                        log.info(
                            "instagram.insights.daily_unavailable channel=%s day=%s err=%s",
                            channel.id,
                            day,
                            exc,
                        )
                        break
                    if figures:
                        daily[day] = figures
                if daily:
                    # Only with the insights permission (the days needed it).
                    audience = await _audience(client, url, channel.access_token)
        except _InsightsError as exc:
            return None, {}, {}, _spanish_error(exc)
        except httpx.HTTPError as exc:
            log.warning("instagram.insights.account_transport channel=%s err=%s", channel.id, exc)
            return None, {}, {}, "No se pudo conectar con Instagram."
    return current, daily, audience, None


__all__ = [
    "fetch_account_metrics",
    "fetch_media_metrics",
    "story_metrics_from_webhook",
]
