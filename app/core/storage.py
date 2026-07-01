"""S3 / MinIO pre-signed URL helper — dependency-free SigV4.

Chatwoot leans on ActiveStorage's direct-upload flow (the browser PUTs
straight to S3 with a pre-signed URL, then references the blob). We don't
ship ActiveStorage, and rather than pull in boto3/aioboto3 just for URL
signing we hand-roll the AWS Signature V4 *query-string* variant with the
standard library (``hmac`` + ``hashlib``). That's all a pre-signed URL is:
a deterministic HMAC chain over a canonical request.

The signed URL lets a client (the dashboard composer) upload an attachment
directly to the object store without the bytes ever transiting our API;
the resulting :func:`object_url` is what we persist as the attachment's
``external_url``.

Path-style addressing (``<endpoint>/<bucket>/<key>``) so it works against
MinIO out of the box; ``s3_*`` settings drive the credentials + region.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from urllib.parse import quote, urlparse

from app.core.config import get_settings

_SERVICE = "s3"
_ALGORITHM = "AWS4-HMAC-SHA256"
# Pre-signed uploads carry no signed body — S3 accepts UNSIGNED-PAYLOAD for
# the query-string auth variant.
_UNSIGNED_PAYLOAD = "UNSIGNED-PAYLOAD"


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, date_stamp: str, region: str) -> bytes:
    k_date = _hmac(("AWS4" + secret).encode("utf-8"), date_stamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, _SERVICE)
    return _hmac(k_service, "aws4_request")


def _canonical_uri(bucket: str, key: str) -> str:
    """Path-style canonical URI: ``/<bucket>[/<key>]``.

    The key is URI-encoded but ``/`` is preserved so nested prefixes
    (``accounts/2/uploads/…``) stay intact. An empty key targets the
    bucket itself (used for bucket creation)."""
    uri = "/" + quote(bucket, safe="")
    if key:
        uri += "/" + quote(key, safe="/")
    return uri


def presigned_put_url(
    key: str,
    *,
    expires: int = 900,
    method: str = "PUT",
    now: datetime | None = None,
) -> str:
    """Return a pre-signed URL a client can use to ``method`` (default
    PUT) an object at ``key`` directly on the object store.

    ``expires`` is the validity window in seconds (default 15 min).
    ``now`` is injectable for deterministic tests.
    """
    settings = get_settings()
    parsed = urlparse(settings.s3_endpoint_url.rstrip("/"))
    host = parsed.netloc
    scheme = parsed.scheme
    region = settings.s3_region
    access_key = settings.s3_access_key
    secret_key = settings.s3_secret_key
    bucket = settings.s3_bucket

    now = now or datetime.now(UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    canonical_uri = _canonical_uri(bucket, key)
    credential = f"{access_key}/{date_stamp}/{region}/{_SERVICE}/aws4_request"
    query_params = {
        "X-Amz-Algorithm": _ALGORITHM,
        "X-Amz-Credential": credential,
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(expires),
        "X-Amz-SignedHeaders": "host",
    }
    canonical_query = "&".join(
        f"{quote(k, safe='')}={quote(v, safe='')}"
        for k, v in sorted(query_params.items())
    )
    canonical_headers = f"host:{host}\n"
    signed_headers = "host"
    canonical_request = "\n".join(
        [
            method,
            canonical_uri,
            canonical_query,
            canonical_headers,
            signed_headers,
            _UNSIGNED_PAYLOAD,
        ]
    )

    scope = f"{date_stamp}/{region}/{_SERVICE}/aws4_request"
    string_to_sign = "\n".join(
        [
            _ALGORITHM,
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signature = hmac.new(
        _signing_key(secret_key, date_stamp, region),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return (
        f"{scheme}://{host}{canonical_uri}"
        f"?{canonical_query}&X-Amz-Signature={signature}"
    )


def object_url(key: str) -> str:
    """The stable object URL persisted as an attachment's ``external_url``.

    Not pre-signed — reading is governed by the bucket/object policy (for
    a private bucket the dashboard fetches a pre-signed GET the same way it
    uploads). We keep the raw path-style URL so the value round-trips
    regardless of how reads are gated in a given deployment.
    """
    settings = get_settings()
    endpoint = settings.s3_endpoint_url.rstrip("/")
    return f"{endpoint}{_canonical_uri(settings.s3_bucket, key)}"


def signed_read_url(stored_url: str, *, expires: int = 3600) -> str:
    """Pre-sign a GET for a stored object URL so a *private* bucket's
    attachment still renders in the browser.

    URLs that don't point at our own bucket (external embeds, legacy direct
    links, or a non-configured store) pass through unchanged — so existing
    non-store ``external_url`` values are unaffected.
    """
    from urllib.parse import unquote

    marker = object_url("") + "/"
    if not stored_url.startswith(marker):
        return stored_url
    key = unquote(stored_url[len(marker) :])
    return presigned_put_url(key, method="GET", expires=expires)


__all__ = ["object_url", "presigned_put_url", "signed_read_url"]
