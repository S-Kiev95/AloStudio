"""Meta Marketing API client — ad-level insights.

One call: the ad account's insights broken down per ad per day, which is
what :mod:`app.domains.ads.service` caches and the reports join against
``conversations.ad_id``.

Deliberately narrow. The Marketing API is enormous; we read delivery
figures and never create or edit campaigns, so the integration needs
``ads_read`` rather than full ``ads_management`` — a materially smaller
ask at App Review.

Never raises for a bad response: a failed sync must leave the previously
cached figures alone rather than blank a report.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx

from app.domains.instagram.graph import graph_base

log = logging.getLogger(__name__)

_TIMEOUT = 30.0
# Meta paginates insights; a month of daily rows for a busy account can run
# to several pages. Bounded so a pathological response cannot spin forever.
_MAX_PAGES = 20


@dataclass
class AdInsightRow:
    """One ad's figures for one day, normalised."""

    ad_id: str
    date: date
    spend: float = 0.0
    currency: str | None = None
    impressions: int = 0
    clicks: int = 0
    reach: int = 0
    ad_name: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class InsightsResult:
    """Outcome of a fetch. ``ok`` False means keep the cached numbers."""

    ok: bool
    rows: list[AdInsightRow] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _parse_row(raw: dict[str, Any]) -> AdInsightRow | None:
    """Normalise one insights entry; None when it carries no ad to key on."""
    ad_id = raw.get("ad_id")
    # ``date_start`` is the day when time_increment=1 is requested.
    day = raw.get("date_start")
    if not ad_id or not day:
        return None
    try:
        parsed = date.fromisoformat(str(day))
    except ValueError:
        return None
    return AdInsightRow(
        ad_id=str(ad_id),
        date=parsed,
        spend=_num(raw.get("spend")),
        # Meta omits the currency when the account has never spent.
        currency=(str(raw["account_currency"]) if raw.get("account_currency") else None),
        impressions=_int(raw.get("impressions")),
        clicks=_int(raw.get("clicks")),
        reach=_int(raw.get("reach")),
        ad_name=(str(raw["ad_name"]) if raw.get("ad_name") else None),
        raw=raw,
    )


def _error_of(payload: Any) -> tuple[str | None, str | None]:
    if not isinstance(payload, dict):
        return None, None
    err = payload.get("error")
    if not isinstance(err, dict):
        return None, None
    code = err.get("code")
    return (str(code) if code is not None else None), err.get("message")


async def fetch_ad_insights(
    *,
    ad_account_id: str,
    access_token: str,
    since: date,
    until: date,
) -> InsightsResult:
    """Read per-ad, per-day insights for ``[since, until]``.

    ``ad_account_id`` is the numeric id; the ``act_`` prefix Meta's endpoint
    expects is added here so callers can store either form.
    """
    account = (
        ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
    )
    # ``graph_base()`` already carries scheme, host and the configured API
    # version, so the version is never pinned twice.
    url = f"{graph_base()}/{account}/insights"
    params: dict[str, Any] = {
        "level": "ad",
        "fields": "ad_id,ad_name,spend,impressions,clicks,reach,account_currency",
        # One row per ad per day — the granularity the cache stores.
        "time_increment": 1,
        "time_range": f'{{"since":"{since.isoformat()}","until":"{until.isoformat()}"}}',
        "limit": 500,
        "access_token": access_token,
    }

    rows: list[AdInsightRow] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            next_url: str | None = url
            next_params: dict[str, Any] | None = params
            for _page in range(_MAX_PAGES):
                if next_url is None:
                    break
                resp = await client.get(next_url, params=next_params)
                payload = resp.json() if resp.content else {}
                if resp.status_code >= 400:
                    code, message = _error_of(payload)
                    log.warning(
                        "ads.insights.failed account=%s status=%s code=%s msg=%s",
                        account, resp.status_code, code, message,
                    )
                    return InsightsResult(
                        ok=False,
                        error_code=code or str(resp.status_code),
                        error_message=message or "insights request failed",
                    )
                for entry in payload.get("data") or []:
                    if isinstance(entry, dict):
                        parsed = _parse_row(entry)
                        if parsed is not None:
                            rows.append(parsed)
                # The cursor URL already carries the token and every param.
                next_url = ((payload.get("paging") or {}).get("next")) or None
                next_params = None
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning("ads.insights.transport_error account=%s error=%s", account, exc)
        return InsightsResult(
            ok=False, error_code="transport", error_message=str(exc)
        )

    return InsightsResult(ok=True, rows=rows)


__all__ = ["AdInsightRow", "InsightsResult", "fetch_ad_insights"]
