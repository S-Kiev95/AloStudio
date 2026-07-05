"""Web-push payload encryption (RFC 8291) + VAPID headers (RFC 8292).

Hand-rolled on top of ``cryptography`` (no ``pywebpush`` / ``py_vapid``
dependency) — the codebase's dependency-light posture. We emit a single
``aes128gcm`` record (RFC 8188) keyed per RFC 8291, with an RFC 8292 VAPID
``Authorization`` header signed ES256.

The algorithm (RFC 8291 §3.4):

  ecdh    = ECDH(server_ephemeral_private, subscription_public)
  ikm     = HKDF(salt=auth, ikm=ecdh,
                 info="WebPush: info\\0" + ua_public + as_public, 32)
  CEK     = HKDF(salt=salt, ikm, "Content-Encoding: aes128gcm\\0", 16)
  nonce   = HKDF(salt=salt, ikm, "Content-Encoding: nonce\\0", 12)
  body    = salt || rs(4) || idlen(1) || as_public || AES128GCM(CEK, nonce, data||0x02)

``HKDF(salt, ikm, info, L)`` is RFC 5869 with a single expand block.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import struct
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from urllib.parse import urlparse

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

_RECORD_SIZE = 4096


def b64url_decode(data: str) -> bytes:
    return urlsafe_b64decode(data + "=" * (-len(data) % 4))


def b64url_encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    return hmac.new(prk, info + b"\x01", hashlib.sha256).digest()[:length]


def _point(pub: ec.EllipticCurvePublicKey) -> bytes:
    return pub.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)


def encrypt_payload(
    payload: bytes,
    *,
    p256dh: bytes,
    auth: bytes,
    _as_private: ec.EllipticCurvePrivateKey | None = None,
    _salt: bytes | None = None,
) -> bytes:
    """Encrypt ``payload`` for a push subscription → the aes128gcm body.

    ``p256dh`` is the subscription's 65-byte uncompressed public point and
    ``auth`` its 16-byte auth secret. The ``_as_private`` / ``_salt`` hooks
    exist only to make the output deterministic under test.
    """
    as_private = _as_private or ec.generate_private_key(ec.SECP256R1())
    as_public = _point(as_private.public_key())
    salt = _salt or os.urandom(16)

    ua_public = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), p256dh
    )
    ecdh_secret = as_private.exchange(ec.ECDH(), ua_public)

    key_info = b"WebPush: info\x00" + p256dh + as_public
    ikm = _hkdf(auth, ecdh_secret, key_info, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)

    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    header = (
        salt
        + struct.pack("!I", _RECORD_SIZE)
        + bytes([len(as_public)])
        + as_public
    )
    return header + ciphertext


def generate_vapid_keys() -> tuple[str, str]:
    """Return ``(private_b64url, public_b64url)`` — a fresh VAPID keypair.

    The private key is the raw 32-byte P-256 scalar; the public key is the
    65-byte uncompressed point. Matches ``web-push generate-vapid-keys``.
    """
    priv = ec.generate_private_key(ec.SECP256R1())
    scalar = priv.private_numbers().private_value.to_bytes(32, "big")
    return b64url_encode(scalar), b64url_encode(_point(priv.public_key()))


def vapid_authorization(
    endpoint: str, *, private_key_b64: str, public_key_b64: str, subject: str
) -> str:
    """Build the RFC 8292 ``Authorization: vapid t=<jwt>, k=<pubkey>`` value."""
    parsed = urlparse(endpoint)
    claims = {
        "aud": f"{parsed.scheme}://{parsed.netloc}",
        "exp": int(time.time()) + 12 * 3600,
        "sub": subject,
    }
    priv = ec.derive_private_key(
        int.from_bytes(b64url_decode(private_key_b64), "big"), ec.SECP256R1()
    )
    token = jwt.encode(claims, priv, algorithm="ES256")
    return f"vapid t={token}, k={public_key_b64}"


async def send_web_push(
    subscription: dict,
    payload: bytes,
    *,
    vapid_private_key: str,
    vapid_public_key: str,
    vapid_subject: str,
    ttl: int = 2419200,
) -> int:
    """POST an encrypted push to ``subscription['endpoint']`` → status code.

    ``subscription`` is the browser ``PushSubscription`` JSON:
    ``{"endpoint": ..., "keys": {"p256dh": ..., "auth": ...}}``.
    """
    import httpx

    endpoint = subscription["endpoint"]
    keys = subscription["keys"]
    body = encrypt_payload(
        payload,
        p256dh=b64url_decode(keys["p256dh"]),
        auth=b64url_decode(keys["auth"]),
    )
    authorization = vapid_authorization(
        endpoint,
        private_key_b64=vapid_private_key,
        public_key_b64=vapid_public_key,
        subject=vapid_subject,
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            endpoint,
            content=body,
            headers={
                "Content-Encoding": "aes128gcm",
                "Content-Type": "application/octet-stream",
                "TTL": str(ttl),
                "Authorization": authorization,
            },
        )
    return resp.status_code


__all__ = [
    "b64url_decode",
    "b64url_encode",
    "encrypt_payload",
    "generate_vapid_keys",
    "send_web_push",
    "vapid_authorization",
]
