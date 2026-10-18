"""Unit tests for the attachment half of ``present_message``.

Mirrors ``Attachment#push_event_data``. Blob types also carry the original
file name (``fallback_title``) and ``extension``: Chatwoot reads a name off
the ActiveStorage blob, we have no blob, so without them a client can only
show a generic "Download attachment". The shape stays a superset of
Chatwoot's — these tests pin both halves.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.storage import object_url
from app.domains.conversations.models import (
    FILE_TYPE_AUDIO,
    FILE_TYPE_CONTACT,
    FILE_TYPE_EMBED,
    FILE_TYPE_FALLBACK,
    FILE_TYPE_FILE,
    FILE_TYPE_IG_POST,
    FILE_TYPE_IG_REEL,
    FILE_TYPE_IG_STORY,
    FILE_TYPE_IMAGE,
    FILE_TYPE_LOCATION,
    FILE_TYPE_SHARE,
    FILE_TYPE_STORY_MENTION,
    FILE_TYPE_VIDEO,
)
from app.domains.conversations.presenters import present_attachment_push_event

pytestmark = pytest.mark.unit

BASE_KEYS = {"id", "message_id", "file_type", "account_id"}


def _attachment(**over):
    base = {
        "id": 15,
        "account_id": 7,
        "message_id": 40,
        "file_type": FILE_TYPE_FILE,
        "external_url": object_url("7/uploads/presupuesto-octubre.txt"),
        "extension": "txt",
        "fallback_title": "presupuesto-octubre.txt",
        "coordinates_lat": 0.0,
        "coordinates_long": 0.0,
        "meta": None,
    }
    base.update(over)
    return SimpleNamespace(**base)


def test_a_sent_file_keeps_its_name_and_extension():
    out = present_attachment_push_event(_attachment())
    assert out == {
        "id": 15,
        "message_id": 40,
        "file_type": "file",
        "account_id": 7,
        "extension": "txt",
        "fallback_title": "presupuesto-octubre.txt",
        "data_url": "/api/backend/api/v1/accounts/7/attachments/15",
        "thumb_url": "",
    }


@pytest.mark.parametrize(
    "file_type",
    [
        FILE_TYPE_IMAGE,
        FILE_TYPE_VIDEO,
        FILE_TYPE_FILE,
        FILE_TYPE_SHARE,
        FILE_TYPE_STORY_MENTION,
        FILE_TYPE_IG_REEL,
        FILE_TYPE_IG_POST,
        FILE_TYPE_IG_STORY,
    ],
)
def test_every_default_branch_type_is_a_superset_of_chatwoot(file_type):
    out = present_attachment_push_event(
        _attachment(file_type=file_type, fallback_title="foto.png", extension="png")
    )
    # Chatwoot's keys, untouched…
    assert {"data_url", "thumb_url"} | BASE_KEYS <= out.keys()
    assert out["thumb_url"] == ""
    # …plus the name a client needs to label the download.
    assert out["fallback_title"] == "foto.png"
    assert out["extension"] == "png"


def test_audio_keeps_its_transcript_and_gains_the_name():
    out = present_attachment_push_event(
        _attachment(
            file_type=FILE_TYPE_AUDIO,
            fallback_title="nota-de-voz.ogg",
            extension="ogg",
            meta={"transcribed_text": "hola"},
        )
    )
    assert out["transcribed_text"] == "hola"
    assert out["thumb_url"] == ""
    assert out["extension"] == "ogg"
    assert out["fallback_title"] == "nota-de-voz.ogg"


def test_a_file_without_a_stored_name_presents_null():
    """Legacy rows and inbound media may have no name; the key is still
    there (null) so a client can fall back on its own label."""
    out = present_attachment_push_event(_attachment(fallback_title=None, extension=None))
    assert out["fallback_title"] is None
    assert out["extension"] is None


def test_an_external_url_passes_through_unchanged():
    out = present_attachment_push_event(
        _attachment(external_url="https://cdn.example.com/a.png", file_type=FILE_TYPE_IMAGE)
    )
    assert out["data_url"] == "https://cdn.example.com/a.png"


@pytest.mark.parametrize(
    ("file_type", "keys"),
    [
        (FILE_TYPE_LOCATION, {"coordinates_lat", "coordinates_long", "fallback_title", "data_url"}),
        (FILE_TYPE_FALLBACK, {"fallback_title", "data_url"}),
        (FILE_TYPE_CONTACT, {"fallback_title", "meta"}),
        (FILE_TYPE_EMBED, {"data_url"}),
    ],
)
def test_non_blob_types_keep_their_exact_shape(file_type, keys):
    out = present_attachment_push_event(_attachment(file_type=file_type))
    assert out.keys() == BASE_KEYS | keys
