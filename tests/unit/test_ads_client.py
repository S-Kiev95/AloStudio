"""Marketing API insights client — parsing, paging and failure handling.

The account this was built against has no ad spend, so the shapes here come
from Meta's documented insights response rather than a captured one. The
client is written to tolerate that: it reads what it recognises, drops what
it cannot key on, and keeps the untouched row.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from app.domains.ads.client import fetch_ad_insights
from app.domains.instagram.graph import graph_base

pytestmark = pytest.mark.unit

TOKEN = "TOKEN"  # a fixture value, not a credential
ACCOUNT = "123456789"
INSIGHTS_URL = f"{graph_base()}/act_{ACCOUNT}/insights"


def _row(ad_id: str, day: str, spend: str, **over):
    base = {
        "ad_id": ad_id,
        "ad_name": "20% OFF",
        "date_start": day,
        "date_stop": day,
        "spend": spend,
        "impressions": "1500",
        "clicks": "42",
        "reach": "1200",
        "account_currency": "ARS",
    }
    base.update(over)
    return base


async def _fetch():
    return await fetch_ad_insights(
        ad_account_id=ACCOUNT,
        access_token=TOKEN,
        since=date(2026, 8, 1),
        until=date(2026, 8, 2),
    )


@respx.mock
async def test_parses_a_daily_row():
    respx.get(INSIGHTS_URL).mock(
        return_value=httpx.Response(
            200, json={"data": [_row("111", "2026-08-01", "1234.56")]}
        )
    )
    result = await _fetch()
    assert result.ok
    (row,) = result.rows
    assert row.ad_id == "111"
    assert row.date == date(2026, 8, 1)
    assert row.spend == pytest.approx(1234.56)
    assert row.currency == "ARS"
    assert row.impressions == 1500
    assert row.clicks == 42
    # The untouched entry is kept for later reconciliation.
    assert row.raw["date_stop"] == "2026-08-01"


@respx.mock
async def test_accepts_an_account_id_that_already_has_the_prefix():
    """Callers may store either ``123`` or ``act_123``."""
    route = respx.get(INSIGHTS_URL).mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    result = await fetch_ad_insights(
        ad_account_id=f"act_{ACCOUNT}",
        access_token=TOKEN,
        since=date(2026, 8, 1),
        until=date(2026, 8, 2),
    )
    assert result.ok
    assert route.called  # no doubled "act_act_" prefix


@respx.mock
async def test_follows_pagination():
    page2 = "https://graph.facebook.com/next-page"
    respx.get(INSIGHTS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [_row("111", "2026-08-01", "10")],
                "paging": {"next": page2},
            },
        )
    )
    respx.get(page2).mock(
        return_value=httpx.Response(
            200, json={"data": [_row("222", "2026-08-02", "20")]}
        )
    )
    result = await _fetch()
    assert result.ok
    assert [r.ad_id for r in result.rows] == ["111", "222"]


@respx.mock
async def test_rows_without_an_ad_or_a_day_are_dropped():
    """Account-level totals come back with no ad_id — nothing to key on."""
    respx.get(INSIGHTS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"spend": "99", "date_start": "2026-08-01"},  # no ad_id
                    {"ad_id": "111", "spend": "5"},  # no day
                    _row("222", "2026-08-01", "7"),
                ]
            },
        )
    )
    result = await _fetch()
    assert [r.ad_id for r in result.rows] == ["222"]


@respx.mock
async def test_an_api_error_reports_not_ok_and_keeps_no_rows():
    """A failed sync must leave cached figures alone, not blank them."""
    respx.get(INSIGHTS_URL).mock(
        return_value=httpx.Response(
            400,
            json={"error": {"code": 190, "message": "Invalid OAuth access token"}},
        )
    )
    result = await _fetch()
    assert result.ok is False
    assert result.rows == []
    assert result.error_code == "190"
    assert "OAuth" in (result.error_message or "")


@respx.mock
async def test_a_transport_failure_is_not_raised():
    respx.get(INSIGHTS_URL).mock(side_effect=httpx.ConnectError("boom"))
    result = await _fetch()
    assert result.ok is False
    assert result.error_code == "transport"


@respx.mock
async def test_missing_numbers_default_instead_of_raising():
    respx.get(INSIGHTS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "ad_id": "111",
                        "date_start": "2026-08-01",
                        "spend": "not-a-number",
                    }
                ]
            },
        )
    )
    result = await _fetch()
    (row,) = result.rows
    assert row.spend == 0.0
    assert row.impressions == 0
    assert row.currency is None
