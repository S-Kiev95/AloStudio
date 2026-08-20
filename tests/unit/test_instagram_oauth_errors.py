"""Unit tests for what ``oauth.py`` reads back from Meta (no DB).

Both of these surface directly on the admin's screen now that the connect
callback redirects: the error message becomes the failure banner, and the
handle becomes the inbox's name.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.domains.instagram.oauth import _extract_error, fetch_username


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
async def test_instagram_login_reads_the_handle_off_me():
    route = respx.get("https://graph.instagram.com/v23.0/me").mock(
        return_value=httpx.Response(200, json={"username": "s_kiev995"})
    )
    got = await fetch_username(
        instagram_id="28005623165709042",
        access_token="TOK",
        login_type="instagram",
    )
    assert got == "s_kiev995"
    assert route.called


@respx.mock
async def test_facebook_login_addresses_the_account_by_id():
    """A Page token isn't bound to one account, so /me would be wrong."""
    route = respx.get(
        "https://graph.facebook.com/v23.0/17841451736515320"
    ).mock(return_value=httpx.Response(200, json={"username": "yoruguamaps"}))
    got = await fetch_username(
        instagram_id="17841451736515320",
        access_token="PAGETOK",
        login_type="facebook",
    )
    assert got == "yoruguamaps"
    assert route.called


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(400, json={"error": {"message": "token vencido"}}),
        httpx.Response(200, json={"id": "123"}),  # no username field
        httpx.Response(200, text="not json"),
    ],
)
async def test_an_unavailable_handle_is_not_an_error(response):
    """The connection is worth keeping even with no display name."""
    respx.get("https://graph.instagram.com/v23.0/me").mock(
        return_value=response
    )
    got = await fetch_username(
        instagram_id="1", access_token="TOK", login_type="instagram"
    )
    assert got is None


@respx.mock
async def test_a_network_failure_never_surfaces_the_token():
    respx.get("https://graph.instagram.com/v23.0/me").mock(
        side_effect=httpx.ConnectError("boom")
    )
    got = await fetch_username(
        instagram_id="1", access_token="SECRETO", login_type="instagram"
    )
    assert got is None
