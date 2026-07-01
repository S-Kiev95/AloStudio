"""Integration tests for attachment uploads.

Two layers:
  * ``test_upload_endpoint_*`` — the ``POST /uploads`` surface returns a
    well-formed pre-signed PUT URL namespaced under the account.
  * ``test_presigned_put_roundtrip_live`` — the *definitive* check: a real
    PUT to MinIO with the signed URL. A 200 there proves the SigV4
    signature is correct (MinIO answers 403 SignatureDoesNotMatch on a bad
    one). Skips when MinIO isn't reachable so the suite stays green without
    it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.core.storage import object_url, presigned_put_url
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[get_session] = _override
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


async def _seeded(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@up.example.com",
            account_name="Up Inc",
            user_full_name="Up Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    await db_session.flush()
    return owner, headers.as_response_headers()


async def test_upload_endpoint_returns_presigned_url(client, db_session):
    owner, hdrs = await _seeded(db_session)
    acc = owner.account.id

    resp = await client.post(
        f"/api/v1/accounts/{acc}/uploads",
        json={"filename": "my report.pdf", "content_type": "application/pdf"},
        headers=hdrs,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Key is namespaced under the account + carries the sanitised filename.
    assert body["key"].startswith(f"accounts/{acc}/uploads/")
    assert body["key"].endswith("my-report.pdf")
    # The upload URL is a SigV4 pre-signed URL.
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in body["upload_url"]
    assert "X-Amz-Signature=" in body["upload_url"]
    assert body["expires_in"] == 900
    assert body["file_url"] == object_url(body["key"])


async def test_upload_endpoint_requires_auth(client, db_session):
    owner, _ = await _seeded(db_session)
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/uploads",
        json={"filename": "x.png"},
    )
    assert resp.status_code == 401, resp.text


async def test_presigned_put_roundtrip_live():
    """PUT a real object to MinIO with a signed URL — proves the signature."""
    settings = get_settings()
    endpoint = settings.s3_endpoint_url.rstrip("/")

    # Skip cleanly when MinIO isn't up (keeps the suite green without it).
    try:
        async with httpx.AsyncClient(timeout=3.0) as probe:
            health = await probe.get(f"{endpoint}/minio/health/live")
        if health.status_code >= 500:
            pytest.skip("MinIO not healthy")
    except (httpx.HTTPError, OSError):
        pytest.skip("MinIO not reachable")

    async with httpx.AsyncClient(timeout=10.0) as http:
        # Ensure the bucket exists (idempotent — 200 created / 409 exists).
        bucket_resp = await http.put(presigned_put_url(""))
        assert bucket_resp.status_code in (200, 409), bucket_resp.text

        key = f"test-uploads/{uuid4().hex}.txt"
        put_resp = await http.put(
            presigned_put_url(key), content=b"hola desde el test"
        )
        assert put_resp.status_code == 200, put_resp.text
