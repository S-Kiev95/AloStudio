"""Smoke tests for password hashing + JWT — no DB involved."""

from __future__ import annotations

import time

import jwt
import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

pytestmark = pytest.mark.unit


def test_bcrypt_roundtrip() -> None:
    h = hash_password("Password123!")
    assert h.startswith("$2")  # bcrypt prefix
    assert verify_password("Password123!", h)
    assert not verify_password("wrong", h)


def test_bcrypt_does_not_match_empty() -> None:
    h = hash_password("Password123!")
    assert not verify_password("", h)


def test_access_token_roundtrip() -> None:
    tok = create_access_token(subject=42, extra={"account_id": 1})
    payload = decode_token(tok)
    assert payload["sub"] == "42"
    assert payload["typ"] == "access"
    assert payload["account_id"] == 1
    assert payload["exp"] > int(time.time())


def test_refresh_token_type() -> None:
    payload = decode_token(create_refresh_token(subject="7"))
    assert payload["typ"] == "refresh"


def test_tampered_token_rejected() -> None:
    tok = create_access_token(subject=1)
    tampered = tok[:-2] + ("AA" if tok[-2:] != "AA" else "BB")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(tampered)
