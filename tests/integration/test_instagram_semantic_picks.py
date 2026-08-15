"""Which prepared answers one publication matches against.

Answers are written once for the account and picked per publication. The
rule that makes this usable is that absence means everything: a post that
has picked nothing can use the whole library, so similarity matching works
before anyone curates it, and picking is what narrows it.

Embeddings are stubbed with one-hot vectors so the distances are exact and
the test asserts on selection, not on how a real model happens to rank two
Spanish sentences.
"""

from __future__ import annotations

import pytest

from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.inboxes.service import InboxBuilder, InboxBuilderParams
from app.domains.instagram import autoreply as autoreply_mod
from app.domains.instagram.autoreply import decide_reply
from app.domains.instagram.autoreply_models import (
    COMMENT_REPLY_EMBEDDING_DIM,
    InstagramCommentReply,
    InstagramPostReplyPick,
)
from app.domains.instagram.models import InstagramComment, InstagramPost
from app.domains.instagram.post_autoreply_models import InstagramPostAutoreply
from app.domains.teams import models as _teams  # noqa: F401  (mapper)

pytestmark = pytest.mark.integration

OUR_IG_ID = "IG-BIZ"


def _vec(slot: int) -> list[float]:
    """A one-hot vector: identical slots are distance 0, different are 1."""
    v = [0.0] * COMMENT_REPLY_EMBEDDING_DIM
    v[slot] = 1.0
    return v


@pytest.fixture
def stub_embeddings(monkeypatch):
    """Embed the comment into whichever slot the test asks for."""
    slot = {"value": 0}

    async def _embed(text: str) -> list[float]:
        return _vec(slot["value"])

    monkeypatch.setattr(autoreply_mod, "embed_text", _embed)
    monkeypatch.setattr(autoreply_mod, "embedding_search_enabled", lambda: True)
    return slot


async def _seed(db_session, suffix: str):
    owner = await AccountBuilder(
        db_session,
        AccountBuilderParams(
            email=f"admin{suffix}@igsem.example.com",
            account_name=f"IGSEM{suffix}",
            user_full_name=f"Admin{suffix}",
            user_password="Password123!",
            confirmed=True,
        ),
    ).perform()
    result = await InboxBuilder(
        db_session,
        InboxBuilderParams(
            account=owner.account,
            name=f"IG{suffix}",
            channel_type="instagram",
            channel_params={
                "instagram_id": OUR_IG_ID + suffix,
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
    # Every post in these tests answers by similarity.
    for post in posts:
        db_session.add(
            InstagramPostAutoreply(
                account_id=owner.account.id,
                post_id=post.id,
                match_type="semantic",
                delivery="public",
                enabled=True,
            )
        )
    await db_session.flush()
    return owner, result.channel, posts


async def _answer(db_session, *, account_id, trigger, reply, slot, indexed=True):
    row = InstagramCommentReply(
        account_id=account_id,
        trigger=trigger,
        reply=reply,
        enabled=True,
        embedding=_vec(slot) if indexed else None,
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def _pick(db_session, *, post, answer):
    db_session.add(
        InstagramPostReplyPick(post_id=post.id, comment_reply_id=answer.id)
    )
    await db_session.flush()


def _comment(*, account_id, channel_id, post, text):
    return InstagramComment(
        account_id=account_id,
        channel_instagram_id=channel_id,
        ig_comment_id=f"CMT-{post.id}-{text[:6]}",
        ig_media_id=post.ig_media_id,
        from_id="SOMEONE-ELSE",
        text=text,
    )


async def _decide(db_session, *, owner, channel, post, text):
    return await decide_reply(
        db_session,
        comment=_comment(
            account_id=owner.account.id,
            channel_id=channel.id,
            post=post,
            text=text,
        ),
        post=post,
        our_ig_user_id=channel.instagram_id,
    )


async def test_a_publication_that_picked_nothing_uses_the_whole_library(
    db_session, stub_embeddings
):
    """Turning similarity on must not require curating first."""
    owner, channel, posts = await _seed(db_session, "-nopick")
    await _answer(
        db_session,
        account_id=owner.account.id,
        trigger="hacen envíos?",
        reply="Sí, a todo el país.",
        slot=0,
    )
    stub_embeddings["value"] = 0
    for post in posts:
        d = await _decide(
            db_session, owner=owner, channel=channel, post=post, text="envían?"
        )
        assert d.text == "Sí, a todo el país."


async def test_a_picked_answer_is_used(db_session, stub_embeddings):
    owner, channel, posts = await _seed(db_session, "-picked")
    sizes = await _answer(
        db_session,
        account_id=owner.account.id,
        trigger="qué talles hay?",
        reply="Del 38 al 45.",
        slot=0,
    )
    await _pick(db_session, post=posts[0], answer=sizes)
    stub_embeddings["value"] = 0
    d = await _decide(
        db_session, owner=owner, channel=channel, post=posts[0], text="talles?"
    )
    assert d.text == "Del 38 al 45."


async def test_picking_excludes_everything_not_picked(
    db_session, stub_embeddings
):
    """The point of picking. Ten of a hundred means ten, not a preference."""
    owner, channel, posts = await _seed(db_session, "-excl")
    sizes = await _answer(
        db_session,
        account_id=owner.account.id,
        trigger="qué talles hay?",
        reply="Del 38 al 45.",
        slot=0,
    )
    await _answer(
        db_session,
        account_id=owner.account.id,
        trigger="hacen envíos?",
        reply="Sí, a todo el país.",
        slot=1,
    )
    await _pick(db_session, post=posts[0], answer=sizes)

    # A comment that would match the shipping answer exactly gets nothing,
    # because this publication does not offer it.
    stub_embeddings["value"] = 1
    d = await _decide(
        db_session, owner=owner, channel=channel, post=posts[0], text="envían?"
    )
    assert d.text is None
    assert d.reason == "below_threshold"


async def test_another_publication_keeps_its_own_picks(
    db_session, stub_embeddings
):
    owner, channel, posts = await _seed(db_session, "-perpost")
    sizes = await _answer(
        db_session,
        account_id=owner.account.id,
        trigger="qué talles hay?",
        reply="Del 38 al 45.",
        slot=0,
    )
    shipping = await _answer(
        db_session,
        account_id=owner.account.id,
        trigger="hacen envíos?",
        reply="Sí, a todo el país.",
        slot=1,
    )
    await _pick(db_session, post=posts[0], answer=sizes)
    await _pick(db_session, post=posts[1], answer=shipping)

    stub_embeddings["value"] = 0
    assert (
        await _decide(
            db_session, owner=owner, channel=channel, post=posts[0], text="?"
        )
    ).text == "Del 38 al 45."
    stub_embeddings["value"] = 1
    assert (
        await _decide(
            db_session, owner=owner, channel=channel, post=posts[1], text="?"
        )
    ).text == "Sí, a todo el país."


async def test_one_answer_serves_several_publications(
    db_session, stub_embeddings
):
    """Written once, picked twice — the reason this is not a column."""
    owner, channel, posts = await _seed(db_session, "-reuse")
    shipping = await _answer(
        db_session,
        account_id=owner.account.id,
        trigger="hacen envíos?",
        reply="Sí, a todo el país.",
        slot=0,
    )
    for post in posts:
        await _pick(db_session, post=post, answer=shipping)

    stub_embeddings["value"] = 0
    for post in posts:
        d = await _decide(
            db_session, owner=owner, channel=channel, post=post, text="envían?"
        )
        assert d.text == "Sí, a todo el país."


async def test_the_closest_of_the_picked_ones_wins(db_session, stub_embeddings):
    owner, channel, posts = await _seed(db_session, "-closest")
    sizes = await _answer(
        db_session,
        account_id=owner.account.id,
        trigger="qué talles hay?",
        reply="Del 38 al 45.",
        slot=0,
    )
    shipping = await _answer(
        db_session,
        account_id=owner.account.id,
        trigger="hacen envíos?",
        reply="Sí, a todo el país.",
        slot=1,
    )
    for answer in (sizes, shipping):
        await _pick(db_session, post=posts[0], answer=answer)

    stub_embeddings["value"] = 1
    d = await _decide(
        db_session, owner=owner, channel=channel, post=posts[0], text="envían?"
    )
    assert d.text == "Sí, a todo el país."


async def test_an_unrelated_comment_is_left_for_a_person(
    db_session, stub_embeddings
):
    owner, channel, posts = await _seed(db_session, "-miss")
    await _answer(
        db_session,
        account_id=owner.account.id,
        trigger="hacen envíos?",
        reply="Sí, a todo el país.",
        slot=0,
    )
    # Orthogonal to every answer: distance 1.0, well past the threshold.
    stub_embeddings["value"] = 500
    d = await _decide(
        db_session,
        owner=owner,
        channel=channel,
        post=posts[0],
        text="qué lindo reel",
    )
    assert d.text is None
    assert d.reason == "below_threshold"


async def test_an_unindexed_answer_is_never_offered(db_session, stub_embeddings):
    """Even picked — the UI warns about this, so it must be true."""
    owner, channel, posts = await _seed(db_session, "-noidx")
    row = await _answer(
        db_session,
        account_id=owner.account.id,
        trigger="hacen envíos?",
        reply="Sí, a todo el país.",
        slot=0,
        indexed=False,
    )
    await _pick(db_session, post=posts[0], answer=row)
    stub_embeddings["value"] = 0
    d = await _decide(
        db_session, owner=owner, channel=channel, post=posts[0], text="envían?"
    )
    assert d.text is None
    assert d.reason == "no_prepared_answers"
