"""Integration tests for the product catalogue (I.11) + post linking.

Covers:
  * product CRUD (service + endpoints, admin-gated writes),
  * linking a post/story to products (`set_post_products`, `product_ids`
    on create),
  * the AI-context resolvers (`products_for_post`, `products_for_media`),
  * cascade behaviour on post / product delete.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.contacts import models as _contacts  # noqa: F401  (mapper)
from app.domains.conversations import models as _conversations  # noqa: F401
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram import publishing_service as ig_svc
from app.domains.products import service as psvc
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.domains.users.models import ACCOUNT_USER_ROLE_AGENT, AccountUser
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


async def _seed_admin(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@prod.example.com",
            account_name=f"PROD{suffix}",
            user_full_name=f"Admin{suffix}",
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


async def _seed_ig_post(db_session, owner, suffix, *, ig_media_id=None):
    inbox_res = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"IG{suffix}",
            channel_type="instagram",
            channel_params={
                "instagram_id": f"ig-p-{suffix}",
                "access_token": "PAGE-TOKEN",
            },
        ),
    ).perform()
    post = await ig_svc.create_post(
        db_session,
        account_id=owner.account.id,
        inbox_id=inbox_res.inbox.id,
        channel_instagram_id=inbox_res.channel.id,
        media_type="IMAGE",
        source={"image_url": "https://x.example.com/p.jpg"},
    )
    if ig_media_id:
        post.state = "published"
        post.ig_media_id = ig_media_id
        db_session.add(post)
        await db_session.flush()
    return post


# ---------------------------------------------------------------------------
# Service — product CRUD
# ---------------------------------------------------------------------------
async def test_product_crud_service(db_session):
    owner, _ = await _seed_admin(db_session, "-crud")
    p = await psvc.create_product(
        db_session,
        account_id=owner.account.id,
        payload={"name": "Zapatillas", "price": 99.9, "currency": "USD"},
    )
    assert p.id is not None
    assert p.name == "Zapatillas"

    got = await psvc.get_product(
        db_session, account_id=owner.account.id, product_id=p.id
    )
    assert got is not None

    updated = await psvc.update_product(
        db_session, product=got, payload={"name": "Zapatillas Pro"}
    )
    assert updated.name == "Zapatillas Pro"

    rows = await psvc.list_products(db_session, account_id=owner.account.id)
    assert any(r.id == p.id for r in rows)

    await psvc.delete_product(db_session, product=updated)
    assert (
        await psvc.get_product(
            db_session, account_id=owner.account.id, product_id=p.id
        )
        is None
    )


async def test_product_create_requires_name(db_session):
    owner, _ = await _seed_admin(db_session, "-noname")
    with pytest.raises(ChatwootHTTPException) as exc:
        await psvc.create_product(
            db_session, account_id=owner.account.id, payload={"name": "  "}
        )
    assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# Service — post ↔ product linking + resolvers
# ---------------------------------------------------------------------------
async def test_set_post_products_links_and_validates(db_session):
    owner, _ = await _seed_admin(db_session, "-link")
    p1 = await psvc.create_product(
        db_session, account_id=owner.account.id, payload={"name": "A"}
    )
    p2 = await psvc.create_product(
        db_session, account_id=owner.account.id, payload={"name": "B"}
    )
    post = await _seed_ig_post(db_session, owner, "-link")

    await ig_svc.set_post_products(
        db_session,
        account_id=owner.account.id,
        post=post,
        product_ids=[p1.id, p2.id],
    )
    linked = await ig_svc.products_for_post(db_session, post_id=post.id)
    assert {p.id for p in linked} == {p1.id, p2.id}

    # Replace (idempotent update) — only p2 remains.
    await ig_svc.set_post_products(
        db_session,
        account_id=owner.account.id,
        post=post,
        product_ids=[p2.id],
    )
    linked = await ig_svc.products_for_post(db_session, post_id=post.id)
    assert {p.id for p in linked} == {p2.id}


async def test_set_post_products_rejects_foreign_id(db_session):
    owner, _ = await _seed_admin(db_session, "-foreign")
    other, _ = await _seed_admin(db_session, "-foreign2")
    foreign = await psvc.create_product(
        db_session, account_id=other.account.id, payload={"name": "X"}
    )
    post = await _seed_ig_post(db_session, owner, "-foreign")
    with pytest.raises(ChatwootHTTPException) as exc:
        await ig_svc.set_post_products(
            db_session,
            account_id=owner.account.id,
            post=post,
            product_ids=[foreign.id],
        )
    assert exc.value.status_code == 422


async def test_products_for_media_resolver(db_session):
    owner, _ = await _seed_admin(db_session, "-media")
    p = await psvc.create_product(
        db_session, account_id=owner.account.id, payload={"name": "Curso"}
    )
    post = await _seed_ig_post(
        db_session, owner, "-media", ig_media_id="MEDIA_X"
    )
    await ig_svc.set_post_products(
        db_session,
        account_id=owner.account.id,
        post=post,
        product_ids=[p.id],
    )
    found = await ig_svc.products_for_media(
        db_session, account_id=owner.account.id, ig_media_id="MEDIA_X"
    )
    assert [x.id for x in found] == [p.id]
    # Unknown media → empty.
    assert (
        await ig_svc.products_for_media(
            db_session, account_id=owner.account.id, ig_media_id="NOPE"
        )
        == []
    )


async def test_cascade_on_post_delete(db_session):
    owner, _ = await _seed_admin(db_session, "-cascpost")
    p = await psvc.create_product(
        db_session, account_id=owner.account.id, payload={"name": "C"}
    )
    post = await _seed_ig_post(db_session, owner, "-cascpost")
    await ig_svc.set_post_products(
        db_session,
        account_id=owner.account.id,
        post=post,
        product_ids=[p.id],
    )
    post_id = post.id
    await db_session.delete(post)
    await db_session.flush()
    # Join rows cascaded; product survives.
    assert await ig_svc.products_for_post(db_session, post_id=post_id) == []
    assert (
        await psvc.get_product(
            db_session, account_id=owner.account.id, product_id=p.id
        )
        is not None
    )


async def test_cascade_on_product_delete(db_session):
    owner, _ = await _seed_admin(db_session, "-cascprod")
    p = await psvc.create_product(
        db_session, account_id=owner.account.id, payload={"name": "D"}
    )
    post = await _seed_ig_post(db_session, owner, "-cascprod")
    await ig_svc.set_post_products(
        db_session,
        account_id=owner.account.id,
        post=post,
        product_ids=[p.id],
    )
    await psvc.delete_product(db_session, product=p)
    # Join row cascaded; post survives with no products.
    assert await ig_svc.products_for_post(db_session, post_id=post.id) == []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
async def test_products_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/products")
    assert resp.status_code == 401


async def test_product_crud_endpoints(client, db_session):
    owner, headers = await _seed_admin(db_session, "-ep")
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/products",
        json={"name": "Plan Pro", "price": 19.99, "currency": "USD"},
        headers=headers,
    )
    assert create.status_code == 200, create.text
    pid = create.json()["id"]
    assert create.json()["price"] == 19.99

    index = await client.get(
        f"/api/v1/accounts/{owner.account.id}/products", headers=headers
    )
    assert index.status_code == 200
    assert any(p["id"] == pid for p in index.json())

    patch = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/products/{pid}",
        json={"enabled": False},
        headers=headers,
    )
    assert patch.status_code == 200
    assert patch.json()["enabled"] is False

    delete = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/products/{pid}", headers=headers
    )
    assert delete.status_code == 200


async def test_product_create_blocked_for_agent(client, db_session):
    owner, _ = await _seed_admin(db_session, "-agent")
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email="agent-prod@prod.example.com",
            account_name="Other",
            user_full_name="Agent",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner.account.id,
            user_id=agent.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    await db_session.flush()
    ah, new_tokens = create_new_auth_token(
        user_tokens=agent.user.tokens, uid=agent.user.uid
    )
    agent.user.tokens = new_tokens
    db_session.add(agent.user)
    await db_session.flush()
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/products",
        json={"name": "X"},
        headers=ah.as_response_headers(),
    )
    assert resp.status_code == 401


async def test_create_post_with_product_ids_endpoint(client, db_session):
    owner, headers = await _seed_admin(db_session, "-postlink")
    inbox_res = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="IG-postlink",
            channel_type="instagram",
            channel_params={
                "instagram_id": "ig-postlink",
                "access_token": "PAGE-TOKEN",
            },
        ),
    ).perform()
    p = await psvc.create_product(
        db_session, account_id=owner.account.id, payload={"name": "Mochila"}
    )
    from datetime import UTC, datetime, timedelta

    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts",
        json={
            "inbox_id": inbox_res.inbox.id,
            "media_type": "IMAGE",
            "source": {"image_url": "https://x.example.com/p.jpg"},
            "scheduled_for": future,
            "product_ids": [p.id],
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [pr["id"] for pr in body["products"]] == [p.id]
    post_id = body["id"]

    # Dedicated products endpoint reflects the link.
    got = await client.get(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts/{post_id}/products",
        headers=headers,
    )
    assert got.status_code == 200
    assert [pr["id"] for pr in got.json()] == [p.id]


async def test_create_post_with_unknown_product_id_422(client, db_session):
    owner, headers = await _seed_admin(db_session, "-badlink")
    inbox_res = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name="IG-badlink",
            channel_type="instagram",
            channel_params={
                "instagram_id": "ig-badlink",
                "access_token": "PAGE-TOKEN",
            },
        ),
    ).perform()
    from datetime import UTC, datetime, timedelta

    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts",
        json={
            "inbox_id": inbox_res.inbox.id,
            "media_type": "IMAGE",
            "source": {"image_url": "https://x.example.com/p.jpg"},
            "scheduled_for": future,
            "product_ids": [99999999],
        },
        headers=headers,
    )
    assert resp.status_code == 422
