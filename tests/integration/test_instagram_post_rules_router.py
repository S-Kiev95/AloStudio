"""The per-publication rule endpoints, driven with the form's own payloads.

Each test posts exactly what ``PostAutoreplyRules`` sends for that mode —
including the nulls it sends for the fields that mode does not use — so a
rule that saves in a test but not in the browser cannot pass here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram.models import InstagramPost
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


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@igpr.example.com",
            account_name=f"IGPR{suffix}",
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
    return owner, headers.as_response_headers(), post


def _rules_url(owner, post) -> str:
    return (
        f"/api/v1/accounts/{owner.account.id}"
        f"/instagram_posts/{post.id}/autoreply_rules"
    )


# What the form actually sends, per mode.
KEYWORD_PAYLOAD = {
    "match_type": "keyword",
    "keywords": "info, link",
    "reply_text": "Ahí va: ejemplo.com",
    "delivery": "dm",
    "enabled": True,
}
SEMANTIC_PAYLOAD = {
    "match_type": "semantic",
    "keywords": None,
    "reply_text": None,
    "delivery": "dm",
    "enabled": True,
}
ALL_PAYLOAD = {
    "match_type": "all",
    "keywords": None,
    "reply_text": "¡Gracias por comentar!",
    "delivery": "public",
    "enabled": True,
}


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("keyword", KEYWORD_PAYLOAD),
        ("semantic", SEMANTIC_PAYLOAD),
        ("all", ALL_PAYLOAD),
    ],
)
async def test_the_form_payload_saves_and_comes_back_in_the_list(
    client, db_session, name, payload
):
    owner, headers, post = await _seed(db_session, f"-{name}")
    created = await client.post(
        _rules_url(owner, post), json=payload, headers=headers
    )
    assert created.status_code == 200, created.text
    assert created.json()["match_type"] == payload["match_type"]

    listed = await client.get(_rules_url(owner, post), headers=headers)
    assert listed.status_code == 200
    assert [r["id"] for r in listed.json()] == [created.json()["id"]]


async def test_a_semantic_rule_needs_no_text_of_its_own(client, db_session):
    """Its text comes from the matched library entry, not the rule."""
    owner, headers, post = await _seed(db_session, "-sem2")
    resp = await client.post(
        _rules_url(owner, post), json=SEMANTIC_PAYLOAD, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["reply_text"] is None
    assert resp.json()["keywords"] is None


async def test_a_keyword_rule_without_words_is_refused(client, db_session):
    """A rule that can never fire is worse than an error at save time."""
    owner, headers, post = await _seed(db_session, "-nokw")
    resp = await client.post(
        _rules_url(owner, post),
        json={**KEYWORD_PAYLOAD, "keywords": None},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_a_catch_all_without_text_is_refused(client, db_session):
    owner, headers, post = await _seed(db_session, "-notext")
    resp = await client.post(
        _rules_url(owner, post),
        json={**ALL_PAYLOAD, "reply_text": None},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_rules_come_back_in_the_order_they_fire(client, db_session):
    """Written catch-all first, but shown last.

    A catch-all listed above a keyword rule reads as if it swallowed
    everything, which is the opposite of what the matcher does.
    """
    owner, headers, post = await _seed(db_session, "-order")
    for payload in (ALL_PAYLOAD, SEMANTIC_PAYLOAD, KEYWORD_PAYLOAD):
        resp = await client.post(
            _rules_url(owner, post), json=payload, headers=headers
        )
        assert resp.status_code == 200, resp.text

    listed = (await client.get(_rules_url(owner, post), headers=headers)).json()
    assert [r["match_type"] for r in listed] == ["keyword", "semantic", "all"]


async def test_a_publication_from_another_account_is_rejected(
    client, db_session
):
    owner, headers, _post = await _seed(db_session, "-mine")
    _other, _oh, other_post = await _seed(db_session, "-theirs")
    resp = await client.post(
        f"/api/v1/accounts/{owner.account.id}"
        f"/instagram_posts/{other_post.id}/autoreply_rules",
        json=KEYWORD_PAYLOAD,
        headers=headers,
    )
    assert resp.status_code == 404
