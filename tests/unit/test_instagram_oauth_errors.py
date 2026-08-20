"""Unit tests for Meta's two OAuth error shapes (no DB, no network).

The reason travels all the way to a banner on the admin's screen, so a
shape we fail to recognise shows up there as a raw JSON body.
"""

from __future__ import annotations

import httpx

from app.domains.instagram.oauth import _extract_error


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
