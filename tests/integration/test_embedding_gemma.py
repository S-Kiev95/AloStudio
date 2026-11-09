"""F9: the local embedding model (EmbeddingGemma 2) next to OpenAI.

What the migration promises, end to end against a real pgvector:

* every save writes both providers' vectors while both are configured;
* an account reads with one model, chosen per account, with that model's
  threshold — an OpenAI threshold is never read on the local scale;
* editing a rule on one scale leaves the other model's value untouched;
* shadow mode only logs, never changes the reply;
* the backfill fills in what is missing and nothing else;
* the Help Center indexes and searches with the local model.

The service is stubbed with one-hot vectors so distances are exact.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.config import get_settings
from app.core.db import get_session
from app.core.embeddings import GEMMA_DIM, READ_MODEL_KEY
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram import autoreply as autoreply_mod
from app.domains.instagram import autoreply_router as router_mod
from app.domains.instagram.autoreply import decide_reply
from app.domains.instagram.autoreply_models import (
    COMMENT_REPLY_EMBEDDING_DIM,
    InstagramCommentReply,
)
from app.domains.instagram.models import InstagramComment, InstagramPost
from app.domains.instagram.post_autoreply_models import InstagramPostAutoreply
from app.domains.portals import embeddings as portal_embeddings
from app.domains.portals.models import (
    ARTICLE_STATUS_PUBLISHED,
    Article,
    ArticleEmbedding,
    Portal,
)
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app
from app.workers import embeddings_backfill

pytestmark = pytest.mark.integration


def _gemma(slot: int, *, near: float = 0.0) -> list[float]:
    """One-hot on the local scale; ``near`` tilts it towards slot+1 so the
    cosine distance to ``_gemma(slot)`` is small but not zero."""
    v = [0.0] * GEMMA_DIM
    v[slot] = 1.0
    v[slot + 1] = near
    return v


def _openai(slot: int) -> list[float]:
    v = [0.0] * COMMENT_REPLY_EMBEDDING_DIM
    v[slot] = 1.0
    return v


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


@pytest.fixture
def shadow_on():
    s = get_settings()
    old = s.embedding_shadow
    s.embedding_shadow = True
    try:
        yield
    finally:
        s.embedding_shadow = old


async def _seed(db_session, suffix: str, *, read_model: str | None = None):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@gemma.example.com",
            account_name=f"GEMMA{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    if read_model is not None:
        owner.account.internal_attributes = {READ_MODEL_KEY: read_model}
        db_session.add(owner.account)
    headers, new_tokens = create_new_auth_token(
        user_tokens=owner.user.tokens, uid=owner.user.uid
    )
    owner.user.tokens = new_tokens
    db_session.add(owner.user)
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"IG{suffix}",
            channel_type="instagram",
            channel_params={
                "instagram_id": f"IG-BIZ{suffix}",
                "access_token": "PAGE-TOKEN",
            },
        ),
    ).perform()
    post = InstagramPost(
        account_id=owner.account.id,
        inbox_id=result.inbox.id,
        channel_instagram_id=result.channel.id,
        media_type="IMAGE",
        state="published",
        ig_media_id=f"MED{suffix}",
    )
    db_session.add(post)
    await db_session.flush()
    return owner, headers.as_response_headers(), result.channel, post


async def _semantic_rule(db_session, owner, post, **kw):
    rule = InstagramPostAutoreply(
        account_id=owner.account.id,
        post_id=post.id,
        match_type="semantic",
        delivery="public",
        enabled=True,
        **kw,
    )
    db_session.add(rule)
    await db_session.flush()
    return rule


async def _answer(db_session, owner, *, slot: int, reply: str):
    row = InstagramCommentReply(
        account_id=owner.account.id,
        trigger=f"pregunta {slot}",
        reply=reply,
        enabled=True,
        embedding=_openai(slot),
        embedding_gemma=_gemma(slot),
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def _decide(db_session, owner, channel, post, text="hola"):
    return await decide_reply(
        db_session,
        comment=InstagramComment(
            account_id=owner.account.id,
            channel_instagram_id=channel.id,
            ig_comment_id=f"CMT-{post.id}-{text[:6]}",
            ig_media_id=post.ig_media_id,
            from_id="SOMEONE-ELSE",
            text=text,
        ),
        post=post,
        our_ig_user_id=channel.instagram_id,
    )


def _stub_matching(monkeypatch, *, openai_slot: int, gemma_vector: list[float]):
    async def _openai_embed(text: str) -> list[float]:
        return _openai(openai_slot)

    async def _gemma_embed(text: str, *, task: str, title=None) -> list[float]:
        assert task == "classification"
        return gemma_vector

    monkeypatch.setattr(autoreply_mod, "embedding_search_enabled", lambda: True)
    monkeypatch.setattr(autoreply_mod, "embed_text", _openai_embed)
    monkeypatch.setattr(autoreply_mod, "gemma_enabled", lambda: True)
    monkeypatch.setattr(autoreply_mod, "embed_gemma_one", _gemma_embed)


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------
async def test_an_account_on_gemma_matches_with_the_local_vectors(
    db_session, monkeypatch
):
    owner, _h, channel, post = await _seed(db_session, "-read", read_model="gemma")
    await _semantic_rule(db_session, owner, post)
    await _answer(db_session, owner, slot=0, reply="sí, hay becas")
    await _answer(db_session, owner, slot=4, reply="enviamos a todo el país")
    # OpenAI would pick slot 4; the local model points at slot 0.
    _stub_matching(monkeypatch, openai_slot=4, gemma_vector=_gemma(0, near=0.3))

    decision = await _decide(db_session, owner, channel, post)
    assert decision.text == "sí, hay becas"
    assert decision.distance is not None and decision.distance < 0.15


async def test_the_openai_threshold_is_never_read_on_the_local_scale(
    db_session, monkeypatch
):
    """A rule tuned to 0.55 for OpenAI would answer anything on the local
    scale. With no local threshold of its own it uses the local default."""
    owner, _h, channel, post = await _seed(db_session, "-scale", read_model="gemma")
    await _semantic_rule(db_session, owner, post, max_distance=0.55)
    await _answer(db_session, owner, slot=0, reply="sí, hay becas")
    # Distance ≈ 0.22 to the answer: inside 0.55, outside the local 0.15.
    _stub_matching(monkeypatch, openai_slot=0, gemma_vector=_gemma(0, near=0.8))

    decision = await _decide(db_session, owner, channel, post)
    assert decision.text is None
    assert decision.reason == "below_threshold"


async def test_a_local_threshold_on_the_rule_is_used(db_session, monkeypatch):
    owner, _h, channel, post = await _seed(db_session, "-own", read_model="gemma")
    await _semantic_rule(db_session, owner, post, max_distance_gemma=0.35)
    await _answer(db_session, owner, slot=0, reply="sí, hay becas")
    _stub_matching(monkeypatch, openai_slot=0, gemma_vector=_gemma(0, near=0.8))

    decision = await _decide(db_session, owner, channel, post)
    assert decision.text == "sí, hay becas"


async def test_an_account_without_the_flag_keeps_answering_with_openai(
    db_session, monkeypatch
):
    owner, _h, channel, post = await _seed(db_session, "-default")
    await _semantic_rule(db_session, owner, post)
    await _answer(db_session, owner, slot=0, reply="sí, hay becas")
    await _answer(db_session, owner, slot=4, reply="enviamos a todo el país")
    _stub_matching(monkeypatch, openai_slot=4, gemma_vector=_gemma(0))

    decision = await _decide(db_session, owner, channel, post)
    assert decision.text == "enviamos a todo el país"


async def test_shadow_mode_logs_both_and_changes_nothing(
    db_session, monkeypatch, shadow_on, caplog
):
    owner, _h, channel, post = await _seed(db_session, "-shadow")
    await _semantic_rule(db_session, owner, post)
    await _answer(db_session, owner, slot=0, reply="sí, hay becas")
    await _answer(db_session, owner, slot=4, reply="enviamos a todo el país")
    _stub_matching(monkeypatch, openai_slot=4, gemma_vector=_gemma(0))

    with caplog.at_level(logging.INFO, logger=autoreply_mod.__name__):
        decision = await _decide(db_session, owner, channel, post)
    assert decision.text == "enviamos a todo el país"
    shadow = [r.getMessage() for r in caplog.records if "autoreply.shadow " in r.getMessage()]
    assert len(shadow) == 1
    assert "reading=openai" in shadow[0]
    assert "same_decision=False" in shadow[0]


async def test_a_failing_shadow_never_breaks_the_reply(
    db_session, monkeypatch, shadow_on
):
    owner, _h, channel, post = await _seed(db_session, "-shfail")
    await _semantic_rule(db_session, owner, post)
    await _answer(db_session, owner, slot=0, reply="sí, hay becas")
    _stub_matching(monkeypatch, openai_slot=0, gemma_vector=_gemma(0))

    async def _down(text: str, *, task: str, title=None) -> list[float]:
        raise RuntimeError("service down")

    monkeypatch.setattr(autoreply_mod, "embed_gemma_one", _down)
    decision = await _decide(db_session, owner, channel, post)
    assert decision.text == "sí, hay becas"


# ---------------------------------------------------------------------------
# Admin API
# ---------------------------------------------------------------------------
def _stub_saving(monkeypatch):
    async def _openai_embed(text: str) -> list[float]:
        return _openai(1)

    async def _gemma_embed(text: str, *, task: str, title=None) -> list[float]:
        return _gemma(1)

    monkeypatch.setattr(router_mod, "embedding_search_enabled", lambda: True)
    monkeypatch.setattr(router_mod, "embed_text", _openai_embed)
    monkeypatch.setattr(router_mod, "gemma_enabled", lambda: True)
    monkeypatch.setattr(router_mod, "embed_gemma_one", _gemma_embed)


async def test_saving_an_answer_writes_both_vectors(client, db_session, monkeypatch):
    owner, headers, _c, _p = await _seed(db_session, "-dual")
    _stub_saving(monkeypatch)
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_comment_replies",
        json={"trigger": "tienen becas?", "reply": "sí", "enabled": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    row = await db_session.get(InstagramCommentReply, resp.json()["id"])
    assert row.embedding is not None
    assert row.embedding_gemma is not None


async def test_the_status_says_which_model_answers(client, db_session, monkeypatch):
    owner, headers, _c, _p = await _seed(db_session, "-status", read_model="gemma")
    monkeypatch.setattr(router_mod, "gemma_enabled", lambda: True)
    resp = await client.get(
        f"/api/v1/accounts/{owner.account.id}/instagram_autoreply_status",
        headers=headers,
    )
    assert resp.json() == {"semantic_available": True, "embedding_model": "gemma"}


async def test_editing_the_local_threshold_keeps_the_openai_one(
    client, db_session
):
    """The owner's rule: OpenAI values are reviewed, never rewritten."""
    owner, headers, _c, post = await _seed(db_session, "-keep", read_model="gemma")
    rule = await _semantic_rule(db_session, owner, post, max_distance=0.55)
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/autoreply_rules/{rule.id}",
        json={
            "match_type": "semantic",
            "delivery": "public",
            "enabled": True,
            "max_distance_gemma": 0.13,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["max_distance"] == 0.55
    assert body["max_distance_gemma"] == 0.13
    assert body["effective_max_distance_gemma"] == 0.13


@pytest.mark.parametrize("value", [0.0, 0.55, 1.0])
async def test_a_local_threshold_outside_its_range_is_refused(
    client, db_session, value
):
    owner, headers, _c, post = await _seed(db_session, f"-grange{value}")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}/instagram_posts/{post.id}/autoreply_rules",
        json={
            "match_type": "semantic",
            "delivery": "public",
            "enabled": True,
            "max_distance_gemma": value,
        },
        headers=headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------
async def test_the_backfill_fills_only_what_is_missing(db_session, monkeypatch):
    owner, _h, _c, _p = await _seed(db_session, "-backfill")
    other, _h2, _c2, _p2 = await _seed(db_session, "-backfill-other")
    done = await _answer(db_session, owner, slot=2, reply="ya tenía")
    missing = InstagramCommentReply(
        account_id=owner.account.id, trigger="hacen envíos?", reply="sí"
    )
    foreign = InstagramCommentReply(
        account_id=other.account.id, trigger="otra cuenta", reply="no"
    )
    db_session.add_all([missing, foreign])
    await db_session.flush()

    calls: list[list[str]] = []

    async def _embed(texts: list[str], *, task: str, titles=None) -> list[list[float]]:
        calls.append(texts)
        assert task == "classification"
        return [_gemma(5) for _ in texts]

    monkeypatch.setattr(embeddings_backfill, "embed_gemma", _embed)
    written = await embeddings_backfill.backfill_comment_replies(
        db_session, account_id=owner.account.id
    )
    assert written == 1
    assert calls == [["hacen envíos?"]]
    await db_session.refresh(missing)
    await db_session.refresh(foreign)
    await db_session.refresh(done)
    assert missing.embedding_gemma is not None
    assert foreign.embedding_gemma is None
    assert list(done.embedding_gemma) == _gemma(2)


# ---------------------------------------------------------------------------
# Help Center
# ---------------------------------------------------------------------------
async def test_help_center_indexes_and_searches_with_the_local_model(
    db_session, monkeypatch
):
    owner, _h, _c, _p = await _seed(db_session, "-hc")
    portal = Portal(account_id=owner.account.id, name="Ayuda", slug="ayuda-gemma")
    db_session.add(portal)
    await db_session.flush()
    articles = []
    for slot, title in ((0, "Nota privada"), (3, "Adjuntar archivos")):
        art = Article(
            account_id=owner.account.id,
            portal_id=portal.id,
            title=title,
            content=f"contenido de {title}",
            slug=f"art-gemma-{slot}",
            status=ARTICLE_STATUS_PUBLISHED,
            locale="es",
        )
        db_session.add(art)
        articles.append((slot, art))
    await db_session.flush()

    by_title = {title: slot for slot, title in ((0, "Nota privada"), (3, "Adjuntar archivos"))}

    async def _embed(text: str, *, task: str, title=None) -> list[float]:
        if task == "document":
            return _gemma(by_title[title])
        assert task == "query"
        return _gemma(3, near=0.2)

    monkeypatch.setattr(portal_embeddings, "gemma_enabled", lambda: True)
    monkeypatch.setattr(portal_embeddings, "embed_gemma_one", _embed)
    for _slot, art in articles:
        assert await portal_embeddings.reindex_article_gemma(db_session, article_id=art.id) == 1

    rows = (
        await db_session.exec(
            select(ArticleEmbedding).where(ArticleEmbedding.model == "gemma")
        )
    ).all()
    assert {r.term for r in rows} >= {"Nota privada", "Adjuntar archivos"}
    assert all(r.embedding is None for r in rows)

    hits = await portal_embeddings.vector_search(
        db_session, portal_id=portal.id, query="mandar un pdf", model="gemma"
    )
    assert [a.title for a in hits][0] == "Adjuntar archivos"
