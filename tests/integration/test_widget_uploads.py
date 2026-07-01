"""Integration tests for widget attachments.

  * ``POST /api/v1/widget/uploads`` — pre-signed direct-upload URL, gated
    on the widget's ``attachments`` feature flag.
  * ``POST /api/v1/widget/messages`` now accepts ``attachments`` so a
    visitor's uploaded file rides along on the message.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.models import WebWidget
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
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


async def _seed_widget(db_session, *, suffix: str, attachments: bool = True):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@wu.example.com",
            account_name=f"WU{suffix}",
            user_full_name="WU Admin",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="Widget",
            channel_type="web_widget",
            channel_params={"website_url": "https://example.com"},
        ),
    ).perform()
    ww = result.channel
    assert isinstance(ww, WebWidget)
    if not attachments:
        ww.feature_flags = 0  # disables every widget feature, incl. attachments
        db_session.add(ww)
        await db_session.flush()
        await db_session.refresh(ww)
    return owner, result.inbox, ww


async def _token(client, ww: WebWidget) -> str:
    resp = await client.post(
        f"/api/v1/widget/config?website_token={ww.website_token}"
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["auth_token"]


async def test_widget_upload_presigns_when_enabled(client, db_session):
    _, _, ww = await _seed_widget(db_session, suffix="-on")
    token = await _token(client, ww)

    resp = await client.post(
        f"/api/v1/widget/uploads?website_token={ww.website_token}",
        headers={"X-Auth-Token": token},
        json={"filename": "foto del visitante.png"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"].endswith("foto-del-visitante.png")
    assert "X-Amz-Signature=" in body["upload_url"]
    assert body["expires_in"] == 900


async def test_widget_upload_forbidden_when_disabled(client, db_session):
    _, _, ww = await _seed_widget(db_session, suffix="-off", attachments=False)
    token = await _token(client, ww)

    resp = await client.post(
        f"/api/v1/widget/uploads?website_token={ww.website_token}",
        headers={"X-Auth-Token": token},
        json={"filename": "x.png"},
    )
    assert resp.status_code == 403, resp.text


async def test_widget_message_accepts_attachment(client, db_session):
    _, _, ww = await _seed_widget(db_session, suffix="-msg")
    token = await _token(client, ww)

    resp = await client.post(
        f"/api/v1/widget/messages?website_token={ww.website_token}",
        headers={"X-Auth-Token": token},
        json={
            "message": {
                "content": "mirá esta captura",
                "attachments": [
                    {
                        "file_type": "image",
                        "external_url": "https://cdn.example.com/pic.png",
                    }
                ],
            }
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("content") == "mirá esta captura"
    atts = body.get("attachments") or []
    assert len(atts) == 1
    assert atts[0]["file_type"] == "image"
    # Non-store URL → signed_read_url passes it through unchanged.
    assert atts[0]["data_url"] == "https://cdn.example.com/pic.png"
