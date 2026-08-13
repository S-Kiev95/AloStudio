"""Auto-reply decision rules for Instagram comments.

Most of these test refusals rather than replies. A reply here is a public
comment under the brand's own post, so the interesting question is not
"does it answer" but "does it correctly stay quiet".
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.models_registry import import_all_models
from app.domains.instagram.autoreply import decide_reply
from app.domains.instagram.models import (
    InstagramChannelSetting,
    InstagramComment,
)

import_all_models()

pytestmark = pytest.mark.unit

OUR_IG_ID = "17841451736515320"


def _setting(**over) -> InstagramChannelSetting:
    base = {
        "channel_instagram_id": 1,
        "comment_autoreply_mode": "fixed",
        "comment_autoreply_text": "¡Gracias por escribir! Te respondemos por DM.",
        "comment_autoreply_max_distance": 0.35,
    }
    base.update(over)
    return InstagramChannelSetting(**base)


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


async def _decide(comment, setting, our_id=OUR_IG_ID):
    # ``session`` is unused on every path these tests exercise: fixed mode
    # never queries, and the guards return before the semantic branch.
    return await decide_reply(
        None, comment=comment, setting=setting, our_ig_user_id=our_id
    )


# ---------------------------------------------------------------------------
# Fixed mode
# ---------------------------------------------------------------------------
async def test_fixed_mode_answers_a_normal_comment():
    d = await _decide(_comment(), _setting())
    assert d.should_reply
    assert d.text.startswith("¡Gracias")
    assert d.reason == "fixed"


async def test_off_by_default_and_when_disabled():
    assert not (await _decide(_comment(), _setting(comment_autoreply_mode="off"))).should_reply
    # An unknown mode is treated as off rather than guessed at.
    d = await _decide(_comment(), _setting(comment_autoreply_mode="weird"))
    assert d.reason == "disabled"


async def test_fixed_mode_without_text_stays_quiet():
    d = await _decide(_comment(), _setting(comment_autoreply_text="  "))
    assert not d.should_reply
    assert d.reason == "fixed_text_missing"


# ---------------------------------------------------------------------------
# Guards — the part that protects the brand's own post
# ---------------------------------------------------------------------------
async def test_never_answers_our_own_comment():
    """The loop guard.

    Our reply is itself a comment that fires the same webhook. Without this
    the account would answer itself indefinitely, in public.
    """
    d = await _decide(_comment(from_id=OUR_IG_ID), _setting())
    assert not d.should_reply
    assert d.reason == "own_comment"


async def test_stays_quiet_when_our_own_id_is_unknown():
    """Without the id the loop guard cannot run, so silence is the safe
    default — better mute than talking to ourselves."""
    d = await _decide(_comment(), _setting(), our_id=None)
    assert not d.should_reply
    assert d.reason == "unknown_own_id"


async def test_never_answers_the_same_comment_twice():
    """Meta redelivers webhooks and the sync re-reads threads."""
    d = await _decide(
        _comment(auto_replied_at=datetime.now(UTC)), _setting()
    )
    assert not d.should_reply
    assert d.reason == "already_replied"


async def test_ignores_replies_inside_a_thread():
    d = await _decide(_comment(parent_comment_id="C0"), _setting())
    assert not d.should_reply
    assert d.reason == "is_a_reply"


async def test_ignores_an_empty_comment():
    """Emoji/sticker-only comments carry nothing to match on."""
    d = await _decide(_comment(text="   "), _setting())
    assert not d.should_reply
    assert d.reason == "empty_comment"


async def test_ignores_a_hidden_comment():
    d = await _decide(_comment(hidden=True), _setting())
    assert not d.should_reply
    assert d.reason == "hidden"


async def test_missing_settings_means_off():
    d = await _decide(_comment(), None)
    assert not d.should_reply
    assert d.reason == "no_settings"
