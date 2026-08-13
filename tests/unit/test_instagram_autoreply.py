"""Auto-reply decision rules for Instagram comments.

Most of these test refusals rather than replies. A public reply is a
comment under the brand's own post, so the interesting question is not
"does it answer" but "does it correctly stay quiet".
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.models_registry import import_all_models
from app.domains.instagram.autoreply import _fold, _keyword_hit
from app.domains.instagram.models import InstagramComment
from app.domains.instagram.post_autoreply_models import (
    DELIVERY_DM,
    MATCH_ALL,
    MATCH_KEYWORD,
    MATCH_PRIORITY,
    MATCH_SEMANTIC,
    InstagramPostAutoreply,
)

import_all_models()

pytestmark = pytest.mark.unit

OUR_IG_ID = "17841451736515320"


def _comment(**over) -> InstagramComment:
    base = {
        "account_id": 1,
        "channel_instagram_id": 1,
        "ig_comment_id": "C1",
        "ig_media_id": "M1",
        "from_id": "999",
        "from_username": "cliente",
        "text": "hacen envíos al interior?",
        "hidden": False,
        "parent_comment_id": None,
    }
    base.update(over)
    return InstagramComment(**base)


def _rule(**over) -> InstagramPostAutoreply:
    base = {
        "account_id": 1,
        "post_id": 1,
        "match_type": MATCH_KEYWORD,
        "keywords": "info",
        "reply_text": "Te lo paso!",
        "delivery": DELIVERY_DM,
        "enabled": True,
    }
    base.update(over)
    return InstagramPostAutoreply(**base)


# ---------------------------------------------------------------------------
# Keyword matching
# ---------------------------------------------------------------------------
def test_keyword_matching_ignores_case_and_accents():
    """A mechanic that only fires on an exact spelling misses most of the
    audience it is aimed at — people type INFO, info and ínfo."""
    rule = _rule(keywords="info")
    for written in ("INFO", "Info", "quiero info por favor", "ínfo"):
        assert _keyword_hit(rule, written), written


def test_keyword_matching_accepts_several_words():
    rule = _rule(keywords="info, precio , LINK")
    assert _keyword_hit(rule, "me pasás el link?")
    assert _keyword_hit(rule, "cuál es el PRECIO")
    assert not _keyword_hit(rule, "qué lindo post")


def test_keyword_matching_ignores_blank_entries():
    """A trailing comma must not turn into a rule that matches everything."""
    rule = _rule(keywords="info,,  ,")
    assert not _keyword_hit(rule, "cualquier cosa")


def test_fold_strips_accents_and_case():
    assert _fold("Envíos RÁPIDOS") == "envios rapidos"


# ---------------------------------------------------------------------------
# Rule ordering
# ---------------------------------------------------------------------------
def test_keyword_rules_outrank_the_catch_all():
    """Otherwise a catch-all on the same post swallows every comment and
    the keyword mechanic never fires."""
    assert MATCH_PRIORITY[MATCH_KEYWORD] < MATCH_PRIORITY[MATCH_SEMANTIC]
    assert MATCH_PRIORITY[MATCH_SEMANTIC] < MATCH_PRIORITY[MATCH_ALL]


# ---------------------------------------------------------------------------
# Guards — the part that protects the brand's own post
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "over,expected",
    [
        ({"auto_replied_at": datetime.now(UTC)}, "already_replied"),
        ({"text": "   "}, "empty_comment"),
        ({"parent_comment_id": "C0"}, "is_a_reply"),
        ({"from_id": OUR_IG_ID}, "own_comment"),
        ({"hidden": True}, "hidden"),
    ],
)
async def test_guards_refuse_to_answer(over, expected):
    from app.domains.instagram.autoreply import decide_reply
    from app.domains.instagram.models import InstagramPost

    post = InstagramPost(
        account_id=1, inbox_id=1, channel_instagram_id=1,
        state=3, media_type="IMAGE", source={}, ig_media_id="M1",
    )
    post.id = 1
    d = await decide_reply(
        None, comment=_comment(**over), post=post, our_ig_user_id=OUR_IG_ID
    )
    assert not d.should_reply
    assert d.reason == expected


async def test_stays_quiet_when_our_own_id_is_unknown():
    """Without the id the loop guard cannot run, so silence is the safe
    default — better mute than talking to ourselves."""
    from app.domains.instagram.autoreply import decide_reply
    from app.domains.instagram.models import InstagramPost

    post = InstagramPost(
        account_id=1, inbox_id=1, channel_instagram_id=1,
        state=3, media_type="IMAGE", source={}, ig_media_id="M1",
    )
    post.id = 1
    d = await decide_reply(
        None, comment=_comment(), post=post, our_ig_user_id=None
    )
    assert d.reason == "unknown_own_id"


async def test_a_comment_on_an_unknown_post_is_ignored():
    """Media published outside AloStudio has no rules to apply."""
    from app.domains.instagram.autoreply import decide_reply

    d = await decide_reply(
        None, comment=_comment(), post=None, our_ig_user_id=OUR_IG_ID
    )
    assert not d.should_reply
    assert d.reason == "unknown_post"
