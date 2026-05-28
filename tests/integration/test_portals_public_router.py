"""Integration tests for the public Help Center surface.

Anchors:
  reference/chatwoot/app/controllers/public/api/v1/portals_controller.rb
  reference/chatwoot/app/controllers/public/api/v1/portals/articles_controller.rb
  reference/chatwoot/app/controllers/public/api/v1/portals/categories_controller.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
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


async def _seed_admin_and_portal(
    db_session,
    client: AsyncClient,
    suffix: str,
    portal_slug: str = "hc-public",
) -> tuple[Any, dict, str]:
    """Returns (owner, admin_headers, portal_slug)."""
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@hcpub.example.com",
            account_name=f"HCPub{suffix}",
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
    admin_headers = headers.as_response_headers()

    await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json={
            "portal": {
                "name": "Public Help",
                "slug": portal_slug,
                "color": "#aabbcc",
            }
        },
        headers=admin_headers,
    )
    return owner, admin_headers, portal_slug


# ---------------------------------------------------------------------------
# Portal show
# ---------------------------------------------------------------------------
async def test_show_portal_public_no_auth(client, db_session):
    owner, headers, slug = await _seed_admin_and_portal(
        db_session, client, "-sh"
    )
    resp = await client.get(f"/hc/{slug}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == slug
    assert body["name"] == "Public Help"


async def test_show_portal_returns_404_for_unknown_slug(client):
    resp = await client.get("/hc/no-such-portal")
    assert resp.status_code == 404


async def test_show_portal_404_when_archived(client, db_session):
    """Archived portals 404 on the public surface (Rails'
    ``find_by!(archived: false)`` semantics)."""
    owner, headers, slug = await _seed_admin_and_portal(
        db_session, client, "-arc", portal_slug="archived-portal"
    )
    # Archive it via the admin endpoint.
    await client.patch(
        f"/api/v1/accounts/{owner.account.id}/portals/{slug}",
        json={"portal": {"archived": True}},
        headers=headers,
    )
    resp = await client.get(f"/hc/{slug}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------
async def test_articles_index_returns_only_published(client, db_session):
    owner, headers, slug = await _seed_admin_and_portal(
        db_session, client, "-ar", portal_slug="ar-portal"
    )
    base = f"/api/v1/accounts/{owner.account.id}/portals/{slug}/articles"
    # Two drafts + two published.
    for i, status in enumerate(
        ["draft", "published", "draft", "published"]
    ):
        await client.post(
            base,
            json={
                "article": {
                    "title": f"Article {i}",
                    "slug": f"ar-art-{i}",
                    "content": "...",
                    "status": status,
                }
            },
            headers=headers,
        )

    resp = await client.get(f"/hc/{slug}/articles")
    assert resp.status_code == 200
    rows = resp.json()
    # Only the two published articles surface.
    assert len(rows) == 2
    for r in rows:
        assert r["status"] == "published"


async def test_articles_filters_by_locale(client, db_session):
    owner, headers, slug = await _seed_admin_and_portal(
        db_session, client, "-lc", portal_slug="lc-portal"
    )
    base = f"/api/v1/accounts/{owner.account.id}/portals/{slug}/articles"
    await client.post(
        base,
        json={
            "article": {
                "title": "EN",
                "slug": "lc-en",
                "status": "published",
                "locale": "en",
            }
        },
        headers=headers,
    )
    await client.post(
        base,
        json={
            "article": {
                "title": "ES",
                "slug": "lc-es",
                "status": "published",
                "locale": "es",
            }
        },
        headers=headers,
    )
    en = (await client.get(f"/hc/{slug}/articles?locale=en")).json()
    es = (await client.get(f"/hc/{slug}/articles?locale=es")).json()
    assert [a["slug"] for a in en] == ["lc-en"]
    assert [a["slug"] for a in es] == ["lc-es"]


async def test_articles_filters_by_category_slug(client, db_session):
    owner, headers, slug = await _seed_admin_and_portal(
        db_session, client, "-cs", portal_slug="cs-portal"
    )
    # Create two categories.
    cat_a = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/portals/{slug}/categories",
            json={"category": {"name": "Setup", "slug": "setup"}},
            headers=headers,
        )
    ).json()
    cat_b = (
        await client.post(
            f"/api/v1/accounts/{owner.account.id}/portals/{slug}/categories",
            json={"category": {"name": "Billing", "slug": "billing-cs"}},
            headers=headers,
        )
    ).json()
    # One article per category.
    base = f"/api/v1/accounts/{owner.account.id}/portals/{slug}/articles"
    await client.post(
        base,
        json={
            "article": {
                "title": "Install",
                "slug": "cs-install",
                "status": "published",
                "category_id": cat_a["id"],
            }
        },
        headers=headers,
    )
    await client.post(
        base,
        json={
            "article": {
                "title": "Refund",
                "slug": "cs-refund",
                "status": "published",
                "category_id": cat_b["id"],
            }
        },
        headers=headers,
    )

    resp = await client.get(
        f"/hc/{slug}/articles?category_slug=setup"
    )
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["slug"] == "cs-install"


# ---------------------------------------------------------------------------
# Article show
# ---------------------------------------------------------------------------
async def test_article_show_returns_published(client, db_session):
    owner, headers, slug = await _seed_admin_and_portal(
        db_session, client, "-as", portal_slug="as-portal"
    )
    base = f"/api/v1/accounts/{owner.account.id}/portals/{slug}/articles"
    await client.post(
        base,
        json={
            "article": {
                "title": "How to install",
                "slug": "how-to-install",
                "content": "# Install\n\nRun the binary.",
                "status": "published",
            }
        },
        headers=headers,
    )
    resp = await client.get(f"/hc/{slug}/articles/how-to-install")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "how-to-install"
    assert body["status"] == "published"
    assert body["content"].startswith("# Install")


async def test_article_show_404_when_draft(client, db_session):
    owner, headers, slug = await _seed_admin_and_portal(
        db_session, client, "-ad", portal_slug="ad-portal"
    )
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals/{slug}/articles",
        json={
            "article": {
                "title": "Draft only",
                "slug": "draft-only",
                "status": "draft",
            }
        },
        headers=headers,
    )
    resp = await client.get(f"/hc/{slug}/articles/draft-only")
    assert resp.status_code == 404


async def test_article_show_404_when_unknown_slug(client, db_session):
    owner, headers, slug = await _seed_admin_and_portal(
        db_session, client, "-an", portal_slug="an-portal"
    )
    resp = await client.get(f"/hc/{slug}/articles/no-such-article")
    assert resp.status_code == 404


async def test_article_show_locale_filter_misses(client, db_session):
    """``?locale=`` scopes the lookup — a locale mismatch 404s even if
    the slug exists in another locale. (NOTE: the DB has a global slug
    uniqueness, so we can't test the multi-locale case Chatwoot supports;
    we test the filter direction that *does* exist.)"""
    owner, headers, slug = await _seed_admin_and_portal(
        db_session, client, "-al", portal_slug="al-portal"
    )
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals/{slug}/articles",
        json={
            "article": {
                "title": "Welcome",
                "slug": "welcome-en",
                "status": "published",
                "locale": "en",
            }
        },
        headers=headers,
    )
    hit = await client.get(f"/hc/{slug}/articles/welcome-en?locale=en")
    miss = await client.get(f"/hc/{slug}/articles/welcome-en?locale=es")
    assert hit.status_code == 200
    assert hit.json()["title"] == "Welcome"
    assert miss.status_code == 404


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
async def test_categories_index_returns_all(client, db_session):
    owner, headers, slug = await _seed_admin_and_portal(
        db_session, client, "-cat", portal_slug="cat-portal"
    )
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals/{slug}/categories",
        json={"category": {"name": "Getting Started", "slug": "gs-cat"}},
        headers=headers,
    )
    resp = await client.get(f"/hc/{slug}/categories")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["slug"] == "gs-cat"


async def test_categories_404_when_portal_archived(client, db_session):
    owner, headers, slug = await _seed_admin_and_portal(
        db_session, client, "-ac", portal_slug="ac-portal"
    )
    await client.patch(
        f"/api/v1/accounts/{owner.account.id}/portals/{slug}",
        json={"portal": {"archived": True}},
        headers=headers,
    )
    resp = await client.get(f"/hc/{slug}/categories")
    assert resp.status_code == 404


# Import-time-only — pull Any in.
from typing import Any  # noqa: E402
