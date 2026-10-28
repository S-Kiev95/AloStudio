"""Instagram Graph insights for analytics — published media and the account.

Written from Meta's Instagram Media Insights and Instagram User Insights
references (2025 metric set: ``views`` replaced ``impressions``/``plays``):

  * ``GET /{ig-media-id}/insights?metric=…`` — lifetime figures of a post.
    Stories report a smaller set, and only while they are live (24 h);
    after that the ``story_insights`` webhook has stored their figures.
  * ``GET /{ig-user-id}?fields=followers_count`` for the follower count,
    and ``GET /{ig-user-id}/insights?metric=views,reach,total_interactions
    &period=day&metric_type=total_value`` once per requested day.

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
}
_STORY_METRICS = ("views", "reach", "shares", "total_interactions")
_ACCOUNT_METRICS = {
    "views": "views",
    "reach": "reach",
    "total_interactions": "interactions",
}
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
    is_story: bool = False,
) -> tuple[dict[str, int] | None, str | None]:
    """``(metrics, error)`` for one published media."""
    if not channel.access_token:
        return None, "La cuenta de Instagram no tiene token."
    names = _STORY_METRICS if is_story else tuple(_MEDIA_METRICS)
    with graph.graph_host(await _graph_host_for_channel(session, channel)):
        base = graph.graph_base()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                payload = await _get(
                    client,
                    f"{base}/{ig_media_id}/insights",
                    {"metric": ",".join(names)},
                    channel.access_token,
                )
        except _InsightsError as exc:
            return None, _spanish_error(exc)
        except httpx.HTTPError as exc:
            log.warning("instagram.insights.media_transport media=%s err=%s", ig_media_id, exc)
            return None, "No se pudo conectar con Instagram."
    return _collect(payload, _MEDIA_METRICS), None


async def fetch_account_metrics(
    session: AsyncSession,
    channel: InstagramChannel,
    *,
    days: list[date],
) -> tuple[dict[str, int] | None, dict[date, dict[str, int]], str | None]:
    """``(current, daily, error)``: followers now, and views/reach/
    interactions for each of ``days`` when the insights permission allows it
    (a day the permission or Meta can't give is simply left out)."""
    if not channel.access_token:
        return None, {}, "La cuenta de Instagram no tiene token."
    if not channel.instagram_id:
        return None, {}, "La cuenta de Instagram no tiene identificador."
    current: dict[str, int] = {}
    daily: dict[date, dict[str, int]] = {}
    with graph.graph_host(await _graph_host_for_channel(session, channel)):
        base = graph.graph_base()
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
                    start = datetime.combine(day, time.min, tzinfo=UTC)
                    try:
                        payload = await _get(
                            client,
                            f"{base}/{channel.instagram_id}/insights",
                            {
                                "metric": ",".join(_ACCOUNT_METRICS),
                                "period": "day",
                                "metric_type": "total_value",
                                "since": int(start.timestamp()),
                                "until": int((start + timedelta(days=1)).timestamp()),
                            },
                            channel.access_token,
                        )
                    except _InsightsError as exc:
                        # The follower count alone is still worth keeping.
                        log.info(
                            "instagram.insights.daily_unavailable channel=%s day=%s err=%s",
                            channel.id,
                            day,
                            exc,
                        )
                        break
                    figures = _collect(payload, _ACCOUNT_METRICS)
                    if figures:
                        daily[day] = figures
        except _InsightsError as exc:
            return None, {}, _spanish_error(exc)
        except httpx.HTTPError as exc:
            log.warning("instagram.insights.account_transport channel=%s err=%s", channel.id, exc)
            return None, {}, "No se pudo conectar con Instagram."
    return current, daily, None


__all__ = [
    "fetch_account_metrics",
    "fetch_media_metrics",
    "story_metrics_from_webhook",
]
