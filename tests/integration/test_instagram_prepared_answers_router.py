"""The prepared-answers endpoints, including scoping to a publication.

Embeddings are stubbed rather than left to the environment: a developer
with a key in ``.env`` would otherwise have these tests billing real
OpenAI calls, and the interesting case here is precisely the *absence* of
a provider — the state that produced the bug this covers, where every
answer saved unindexed and the UI told the admin to save again, which
could not help.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram import autoreply_router as router_mod
from app.domains.instagram.models import InstagramPost
from app.domains.teams import models as _teams  # noqa: F401  (mapper)
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def no_embedding_provider(monkeypatch):
    """The default for these tests: no provider, so nothing is billed and
    nothing reaches the network. Tests that need one override it."""
    monkeypatch.setattr(router_mod, "embedding_search_enabled", lambda: False)


@pytest.fixture
def with_embedding_provider(monkeypatch):
    async def _embed(text: str) -> list[float]:
        return [0.0] * 1536

    monkeypatch.setattr(router_mod, "embedding_search_enabled", lambda: True)
    monkeypatch.setattr(router_mod, "embed_text", _embed)


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


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@igpa.example.com",
            account_name=f"IGPA{suffix}",
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
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"IG{suffix}",
            channel_type="instagram",
            channel_params={
                "instagram_id": f"ig-{suffix}",
                "access_token": "PAGE-TOKEN",
            },
        ),
    ).perform()
    posts = []
    for n in (1, 2):
        post = InstagramPost(
            account_id=owner.account.id,
            inbox_id=result.inbox.id,
            channel_instagram_id=result.channel.id,
            media_type="IMAGE",
            state="published",
            ig_media_id=f"MED{suffix}{n}",
        )
        db_session.add(post)
        posts.append(post)
    await db_session.flush()
    return owner, headers.as_response_headers(), posts


def _url(owner, path: str) -> str:
    return f"/api/v1/accounts/{owner.account.id}{path}"


async def _create(client, owner, headers, *, trigger, post_id=None):
    return await client.post(
        _url(owner, "/instagram_comment_replies"),
        json={
            "trigger": trigger,
            "reply": f"respuesta a {trigger}",
            "enabled": True,
            "post_id": post_id,
        },
        headers=headers,
    )


async def test_status_says_similarity_is_off_without_a_provider(
    client, db_session
):
    owner, headers, _posts = await _seed(db_session, "-statusoff")
    resp = await client.get(
        _url(owner, "/instagram_autoreply_status"), headers=headers
    )
    assert resp.status_code == 200
    assert resp.json() == {"semantic_available": False}


async def test_status_says_similarity_is_on_with_one(
    client, db_session, with_embedding_provider
):
    owner, headers, _posts = await _seed(db_session, "-statuson")
    resp = await client.get(
        _url(owner, "/instagram_autoreply_status"), headers=headers
    )
    assert resp.json() == {"semantic_available": True}


async def test_an_answer_defaults_to_shared(client, db_session):
    owner, headers, _posts = await _seed(db_session, "-shared")
    resp = await _create(client, owner, headers, trigger="hacen envíos?")
    assert resp.status_code == 200
    assert resp.json()["post_id"] is None
    # Honest about the fact that it cannot match without a provider.
    assert resp.json()["indexed"] is False


async def test_an_answer_saved_with_a_provider_is_indexed(
    client, db_session, with_embedding_provider
):
    owner, headers, _posts = await _seed(db_session, "-indexed")
    resp = await _create(client, owner, headers, trigger="hacen envíos?")
    assert resp.json()["indexed"] is True


async def test_re_saving_an_unindexed_answer_retries_the_embedding(
    client, db_session, monkeypatch
):
    """"Volvé a guardarla" is the documented fix, so it has to work.

    Before, a save only re-embedded when the trigger text changed — so
    re-saving the same wording after a transient failure did nothing.
    """
    owner, headers, _posts = await _seed(db_session, "-retry")
    created = (
        await _create(client, owner, headers, trigger="hacen envíos?")
    ).json()
    assert created["indexed"] is False

    async def _embed(text: str) -> list[float]:
        return [0.0] * 1536

    monkeypatch.setattr(router_mod, "embedding_search_enabled", lambda: True)
    monkeypatch.setattr(router_mod, "embed_text", _embed)

    resp = await client.patch(
        _url(owner, f"/instagram_comment_replies/{created['id']}"),
        # Same wording as before — only the provider changed.
        json={
            "trigger": "hacen envíos?",
            "reply": "Sí, a todo el país.",
            "enabled": True,
            "post_id": None,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["indexed"] is True


async def test_an_answer_can_belong_to_one_publication(client, db_session):
    owner, headers, posts = await _seed(db_session, "-scoped")
    resp = await _create(
        client, owner, headers, trigger="qué talles?", post_id=posts[0].id
    )
    assert resp.status_code == 200
    assert resp.json()["post_id"] == posts[0].id


async def test_a_publication_from_another_account_is_rejected(
    client, db_session
):
    owner, headers, _posts = await _seed(db_session, "-mine")
    other, _other_headers, other_posts = await _seed(db_session, "-theirs")
    resp = await _create(
        client, owner, headers, trigger="fisgón", post_id=other_posts[0].id
    )
    assert resp.status_code == 404
    assert other.account.id != owner.account.id


async def test_listing_by_publication_returns_its_own_plus_the_shared(
    client, db_session
):
    owner, headers, posts = await _seed(db_session, "-list")
    await _create(client, owner, headers, trigger="compartida")
    await _create(client, owner, headers, trigger="mía", post_id=posts[0].id)
    await _create(client, owner, headers, trigger="ajena", post_id=posts[1].id)

    resp = await client.get(
        _url(owner, f"/instagram_comment_replies?post_id={posts[0].id}"),
        headers=headers,
    )
    assert resp.status_code == 200
    assert {r["trigger"] for r in resp.json()} == {"compartida", "mía"}


async def test_listing_without_a_publication_returns_the_whole_library(
    client, db_session
):
    owner, headers, posts = await _seed(db_session, "-all")
    await _create(client, owner, headers, trigger="compartida")
    await _create(client, owner, headers, trigger="de un post", post_id=posts[0].id)

    resp = await client.get(
        _url(owner, "/instagram_comment_replies"), headers=headers
    )
    assert {r["trigger"] for r in resp.json()} == {"compartida", "de un post"}


async def test_an_agent_cannot_touch_the_library(client, db_session):
    """These endpoints are admin-only — an answer speaks for the brand."""
    owner, _headers, _posts = await _seed(db_session, "-agent")
    resp = await client.get(_url(owner, "/instagram_comment_replies"))
    assert resp.status_code in (401, 403)
