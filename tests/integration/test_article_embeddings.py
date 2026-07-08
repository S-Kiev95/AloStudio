"""Integration tests for Help-Center embedding search.

Covers the Captain-style port:

  * ``reindex_article`` — gpt-4o term expansion + per-term embeddings,
    replacing any prior rows (OpenAI mocked via respx).
  * ``vector_search`` — cosine nearest-neighbour over stored embeddings.
  * the public ``/hc/<slug>/articles?query=`` route: semantic when the
    key is set, ILIKE fallback when it isn't (or when OpenAI errors).

OpenAI HTTP is always mocked; the pgvector round-trip is real.

Anchors:
  reference/chatwoot/enterprise/app/models/enterprise/concerns/article.rb
  reference/chatwoot/enterprise/app/services/captain/llm/embedding_service.rb
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.db import get_session
from app.core.llm import EMBEDDING_DIM
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.portals.embeddings import (
    reindex_article,
    vector_search,
)
from app.domains.portals.models import (
    ARTICLE_STATUS_PUBLISHED,
    Article,
    ArticleEmbedding,
    Portal,
)
from app.domains.portals.service import create_article
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration

_EMBED_URL = "https://api.openai.com/v1/embeddings"
_CHAT_URL = "https://api.openai.com/v1/chat/completions"


# ---------------------------------------------------------------------------
# Deterministic fake OpenAI
# ---------------------------------------------------------------------------
def _unit(i: int) -> list[float]:
    v = [0.0] * EMBEDDING_DIM
    v[i] = 1.0
    return v


def _vector_for(text: str) -> list[float]:
    t = text.lower()
    if any(k in t for k in ("cat", "felin", "kitten", "gato")):
        return _unit(0)
    if any(k in t for k in ("dog", "perro", "puppy")):
        return _unit(1)
    return _unit(2)


def _embed_side_effect(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    return httpx.Response(
        200, json={"data": [{"embedding": _vector_for(str(body.get("input", "")))}]}
    )


def _chat_side_effect(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    user = str(body["messages"][1]["content"]).lower()
    if "cat" in user or "gato" in user:
        terms = ["cat care", "feline health"]
    elif "dog" in user or "perro" in user:
        terms = ["dog training"]
    else:
        terms = ["general help"]
    content = json.dumps({"search_terms": terms})
    return httpx.Response(
        200, json={"choices": [{"message": {"content": content}}]}
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def enable_embeddings() -> AsyncIterator[None]:
    s = get_settings()
    old_key, old_base = s.openai_api_key, s.openai_base_url
    s.openai_api_key = "sk-test"
    s.openai_base_url = "https://api.openai.com"
    try:
        yield
    finally:
        s.openai_api_key, s.openai_base_url = old_key, old_base


@pytest.fixture
def disable_embeddings() -> AsyncIterator[None]:
    s = get_settings()
    old_key = s.openai_api_key
    s.openai_api_key = ""
    try:
        yield
    finally:
        s.openai_api_key = old_key


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


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------
async def _seed_account(db_session, suffix: str):
    return await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@emb.example.com",
            account_name=f"Emb{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()


async def _seed_portal(db_session, owner, suffix: str) -> Portal:
    portal = Portal(
        account_id=owner.account.id, name="Help", slug=f"help{suffix}"
    )
    db_session.add(portal)
    await db_session.flush()
    await db_session.refresh(portal)
    return portal


async def _seed_article(
    db_session, owner, portal, *, title, content, slug, embed_dim=None
) -> Article:
    art = Article(
        account_id=owner.account.id,
        portal_id=portal.id,
        title=title,
        content=content,
        slug=slug,
        status=ARTICLE_STATUS_PUBLISHED,
        locale="en",
    )
    db_session.add(art)
    await db_session.flush()
    await db_session.refresh(art)
    if embed_dim is not None:
        db_session.add(
            ArticleEmbedding(
                article_id=art.id, term=title, embedding=_unit(embed_dim)
            )
        )
        await db_session.flush()
    return art


async def _embeddings_for(db_session, article_id) -> list[ArticleEmbedding]:
    from sqlmodel import select

    return list(
        (
            await db_session.exec(
                select(ArticleEmbedding).where(
                    ArticleEmbedding.article_id == article_id
                )
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# reindex_article
# ---------------------------------------------------------------------------
@respx.mock
async def test_reindex_creates_one_embedding_per_term(
    db_session, enable_embeddings
):
    respx.post(_CHAT_URL).mock(side_effect=_chat_side_effect)
    respx.post(_EMBED_URL).mock(side_effect=_embed_side_effect)
    owner = await _seed_account(db_session, "-rc")
    portal = await _seed_portal(db_session, owner, "-rc")
    art = await _seed_article(
        db_session, owner, portal, title="Cats", content="all about cats",
        slug="cats-rc",
    )

    written = await reindex_article(db_session, article_id=art.id)
    assert written == 2  # gpt-4o returned two cat terms

    rows = await _embeddings_for(db_session, art.id)
    assert {r.term for r in rows} == {"cat care", "feline health"}
    assert all(r.embedding is not None for r in rows)


@respx.mock
async def test_reindex_replaces_previous_embeddings(
    db_session, enable_embeddings
):
    respx.post(_CHAT_URL).mock(side_effect=_chat_side_effect)
    respx.post(_EMBED_URL).mock(side_effect=_embed_side_effect)
    owner = await _seed_account(db_session, "-rr")
    portal = await _seed_portal(db_session, owner, "-rr")
    art = await _seed_article(
        db_session, owner, portal, title="Dogs", content="about dogs",
        slug="dogs-rr", embed_dim=2,  # a stale pre-existing embedding
    )
    assert len(await _embeddings_for(db_session, art.id)) == 1

    await reindex_article(db_session, article_id=art.id)

    rows = await _embeddings_for(db_session, art.id)
    assert {r.term for r in rows} == {"dog training"}  # stale one gone


async def test_reindex_noop_when_disabled(db_session, disable_embeddings):
    owner = await _seed_account(db_session, "-nd")
    portal = await _seed_portal(db_session, owner, "-nd")
    art = await _seed_article(
        db_session, owner, portal, title="Cats", content="x", slug="cats-nd"
    )
    # No respx routes — a call to OpenAI would raise; the gate must short out.
    assert await reindex_article(db_session, article_id=art.id) == 0
    assert await _embeddings_for(db_session, art.id) == []


async def test_create_article_enqueues_reindex(
    db_session, monkeypatch, enable_embeddings
):
    calls: list[int] = []

    async def _spy(article_id: int) -> None:
        calls.append(article_id)

    monkeypatch.setattr(
        "app.domains.portals.service.enqueue_reindex_article", _spy
    )
    owner = await _seed_account(db_session, "-enq")
    portal = await _seed_portal(db_session, owner, "-enq")
    art = await create_article(
        db_session,
        account_id=owner.account.id,
        portal=portal,
        author_id=None,
        payload={"title": "Hola", "content": "contenido", "slug": "hola-enq"},
    )
    assert calls == [art.id]


# ---------------------------------------------------------------------------
# vector_search
# ---------------------------------------------------------------------------
@respx.mock
async def test_vector_search_ranks_nearest_first(db_session, enable_embeddings):
    respx.post(_EMBED_URL).mock(side_effect=_embed_side_effect)
    owner = await _seed_account(db_session, "-vs")
    portal = await _seed_portal(db_session, owner, "-vs")
    cat = await _seed_article(
        db_session, owner, portal, title="Cats", content="c", slug="cats-vs",
        embed_dim=0,
    )
    dog = await _seed_article(
        db_session, owner, portal, title="Dogs", content="d", slug="dogs-vs",
        embed_dim=1,
    )

    hits = await vector_search(
        db_session, portal_id=portal.id, query="kitten care"
    )
    # Both are neighbours (no distance threshold, mirroring Chatwoot); the
    # cat article must rank first for a cat query.
    assert hits[0].id == cat.id
    assert dog.id in [a.id for a in hits]


@respx.mock
async def test_vector_search_scopes_to_portal(db_session, enable_embeddings):
    respx.post(_EMBED_URL).mock(side_effect=_embed_side_effect)
    owner = await _seed_account(db_session, "-vp")
    portal_a = await _seed_portal(db_session, owner, "-vp-a")
    portal_b = await _seed_portal(db_session, owner, "-vp-b")
    await _seed_article(
        db_session, owner, portal_b, title="Cats", content="c",
        slug="cats-vp", embed_dim=0,
    )
    # Portal A has no cat article — a cat query returns nothing there.
    hits = await vector_search(
        db_session, portal_id=portal_a.id, query="kitten"
    )
    assert hits == []


# ---------------------------------------------------------------------------
# Public endpoint wiring
# ---------------------------------------------------------------------------
@respx.mock
async def test_public_search_is_semantic_when_enabled(
    client, db_session, enable_embeddings
):
    respx.post(_EMBED_URL).mock(side_effect=_embed_side_effect)
    owner = await _seed_account(db_session, "-ps")
    portal = await _seed_portal(db_session, owner, "-ps")
    await _seed_article(
        db_session, owner, portal, title="Cats", content="feline stuff",
        slug="cats-ps", embed_dim=0,
    )
    await _seed_article(
        db_session, owner, portal, title="Dogs", content="canine stuff",
        slug="dogs-ps", embed_dim=1,
    )

    # "kitten" matches no article via ILIKE, so a non-empty result proves
    # the semantic path ran; the cat article ranks first.
    resp = await client.get(f"/hc/{portal.slug}/articles?query=kitten")
    assert resp.status_code == 200, resp.text
    slugs = [a["slug"] for a in resp.json()]
    assert slugs and slugs[0] == "cats-ps"


@respx.mock
async def test_public_search_falls_back_to_ilike_on_llm_error(
    client, db_session, enable_embeddings
):
    # Embeddings endpoint errors → vector_search raises → ILIKE fallback.
    respx.post(_EMBED_URL).mock(return_value=httpx.Response(500))
    owner = await _seed_account(db_session, "-fb")
    portal = await _seed_portal(db_session, owner, "-fb")
    await _seed_article(
        db_session, owner, portal, title="Cats", content="feline stuff",
        slug="cats-fb", embed_dim=0,
    )

    # "Cats" DOES match ILIKE → the fallback returns it even though OpenAI died.
    resp = await client.get(f"/hc/{portal.slug}/articles?query=Cats")
    assert resp.status_code == 200, resp.text
    assert [a["slug"] for a in resp.json()] == ["cats-fb"]


async def test_public_search_uses_ilike_when_disabled(
    client, db_session, disable_embeddings
):
    owner = await _seed_account(db_session, "-di")
    portal = await _seed_portal(db_session, owner, "-di")
    await _seed_article(
        db_session, owner, portal, title="Cats", content="x", slug="cats-di"
    )
    # No respx — with the feature off, no OpenAI call may happen.
    resp = await client.get(f"/hc/{portal.slug}/articles?query=Cats")
    assert resp.status_code == 200, resp.text
    assert [a["slug"] for a in resp.json()] == ["cats-di"]
