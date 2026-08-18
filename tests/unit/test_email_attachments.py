"""Pulling a message's files back out of the store for an outgoing email.

Email is the one channel that needs the bytes — the others are handed a
signed URL and fetch it themselves — so this is the only place a storage
failure can reach a customer. Every failure is non-fatal on purpose: the
reply is what the agent wrote and someone is waiting for it, so a file
that cannot be fetched is skipped and the mail still goes.
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
import respx

from app.domains.email.attachments import (
    MAX_ATTACHMENT_BYTES,
    fetch_attachments,
)

pytestmark = pytest.mark.unit

URL = "https://store.example.com/bucket/file.png"


def _attachment(**over):
    base = {
        "id": 1,
        "external_url": URL,
        "extension": "png",
        "fallback_title": None,
        "file_type_str": "image",
    }
    base.update(over)
    return SimpleNamespace(**base)


def _ok(content=b"bytes", content_type="image/png"):
    return httpx.Response(
        200, content=content, headers={"content-type": content_type}
    )


@respx.mock
async def test_fetches_the_file():
    respx.get(URL).mock(return_value=_ok(b"PNGDATA"))
    (f,) = await fetch_attachments([_attachment()])
    assert f.content == b"PNGDATA"
    assert (f.maintype, f.subtype) == ("image", "png")


@respx.mock
async def test_names_the_file_something_a_person_can_read():
    respx.get(URL).mock(return_value=_ok())
    (f,) = await fetch_attachments(
        [_attachment(fallback_title="presupuesto.pdf")]
    )
    assert f.filename == "presupuesto.pdf"


@respx.mock
async def test_falls_back_to_a_name_that_still_says_what_it_is():
    respx.get(URL).mock(return_value=_ok())
    (f,) = await fetch_attachments([_attachment(id=7)])
    # Not a bare id: a download called "7" tells the recipient nothing.
    assert f.filename == "image-7.png"


@respx.mock
async def test_a_file_that_cannot_be_fetched_does_not_stop_the_others():
    """The reply matters more than the attachment."""
    other = "https://store.example.com/bucket/ok.pdf"
    respx.get(URL).mock(side_effect=httpx.ConnectError("down"))
    respx.get(other).mock(return_value=_ok(b"PDF", "application/pdf"))

    files = await fetch_attachments(
        [_attachment(), _attachment(id=2, external_url=other, extension="pdf")]
    )
    assert [f.content for f in files] == [b"PDF"]


@respx.mock
async def test_a_storage_error_is_skipped_not_raised():
    respx.get(URL).mock(return_value=httpx.Response(404))
    assert await fetch_attachments([_attachment()]) == []


@respx.mock
async def test_an_oversized_file_is_dropped_rather_than_bouncing_the_mail():
    # Providers reject the whole message over ~25 MB once base64 expands
    # it; losing the file beats losing the reply.
    respx.get(URL).mock(return_value=_ok(b"x" * (MAX_ATTACHMENT_BYTES + 1)))
    assert await fetch_attachments([_attachment()]) == []


@respx.mock
async def test_the_total_size_is_capped_too():
    urls = [f"https://store.example.com/bucket/{i}.bin" for i in range(3)]
    half = MAX_ATTACHMENT_BYTES
    for u in urls:
        respx.get(u).mock(return_value=_ok(b"x" * half, "application/octet-stream"))
    files = await fetch_attachments(
        [
            _attachment(id=i, external_url=u, extension="bin")
            for i, u in enumerate(urls)
        ]
    )
    assert len(files) < 3


@respx.mock
async def test_an_attachment_with_no_file_is_skipped():
    """A location carries coordinates, not something to attach."""
    assert await fetch_attachments([_attachment(external_url=None)]) == []


@respx.mock
async def test_an_unknown_type_is_offered_as_a_download():
    respx.get(URL).mock(return_value=_ok(b"?", content_type=""))
    (f,) = await fetch_attachments([_attachment(extension="weird")])
    # octet-stream makes a client offer it rather than guess wrong and
    # render it as the wrong kind of file.
    assert (f.maintype, f.subtype) == ("application", "octet-stream")


@respx.mock
async def test_the_stores_content_type_wins_over_the_extension():
    respx.get(URL).mock(return_value=_ok(b"%PDF", "application/pdf"))
    (f,) = await fetch_attachments([_attachment(extension="png")])
    assert (f.maintype, f.subtype) == ("application", "pdf")


async def test_a_message_with_nothing_attached_costs_no_request():
    assert await fetch_attachments([]) == []
