"""Integration tests for Portal / Category / Article CRUD.

Anchors:
  reference/chatwoot/app/controllers/api/v1/accounts/portals_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/articles_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/categories_controller.rb
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
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
            email=f"admin{suffix}@hc.example.com",
            account_name=f"HC{suffix}",
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


async def _seed_agent_member(db_session, owner_account, suffix: str):
    agent = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"agent{suffix}@hc.example.com",
            account_name=f"Other{suffix}",
            user_full_name=f"Agent{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    db_session.add(
        AccountUser(
            account_id=owner_account.id,
            user_id=agent.user.id,
            role=ACCOUNT_USER_ROLE_AGENT,
        )
    )
    await db_session.flush()
    headers, new_tokens = create_new_auth_token(
        user_tokens=agent.user.tokens, uid=agent.user.uid
    )
    agent.user.tokens = new_tokens
    db_session.add(agent.user)
    await db_session.flush()
    return agent, headers.as_response_headers()


# ---------------------------------------------------------------------------
# Auth gates
# ---------------------------------------------------------------------------
async def test_portals_index_requires_auth(client):
    resp = await client.get("/api/v1/accounts/1/portals")
    assert resp.status_code == 401


async def test_portals_create_blocked_for_agent(client, db_session):
    owner, _ = await _seed_admin(db_session, "-ag")
    _agent, agent_headers = await _seed_agent_member(
        db_session, owner.account, "-ag"
    )
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json={"portal": {"name": "x", "slug": "x"}},
        headers=agent_headers,
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Portal CRUD
# ---------------------------------------------------------------------------
async def test_create_portal_happy_path(client, db_session):
    owner, headers = await _seed_admin(db_session, "-cp")
    body = {
        "portal": {
            "name": "Acme Help",
            "slug": "acme-help",
            "color": "#1f93ff",
            "page_title": "Acme Support",
        }
    }
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["slug"] == "acme-help"
    assert payload["name"] == "Acme Help"
    assert payload["archived"] is False


async def test_create_portal_rejects_duplicate_slug(client, db_session):
    owner, headers = await _seed_admin(db_session, "-dup")
    base = {"portal": {"name": "X", "slug": "dup-slug"}}
    r1 = await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json=base,
        headers=headers,
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json=base,
        headers=headers,
    )
    assert r2.status_code == 422


async def test_create_portal_rejects_blank_name(client, db_session):
    owner, headers = await _seed_admin(db_session, "-bn")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json={"portal": {"name": "", "slug": "anything"}},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_create_portal_rejects_invalid_slug(client, db_session):
    owner, headers = await _seed_admin(db_session, "-bs")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json={"portal": {"name": "X", "slug": "Has Spaces"}},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_update_portal(client, db_session):
    owner, headers = await _seed_admin(db_session, "-up")
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json={"portal": {"name": "Pre", "slug": "pre-slug"}},
        headers=headers,
    )
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/portals/pre-slug",
        json={"portal": {"name": "Post", "header_text": "Hi"}},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Post"
    assert resp.json()["header_text"] == "Hi"


async def test_destroy_portal(client, db_session):
    owner, headers = await _seed_admin(db_session, "-dl")
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json={"portal": {"name": "X", "slug": "del-slug"}},
        headers=headers,
    )
    resp = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/portals/del-slug",
        headers=headers,
    )
    assert resp.status_code == 200
    show = await client.get(
        f"/api/v1/accounts/{owner.account.id}/portals/del-slug",
        headers=headers,
    )
    assert show.status_code == 404


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------
async def test_category_crud(client, db_session):
    owner, headers = await _seed_admin(db_session, "-cc")
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json={"portal": {"name": "P", "slug": "p-slug"}},
        headers=headers,
    )
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals/p-slug/categories",
        json={
            "category": {
                "name": "Billing",
                "slug": "billing",
                "description": "Money things",
            }
        },
        headers=headers,
    )
    assert create.status_code == 200, create.text
    cid = create.json()["id"]

    listing = await client.get(
        f"/api/v1/accounts/{owner.account.id}/portals/p-slug/categories",
        headers=headers,
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    patch = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/portals/p-slug/categories/{cid}",
        json={"category": {"description": "Updated"}},
        headers=headers,
    )
    assert patch.status_code == 200
    assert patch.json()["description"] == "Updated"

    delete = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/portals/p-slug/categories/{cid}",
        headers=headers,
    )
    assert delete.status_code == 200


# ---------------------------------------------------------------------------
# Article CRUD
# ---------------------------------------------------------------------------
async def test_article_crud(client, db_session):
    owner, headers = await _seed_admin(db_session, "-ac")
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json={"portal": {"name": "P", "slug": "art-portal"}},
        headers=headers,
    )
    create = await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals/art-portal/articles",
        json={
            "article": {
                "title": "How to install",
                "slug": "how-to-install",
                "content": "Step 1...",
                "status": "draft",
            }
        },
        headers=headers,
    )
    assert create.status_code == 200, create.text
    aid = create.json()["id"]
    assert create.json()["status"] == "draft"
    assert create.json()["author_id"] == owner.user.id

    publish = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/portals/art-portal/articles/{aid}",
        json={"article": {"status": "published"}},
        headers=headers,
    )
    assert publish.status_code == 200
    assert publish.json()["status"] == "published"

    listing = await client.get(
        f"/api/v1/accounts/{owner.account.id}/portals/art-portal/articles"
        "?status=published",
        headers=headers,
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    delete = await client.delete(
        f"/api/v1/accounts/{owner.account.id}/portals/art-portal/articles/{aid}",
        headers=headers,
    )
    assert delete.status_code == 200


async def test_article_rejects_blank_title(client, db_session):
    owner, headers = await _seed_admin(db_session, "-at")
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json={"portal": {"name": "P", "slug": "at-portal"}},
        headers=headers,
    )
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals/at-portal/articles",
        json={"article": {"title": "", "slug": "x"}},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_article_slug_globally_unique(client, db_session):
    """Articles share a global UNIQUE on slug — two articles can't
    share a slug even across portals."""
    owner, headers = await _seed_admin(db_session, "-uq")
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json={"portal": {"name": "P", "slug": "p1-uq"}},
        headers=headers,
    )
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json={"portal": {"name": "Q", "slug": "p2-uq"}},
        headers=headers,
    )
    r1 = await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals/p1-uq/articles",
        json={
            "article": {"title": "Same", "slug": "same-slug-uq"}
        },
        headers=headers,
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals/p2-uq/articles",
        json={
            "article": {"title": "Same", "slug": "same-slug-uq"}
        },
        headers=headers,
    )
    assert r2.status_code == 422


async def test_article_index_search_by_query(client, db_session):
    """Dashboard ``GET .../articles?query=`` filters via ILIKE over
    title/description/content — and, unlike the public surface, keeps
    drafts in the results."""
    owner, headers = await _seed_admin(db_session, "-qsrch")
    await client.post(
        f"/api/v1/accounts/{owner.account.id}/portals",
        json={"portal": {"name": "Q", "slug": "qsrch-portal"}},
        headers=headers,
    )
    base = (
        f"/api/v1/accounts/{owner.account.id}/portals/qsrch-portal/articles"
    )
    await client.post(
        base,
        json={
            "article": {
                "title": "Refund policy",
                "slug": "qsrch-refund",
                "status": "draft",
            }
        },
        headers=headers,
    )
    await client.post(
        base,
        json={
            "article": {
                "title": "Onboarding guide",
                "slug": "qsrch-onboard",
                "content": "How to refund a charge is covered in billing.",
                "status": "published",
            }
        },
        headers=headers,
    )
    await client.post(
        base,
        json={
            "article": {
                "title": "Release notes",
                "slug": "qsrch-notes",
                "status": "published",
            }
        },
        headers=headers,
    )

    rows = (await client.get(f"{base}?query=refund", headers=headers)).json()
    # Draft (title match) + published (content match); the draft is kept.
    assert sorted(a["slug"] for a in rows) == ["qsrch-onboard", "qsrch-refund"]


async def test_portal_logo_set_update_and_clear(client, db_session):
    owner, headers = await _seed_admin(db_session, "-logo")
    base = f"/api/v1/accounts/{owner.account.id}/portals"

    created = await client.post(
        base,
        json={
            "portal": {
                "name": "Docs",
                "slug": "docs-logo",
                "logo": "https://cdn.example.com/logo.png",
            }
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    assert created.json()["logo"] == "https://cdn.example.com/logo.png"

    upd = await client.patch(
        f"{base}/docs-logo",
        json={"portal": {"logo": "https://cdn.example.com/new.png"}},
        headers=headers,
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["logo"] == "https://cdn.example.com/new.png"

    # Empty string clears the logo (stored as NULL).
    cleared = await client.patch(
        f"{base}/docs-logo",
        json={"portal": {"logo": ""}},
        headers=headers,
    )
    assert cleared.status_code == 200
    assert cleared.json()["logo"] is None
