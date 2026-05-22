"""End-to-end scenario for the Instagram extension (I.12).

One flow exercising the whole surface together: connect a channel →
create a product → create a post linked to it → publish (Meta mocked) →
comment → hide → delete. Proves the milestones compose.

Publishing is driven at the service level (the immediate-publish REST
path enqueues onto the worker's separate engine, which can't see the
test session) — everything else goes through the REST API.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.instagram import publishing_service as ig_svc
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration

GRAPH = "https://graph.facebook.com/v23.0"
IGID = "17841700000000001"


async def _instant_sleep(_seconds: float) -> None:
    return None


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


async def _seed_admin(db_session):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="admin@ige2e.example.com",
            account_name="IGE2E",
            user_full_name="Admin",
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


@respx.mock
async def test_full_instagram_lifecycle(client, db_session):
    owner, headers = await _seed_admin(db_session)
    acc = owner.account.id

    # 1) Connect a channel (manual, Facebook Login → delete enabled).
    connect = await client.post(
        f"/api/v1/accounts/{acc}/instagram_channels/connect_manual",
        json={
            "name": "Tienda IG",
            "instagram_id": IGID,
            "access_token": "PERMA_TOKEN",
            "login_type": "facebook",
        },
        headers=headers,
    )
    assert connect.status_code == 200, connect.text
    inbox_id = connect.json()["inbox_id"]

    # 2) Create a product.
    prod = await client.post(
        f"/api/v1/accounts/{acc}/products",
        json={"name": "Zapatillas Runner", "price": 79.99, "currency": "USD"},
        headers=headers,
    )
    assert prod.status_code == 200, prod.text
    product_id = prod.json()["id"]

    # 3) Create a (scheduled) post linked to the product.
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    create = await client.post(
        f"/api/v1/accounts/{acc}/instagram_posts",
        json={
            "inbox_id": inbox_id,
            "media_type": "IMAGE",
            "source": {"image_url": "https://cdn.example.com/shoe.jpg"},
            "caption": "Nuevo drop",
            "scheduled_for": future,
            "product_ids": [product_id],
        },
        headers=headers,
    )
    assert create.status_code == 200, create.text
    post_id = create.json()["id"]
    assert create.json()["state"] == "pending"
    assert [p["id"] for p in create.json()["products"]] == [product_id]

    # 4) Publish (Meta mocked) at the service level.
    respx.post(f"{GRAPH}/{IGID}/media").mock(
        return_value=httpx.Response(200, json={"id": "C1"})
    )
    respx.get(f"{GRAPH}/C1").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.post(f"{GRAPH}/{IGID}/media_publish").mock(
        return_value=httpx.Response(200, json={"id": "MID9"})
    )
    respx.get(f"{GRAPH}/MID9").mock(
        return_value=httpx.Response(
            200, json={"permalink": "https://www.instagram.com/p/e2e/"}
        )
    )
    published = await ig_svc.publish_post(
        db_session, post_id=post_id, sleep_fn=_instant_sleep
    )
    assert published.state == "published"
    assert published.ig_media_id == "MID9"

    # 5) Show the post — published, with media id + linked product.
    show = await client.get(
        f"/api/v1/accounts/{acc}/instagram_posts/{post_id}", headers=headers
    )
    assert show.status_code == 200
    assert show.json()["state"] == "published"
    assert show.json()["ig_media_id"] == "MID9"
    assert [p["id"] for p in show.json()["products"]] == [product_id]

    # 6) Resolver: media → product (AI context).
    linked = await ig_svc.products_for_media(
        db_session, account_id=acc, ig_media_id="MID9"
    )
    assert [p.id for p in linked] == [product_id]

    # 7) Comment on the published media.
    respx.post(f"{GRAPH}/MID9/comments").mock(
        return_value=httpx.Response(200, json={"id": "CMT1"})
    )
    comment = await client.post(
        f"/api/v1/accounts/{acc}/instagram_posts/{post_id}/comments",
        json={"message": "En stock!"},
        headers=headers,
    )
    assert comment.status_code == 200, comment.text
    comment_id = comment.json()["id"]

    # 8) Hide the comment (moderation).
    respx.post(f"{GRAPH}/CMT1").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    hide = await client.post(
        f"/api/v1/accounts/{acc}/instagram_comments/{comment_id}/hide",
        json={"hide": True},
        headers=headers,
    )
    assert hide.status_code == 200
    assert hide.json()["hidden"] is True

    # 9) Delete the published post (Facebook Login → allowed).
    respx.delete(f"{GRAPH}/MID9").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    delete = await client.delete(
        f"/api/v1/accounts/{acc}/instagram_posts/{post_id}", headers=headers
    )
    assert delete.status_code == 200
    assert delete.json()["state"] == "deleted"
