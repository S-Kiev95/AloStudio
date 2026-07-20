"""Unit tests for Instagram media_type normalisation (no DB).

Meta deprecated the standalone ``VIDEO`` feed type — container creation 400s
with subcode 2207067 — so the publisher folds it to ``REELS``, which surfaces
in the feed the same way.
"""

from __future__ import annotations

import pytest

from app.core.errors import ChatwootHTTPException
from app.domains.instagram.publishing_service import _validate_media_type


def test_video_is_folded_to_reels():
    assert _validate_media_type("VIDEO") == "REELS"


@pytest.mark.parametrize(
    "media_type", ["IMAGE", "REELS", "CAROUSEL", "STORIES"]
)
def test_supported_types_pass_through(media_type):
    assert _validate_media_type(media_type) == media_type


@pytest.mark.parametrize("bad", ["video", "reel", "", "GIF", None, 3])
def test_unknown_types_are_rejected(bad):
    with pytest.raises(ChatwootHTTPException) as exc:
        _validate_media_type(bad)
    assert exc.value.status_code == 422
