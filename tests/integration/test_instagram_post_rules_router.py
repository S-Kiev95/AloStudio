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


# ---------------------------------------------------------------------------
# Picking which prepared answers a publication offers
# ---------------------------------------------------------------------------
def _picks_url(owner, post) -> str:
    return (
        f"/api/v1/accounts/{owner.account.id}"
        f"/instagram_posts/{post.id}/comment_replies"
    )


def _library_url(owner, post=None) -> str:
    url = f"/api/v1/accounts/{owner.account.id}/instagram_comment_replies"
    return url if post is None else f"{url}?post_id={post.id}"


async def _answer(client, owner, headers, trigger: str) -> int:
    resp = await client.post(
        _library_url(owner),
        json={"trigger": trigger, "reply": f"respuesta a {trigger}"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def test_a_publication_with_no_picks_is_offered_the_whole_library(
    client, db_session
):
    """Absence means "everything" — similarity works before curating."""
    owner, headers, post = await _seed(db_session, "-nopicks")
    await _answer(client, owner, headers, "hacen envíos?")
    await _answer(client, owner, headers, "cuánto sale?")

    listed = (await client.get(_library_url(owner, post), headers=headers)).json()
    assert len(listed) == 2
    assert all(r["selected"] is False for r in listed)


async def test_picking_marks_only_the_chosen_ones(client, db_session):
    owner, headers, post = await _seed(db_session, "-pick")
    shipping = await _answer(client, owner, headers, "hacen envíos?")
    await _answer(client, owner, headers, "cuánto sale?")

    resp = await client.put(
        _picks_url(owner, post), json={"reply_ids": [shipping]}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["reply_ids"] == [shipping]

    listed = (await client.get(_library_url(owner, post), headers=headers)).json()
    # The library still lists everything: you cannot pick what is hidden.
    assert len(listed) == 2
    assert {r["id"]: r["selected"] for r in listed} == {
        shipping: True,
        next(r["id"] for r in listed if r["id"] != shipping): False,
    }


async def test_the_same_answer_serves_several_publications(client, db_session):
    """The reason this is a join table and not a column."""
    owner, headers, first = await _seed(db_session, "-shared1")
    second = InstagramPost(
        account_id=owner.account.id,
        inbox_id=first.inbox_id,
        channel_instagram_id=first.channel_instagram_id,
        media_type="IMAGE",
        state="published",
        ig_media_id="MED-shared2",
    )
    db_session.add(second)
    await db_session.flush()

    shipping = await _answer(client, owner, headers, "hacen envíos?")
    for post in (first, second):
        resp = await client.put(
            _picks_url(owner, post),
            json={"reply_ids": [shipping]},
            headers=headers,
        )
        assert resp.status_code == 200

    for post in (first, second):
        listed = (
            await client.get(_library_url(owner, post), headers=headers)
        ).json()
        assert [r["selected"] for r in listed] == [True]


async def test_replacing_the_set_clears_what_was_dropped(client, db_session):
    owner, headers, post = await _seed(db_session, "-replace")
    a = await _answer(client, owner, headers, "hacen envíos?")
    b = await _answer(client, owner, headers, "cuánto sale?")

    await client.put(
        _picks_url(owner, post), json={"reply_ids": [a, b]}, headers=headers
    )
    resp = await client.put(
        _picks_url(owner, post), json={"reply_ids": [b]}, headers=headers
    )
    assert resp.json()["reply_ids"] == [b]


async def test_an_empty_set_falls_back_to_the_whole_library(client, db_session):
    owner, headers, post = await _seed(db_session, "-clear")
    a = await _answer(client, owner, headers, "hacen envíos?")
    await client.put(
        _picks_url(owner, post), json={"reply_ids": [a]}, headers=headers
    )

    resp = await client.put(
        _picks_url(owner, post), json={"reply_ids": []}, headers=headers
    )
    assert resp.json()["reply_ids"] == []
    listed = (await client.get(_library_url(owner, post), headers=headers)).json()
    assert all(r["selected"] is False for r in listed)


async def test_picking_the_same_answer_twice_is_not_an_error(client, db_session):
    """A double-submit must not trip the uniqueness constraint."""
    owner, headers, post = await _seed(db_session, "-twice")
    a = await _answer(client, owner, headers, "hacen envíos?")
    for _ in range(2):
        resp = await client.put(
            _picks_url(owner, post), json={"reply_ids": [a, a]}, headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["reply_ids"] == [a]


async def test_another_accounts_answer_cannot_be_picked(client, db_session):
    owner, headers, post = await _seed(db_session, "-mineown")
    other, other_headers, _op = await _seed(db_session, "-notmine")
    theirs = await _answer(client, other, other_headers, "secreto")

    resp = await client.put(
        _picks_url(owner, post), json={"reply_ids": [theirs]}, headers=headers
    )
    assert resp.status_code == 200
    # Dropped rather than trusted — picking it would leak their answer.
    assert resp.json()["reply_ids"] == []


async def test_picks_for_a_publication_you_do_not_own_are_refused(
    client, db_session
):
    owner, headers, _post = await _seed(db_session, "-owner")
    _other, _oh, other_post = await _seed(db_session, "-otherpost")
    resp = await client.put(
        _picks_url(owner, other_post), json={"reply_ids": []}, headers=headers
    )
    assert resp.status_code == 404


async def test_a_rule_can_be_switched_from_private_to_public(
    client, db_session
):
    """The panel edits a saved rule; the endpoint has to accept the change."""
    owner, headers, post = await _seed(db_session, "-flip")
    created = await client.post(
        _rules_url(owner, post), json=KEYWORD_PAYLOAD, headers=headers
    )
    rule_id = created.json()["id"]

    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/autoreply_rules/{rule_id}",
        json={**KEYWORD_PAYLOAD, "delivery": "public"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["delivery"] == "public"

    listed = (await client.get(_rules_url(owner, post), headers=headers)).json()
    assert [r["delivery"] for r in listed] == ["public"]


async def test_editing_does_not_mint_a_second_rule(client, db_session):
    owner, headers, post = await _seed(db_session, "-onlyone")
    created = await client.post(
        _rules_url(owner, post), json=KEYWORD_PAYLOAD, headers=headers
    )
    await client.patch(
        f"/api/v1/accounts/{owner.account.id}/autoreply_rules/"
        f"{created.json()['id']}",
        json={**KEYWORD_PAYLOAD, "keywords": "becas"},
        headers=headers,
    )
    listed = (await client.get(_rules_url(owner, post), headers=headers)).json()
    assert len(listed) == 1
    assert listed[0]["keywords"] == "becas"


async def test_an_edit_is_validated_like_a_creation(client, db_session):
    """Otherwise editing is a way around the rules that creation enforces."""
    owner, headers, post = await _seed(db_session, "-editval")
    created = await client.post(
        _rules_url(owner, post), json=KEYWORD_PAYLOAD, headers=headers
    )
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/autoreply_rules/"
        f"{created.json()['id']}",
        json={**KEYWORD_PAYLOAD, "keywords": "  "},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_another_accounts_rule_cannot_be_edited(client, db_session):
    owner, headers, _post = await _seed(db_session, "-editmine")
    other, other_headers, other_post = await _seed(db_session, "-edittheirs")
    theirs = await client.post(
        _rules_url(other, other_post), json=KEYWORD_PAYLOAD, headers=other_headers
    )
    resp = await client.patch(
        f"/api/v1/accounts/{owner.account.id}/autoreply_rules/"
        f"{theirs.json()['id']}",
        json={**KEYWORD_PAYLOAD, "delivery": "public"},
        headers=headers,
    )
    assert resp.status_code == 404
