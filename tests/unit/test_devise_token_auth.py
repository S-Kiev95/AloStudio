"""Unit tests for the session-token check in
:mod:`app.core.auth.devise_token_auth` (no DB).

BCrypt is slow on purpose, so a successful compare is memoized: these
tests pin that a repeat check skips BCrypt and that a wrong token, an
expired session or a revoked one is still refused.
"""

from __future__ import annotations

import time

import pytest

from app.core.auth import devise_token_auth as dta


@pytest.fixture(autouse=True)
def _empty_cache():
    dta._verified.clear()
    yield
    dta._verified.clear()


def _tokens(raw: str, *, expiry: int | None = None) -> dict:
    return {
        "c1": {
            "token": dta._hash_token(raw),
            "expiry": expiry if expiry is not None else int(time.time()) + 3600,
        }
    }


def test_repeat_check_skips_bcrypt(monkeypatch):
    tokens = _tokens("secret-token")
    assert dta.verify_auth_token(tokens, client="c1", access_token="secret-token")

    calls = []
    real = dta.bcrypt.checkpw
    monkeypatch.setattr(
        dta.bcrypt, "checkpw", lambda *a: calls.append(a) or real(*a)
    )
    assert dta.verify_auth_token(tokens, client="c1", access_token="secret-token")
    assert calls == []


def test_wrong_token_is_refused_and_not_cached():
    tokens = _tokens("secret-token")
    assert not dta.verify_auth_token(tokens, client="c1", access_token="guess")
    assert not dta.verify_auth_token(tokens, client="c1", access_token="guess")
    assert len(dta._verified) == 0


def test_expired_session_is_refused_after_a_cached_success():
    raw = "secret-token"
    tokens = _tokens(raw)
    assert dta.verify_auth_token(tokens, client="c1", access_token=raw)

    tokens["c1"]["expiry"] = int(time.time()) - 1
    assert not dta.verify_auth_token(tokens, client="c1", access_token=raw)


def test_revoked_session_is_refused_after_a_cached_success():
    raw = "secret-token"
    tokens = _tokens(raw)
    assert dta.verify_auth_token(tokens, client="c1", access_token=raw)

    assert not dta.verify_auth_token({}, client="c1", access_token=raw)
    # A new session for the same client stores a new hash.
    assert not dta.verify_auth_token(
        _tokens("another-token"), client="c1", access_token=raw
    )


def test_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(dta, "_VERIFIED_MAX", 2)
    for raw in ("a", "b", "c"):
        assert dta.verify_auth_token(_tokens(raw), client="c1", access_token=raw)
    assert len(dta._verified) == 2
