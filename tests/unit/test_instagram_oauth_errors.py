"""Unit tests for what ``oauth.py`` reads back from Meta (no DB).

Both of these surface directly on the admin's screen now that the connect
callback redirects: the error message becomes the failure banner, and the
handle becomes the inbox's name.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.domains.instagram.oauth import (
    FACEBOOK_LOGIN_SCOPES,
    PAGE_WEBHOOK_FIELDS,
    _extract_error,
    fetch_profile,
    subscribe_page_webhooks,
)


def test_facebook_nests_the_error():
    resp = httpx.Response(
        400,
        json={
            "error": {
                "code": 190,
                "message": "Error validating access token",
            }
        },
    )
    assert _extract_error(resp) == ("190", "Error validating access token")


def test_instagram_login_answers_flat():
    """``api.instagram.com/oauth/access_token`` has no ``error`` key."""
    resp = httpx.Response(
        400,
        json={
            "error_type": "OAuthException",
            "code": 400,
            "error_message": "Invalid authorization code",
        },
    )
    assert _extract_error(resp) == ("400", "Invalid authorization code")


def test_instagram_shape_without_a_code_falls_back_to_the_status():
    resp = httpx.Response(
        400,
        json={"error_type": "OAuthException", "error_message": "no sirve"},
    )
    assert _extract_error(resp) == ("OAuthException", "no sirve")


def test_an_unrecognised_body_keeps_the_raw_text():
    resp = httpx.Response(502, text="<html>bad gateway</html>")
    code, message = _extract_error(resp)
    assert code == "502"
    assert "bad gateway" in (message or "")


def test_a_json_list_is_not_mistaken_for_an_error_object():
    resp = httpx.Response(400, json=["nope"])
    code, _ = _extract_error(resp)
    assert code == "400"


def test_a_long_message_is_truncated():
    resp = httpx.Response(400, json={"error": {"message": "x" * 900}})
    _, message = _extract_error(resp)
    assert message is not None
    assert len(message) == 500


# ---------------------------------------------------------------------------
# Who does this token belong to?  (names the inbox at connect time)
# ---------------------------------------------------------------------------
@respx.mock
async def test_instagram_login_prefers_the_canonical_id():
    """``/me`` answers with both ids. ``user_id`` is the one webhooks
    carry; the token exchange only ever hands back the app-scoped ``id``.
    Every outbound edge accepts either, so picking the wrong one looks
    like it works right until nothing inbound ever arrives."""
    route = respx.get("https://graph.instagram.com/v23.0/me").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "28005623165709042",
                "user_id": "17841406706985469",
                "username": "s_kiev995",
            },
        )
    )
    canonical, username = await fetch_profile(
        instagram_id="28005623165709042",
        access_token="TOK",
        login_type="instagram",
    )
    assert canonical == "17841406706985469"
    assert username == "s_kiev995"
    assert "user_id" in route.calls[0].request.url.params["fields"]


@respx.mock
async def test_facebook_login_addresses_the_account_by_id():
    """A Page token isn't bound to one account, so /me would be wrong —
    and the id we already hold there is already the canonical one."""
    route = respx.get(
        "https://graph.facebook.com/v23.0/17841451736515320"
    ).mock(return_value=httpx.Response(200, json={"username": "yoruguamaps"}))
    canonical, username = await fetch_profile(
        instagram_id="17841451736515320",
        access_token="PAGETOK",
        login_type="facebook",
    )
    assert canonical == "17841451736515320"
    assert username == "yoruguamaps"
    assert route.called


@respx.mock
async def test_a_missing_handle_still_yields_the_id():
    """An inbox can live with a placeholder name. It cannot live with the
    wrong id."""
    respx.get("https://graph.instagram.com/v23.0/me").mock(
        return_value=httpx.Response(200, json={"user_id": "17841406706985469"})
    )
    canonical, username = await fetch_profile(
        instagram_id="2800", access_token="TOK", login_type="instagram"
    )
    assert canonical == "17841406706985469"
    assert username is None


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(400, json={"error": {"message": "token vencido"}}),
        httpx.Response(200, json={"id": "123"}),  # app-scoped id only
        httpx.Response(200, text="not json"),
        httpx.Response(200, json=["nope"]),
    ],
)
async def test_nothing_usable_comes_back_as_a_pair_of_nones(response):
    respx.get("https://graph.instagram.com/v23.0/me").mock(
        return_value=response
    )
    assert await fetch_profile(
        instagram_id="1", access_token="TOK", login_type="instagram"
    ) == (None, None)


@respx.mock
async def test_a_network_failure_never_surfaces_the_token():
    respx.get("https://graph.instagram.com/v23.0/me").mock(
        side_effect=httpx.ConnectError("boom")
    )
    assert await fetch_profile(
        instagram_id="1", access_token="SECRETO", login_type="instagram"
    ) == (None, None)


# ---------------------------------------------------------------------------
# Installing the app on a Page (the Facebook-Login half of the webhook)
# ---------------------------------------------------------------------------
def test_facebook_login_asks_for_the_dm_scopes():
    """Without these the connect succeeds and the inbox never receives a
    DM — the whole reason to prefer Facebook Login."""
    assert "instagram_manage_messages" in FACEBOOK_LOGIN_SCOPES
    assert "pages_messaging" in FACEBOOK_LOGIN_SCOPES


def test_the_subscribed_fields_are_the_ones_the_receiver_handles():
    assert set(PAGE_WEBHOOK_FIELDS) == {
        "messages",
        "messaging_seen",
        "comments",
        "mentions",
    }
    # message_reads is the Messenger name; Instagram uses messaging_seen.
    assert "message_reads" not in PAGE_WEBHOOK_FIELDS


@respx.mock
async def test_the_page_is_installed_on_the_facebook_host():
    route = respx.post(
        "https://graph.facebook.com/v23.0/PAGE1/subscribed_apps"
    ).mock(return_value=httpx.Response(200, json={"success": True}))
    ok, err = await subscribe_page_webhooks(page_id="PAGE1", page_token="PT")
    assert (ok, err) == (True, None)
    sent = route.calls[0].request.url.params["subscribed_fields"]
    assert "messages" in sent
    assert "comments" in sent


@respx.mock
async def test_a_refused_subscription_is_reported_not_raised():
    """A connection that publishes but receives nothing is still worth
    keeping — the caller logs and carries on."""
    respx.post(
        "https://graph.facebook.com/v23.0/PAGE1/subscribed_apps"
    ).mock(
        return_value=httpx.Response(
            403, json={"error": {"code": 200, "message": "sin permiso"}}
        )
    )
    ok, err = await subscribe_page_webhooks(page_id="PAGE1", page_token="PT")
    assert ok is False
    assert err == "sin permiso"


@respx.mock
async def test_success_false_is_not_mistaken_for_success():
    respx.post(
        "https://graph.facebook.com/v23.0/PAGE1/subscribed_apps"
    ).mock(return_value=httpx.Response(200, json={"success": False}))
    ok, _err = await subscribe_page_webhooks(page_id="PAGE1", page_token="PT")
    assert ok is False


@respx.mock
async def test_a_network_failure_never_surfaces_the_page_token():
    respx.post(
        "https://graph.facebook.com/v23.0/PAGE1/subscribed_apps"
    ).mock(side_effect=httpx.ConnectError("boom"))
    ok, err = await subscribe_page_webhooks(
        page_id="PAGE1", page_token="SECRETO"
    )
    assert ok is False
    assert err == "ConnectError"
