"""Unit tests for the web-push crypto (RFC 8291 / RFC 8292) — no IO.

The headline test reproduces the RFC 8291 §5 worked example byte-for-byte,
which proves interoperability with real push services (FCM / Mozilla).
"""

from __future__ import annotations

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.webpush import (
    _hkdf,
    b64url_decode,
    b64url_encode,
    encrypt_payload,
    generate_vapid_keys,
    vapid_authorization,
)

pytestmark = pytest.mark.unit

# --- RFC 8291 Section 5 worked example (all base64url) -----------------------
_PLAINTEXT = "V2hlbiBJIGdyb3cgdXAsIEkgd2FudCB0byBiZSBhIHdhdGVybWVsb24"
_AUTH = "BTBZMqHH6r4Tts7J_aSIgg"
_UA_PUBLIC = "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
_AS_PRIVATE = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
_SALT = "DGv6ra1nlYgDCS1FRnbzlw"
_EXPECTED_BODY = (
    "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIg"
    "Dll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVB"
    "St2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
)


def test_encrypt_matches_rfc8291_vector():
    as_private = ec.derive_private_key(
        int.from_bytes(b64url_decode(_AS_PRIVATE), "big"), ec.SECP256R1()
    )
    body = encrypt_payload(
        b64url_decode(_PLAINTEXT),
        p256dh=b64url_decode(_UA_PUBLIC),
        auth=b64url_decode(_AUTH),
        _as_private=as_private,
        _salt=b64url_decode(_SALT),
    )
    assert b64url_encode(body) == _EXPECTED_BODY


def test_encrypt_round_trips_for_a_fresh_subscription():
    ua_priv = ec.generate_private_key(ec.SECP256R1())
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    ua_pub = ua_priv.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint
    )
    auth = b"0123456789abcdef"
    message = "Conversación asignada 🎯".encode()

    body = encrypt_payload(message, p256dh=ua_pub, auth=auth)

    # Decrypt as the user agent would.
    salt, as_pub, ct = body[:16], body[21:86], body[86:]
    as_pubkey = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), as_pub
    )
    ecdh = ua_priv.exchange(ec.ECDH(), as_pubkey)
    ikm = _hkdf(auth, ecdh, b"WebPush: info\x00" + ua_pub + as_pub, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    decrypted = AESGCM(cek).decrypt(nonce, ct, None)
    assert decrypted[-1] == 0x02  # last-record delimiter
    assert decrypted[:-1] == message


def test_vapid_authorization_is_a_verifiable_es256_jwt():
    priv_b64, pub_b64 = generate_vapid_keys()
    header = vapid_authorization(
        "https://fcm.googleapis.com/fcm/send/xyz",
        private_key_b64=priv_b64,
        public_key_b64=pub_b64,
        subject="mailto:ops@alostudio.local",
    )
    assert header.startswith("vapid t=") and ", k=" in header
    token = header[len("vapid t=") :].split(", k=")[0]

    pubkey = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), b64url_decode(pub_b64)
    )
    claims = jwt.decode(
        token,
        pubkey,
        algorithms=["ES256"],
        audience="https://fcm.googleapis.com",
    )
    assert claims["sub"] == "mailto:ops@alostudio.local"
    assert claims["exp"] > 0


def test_generate_vapid_keys_shapes():
    priv_b64, pub_b64 = generate_vapid_keys()
    assert len(b64url_decode(priv_b64)) == 32  # P-256 scalar
    assert len(b64url_decode(pub_b64)) == 65  # uncompressed point
