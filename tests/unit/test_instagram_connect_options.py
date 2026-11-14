"""Which connect buttons the panel shows: Instagram Login only when this
installation has its own Instagram app (newer Meta apps don't offer it)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domains.instagram import connect_service


def _settings(**over: str) -> SimpleNamespace:
    base = {
        "meta_app_id": "1",
        "meta_app_secret": "s",
        "meta_oauth_redirect_uri": "https://x.example/cb",
        "meta_instagram_app_id": "",
        "meta_instagram_app_secret": "",
    }
    return SimpleNamespace(**{**base, **over})


@pytest.mark.parametrize(
    ("over", "expected"),
    [
        ({}, {"facebook_login": True, "instagram_login": False}),
        (
            {"meta_instagram_app_id": "9", "meta_instagram_app_secret": "z"},
            {"facebook_login": True, "instagram_login": True},
        ),
        ({"meta_oauth_redirect_uri": ""}, {"facebook_login": False, "instagram_login": False}),
    ],
)
def test_connect_options(monkeypatch, over, expected):
    monkeypatch.setattr(connect_service, "get_settings", lambda: _settings(**over))
    assert connect_service.connect_options() == expected
