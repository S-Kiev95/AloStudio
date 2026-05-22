"""Instagram Graph comments — HTTP client for moderation (I.7).

Pure functions that talk to Meta's comment edges. Like
:mod:`app.domains.instagram.publisher` they never raise — every call
returns a structured result so the service layer can drive persistence
+ surface errors deterministically.

Endpoints (Facebook Login flow, host ``graph.facebook.com``, version
pinned via ``settings.meta_graph_api_version``):

  * ``GET    /{ig-media-id}/comments``    → list (top-level + replies)
  * ``POST   /{ig-media-id}/comments``    → post a comment
  * ``POST   /{ig-comment-id}/replies``   → reply to a comment
  * ``POST   /{ig-comment-id}`` (hide=…)  → hide / unhide
  * ``DELETE /{ig-comment-id}``           → delete

Requires the ``instagram_manage_comments`` scope on the Page token
(``InstagramChannel.access_token``). See PLAN.instagram-graph.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.domains.inboxes.models import InstagramChannel

log = logging.getLogger(__name__)

# Field expansion for the list call — top-level comment metadata plus a
# one-level ``replies`` expansion (Meta only nests one level deep).
_COMMENT_FIELDS = "id,text,username,timestamp,hidden,from"
_LIST_FIELDS = (
    f"{_COMMENT_FIELDS},replies{{{_COMMENT_FIELDS}}}"
)


# ---------------------------------------------------------------------------
# Result objects
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class CommentNode:
    """One flattened comment (a top-level comment or a reply)."""

    ig_comment_id: str
    text: str | None = None
    username: str | None = None
    from_id: str | None = None
    hidden: bool = False
    timestamp: str | None = None
    parent_comment_id: str | None = None


@dataclass(slots=True)
class CommentsListResult:
    ok: bool
    comments: list[CommentNode] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class CommentWriteResult:
    ok: bool
    ig_comment_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class CommentActionResult:
    ok: bool
    error_code: str | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------
def _base() -> str:
    # Host is task-local (Facebook vs Instagram Login) — see graph.py.
    from app.domains.instagram.graph import graph_base

    return graph_base()


def _object_url(object_id: str) -> str:
    return f"{_base()}/{object_id}"


# ---------------------------------------------------------------------------
# Error extraction (mirrors publisher._extract_error)
# ---------------------------------------------------------------------------
def _extract_error(resp: httpx.Response) -> tuple[str | None, str | None]:
    try:
        payload = resp.json()
    except ValueError:
        return str(resp.status_code), resp.text[:500]
    err = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(err, dict):
        return str(resp.status_code), resp.text[:500]
    code = err.get("code")
    subcode = err.get("error_subcode")
    message = err.get("message", "")
    code_str = str(code) if code is not None else str(resp.status_code)
    if subcode is not None:
        message = f"{message} (subcode {subcode})"
    return code_str, message[:500]


def _node_from_payload(
    raw: dict[str, Any], *, parent_comment_id: str | None
) -> CommentNode | None:
    cid = raw.get("id")
    if not cid:
        return None
    frm = raw.get("from") if isinstance(raw.get("from"), dict) else {}
    username = raw.get("username") or frm.get("username")
    return CommentNode(
        ig_comment_id=str(cid),
        text=raw.get("text"),
        username=username,
        from_id=(str(frm["id"]) if frm.get("id") else None),
        hidden=bool(raw.get("hidden", False)),
        timestamp=raw.get("timestamp"),
        parent_comment_id=parent_comment_id,
    )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
async def fetch_comments(
    channel: InstagramChannel, *, ig_media_id: str
) -> CommentsListResult:
    """``GET /{ig-media-id}/comments`` with a one-level ``replies``
    expansion. Flattens the tree into a single list — replies carry
    ``parent_comment_id`` pointing at their top-level comment."""
    if not channel.access_token:
        return CommentsListResult(
            ok=False,
            error_code="missing_access_token",
            error_message="channel has no access token",
        )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{_object_url(ig_media_id)}/comments",
                params={
                    "fields": _LIST_FIELDS,
                    "access_token": channel.access_token,
                },
            )
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        return CommentsListResult(
            ok=False,
            error_code="transport_error",
            error_message=str(exc)[:500],
        )
    if resp.status_code >= 400:
        code, message = _extract_error(resp)
        return CommentsListResult(
            ok=False, error_code=code, error_message=message
        )
    try:
        payload = resp.json()
    except ValueError:
        return CommentsListResult(
            ok=False, error_code="bad_json", error_message=resp.text[:500]
        )

    out: list[CommentNode] = []
    data = payload.get("data") if isinstance(payload, dict) else None
    for raw in data or []:
        if not isinstance(raw, dict):
            continue
        top = _node_from_payload(raw, parent_comment_id=None)
        if top is None:
            continue
        out.append(top)
        replies = raw.get("replies")
        reply_data = (
            replies.get("data") if isinstance(replies, dict) else None
        )
        for r in reply_data or []:
            if not isinstance(r, dict):
                continue
            node = _node_from_payload(
                r, parent_comment_id=top.ig_comment_id
            )
            if node is not None:
                out.append(node)
    return CommentsListResult(ok=True, comments=out)


# ---------------------------------------------------------------------------
# Write — post + reply
# ---------------------------------------------------------------------------
async def _post_message(
    channel: InstagramChannel, *, edge_url: str, message: str
) -> CommentWriteResult:
    if not channel.access_token:
        return CommentWriteResult(
            ok=False,
            error_code="missing_access_token",
            error_message="channel has no access token",
        )
    body = {"message": message, "access_token": channel.access_token}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(edge_url, data=body)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        return CommentWriteResult(
            ok=False,
            error_code="transport_error",
            error_message=str(exc)[:500],
        )
    if resp.status_code >= 400:
        code, message_err = _extract_error(resp)
        return CommentWriteResult(
            ok=False, error_code=code, error_message=message_err
        )
    try:
        payload = resp.json()
    except ValueError:
        return CommentWriteResult(
            ok=False, error_code="bad_json", error_message=resp.text[:500]
        )
    cid = payload.get("id") if isinstance(payload, dict) else None
    if not cid:
        return CommentWriteResult(
            ok=False,
            error_code="no_comment_id",
            error_message=str(payload)[:500],
        )
    return CommentWriteResult(ok=True, ig_comment_id=str(cid))


async def create_comment(
    channel: InstagramChannel, *, ig_media_id: str, message: str
) -> CommentWriteResult:
    """``POST /{ig-media-id}/comments`` — comment on owned media."""
    return await _post_message(
        channel,
        edge_url=f"{_object_url(ig_media_id)}/comments",
        message=message,
    )


async def create_reply(
    channel: InstagramChannel, *, ig_comment_id: str, message: str
) -> CommentWriteResult:
    """``POST /{ig-comment-id}/replies`` — reply to a comment."""
    return await _post_message(
        channel,
        edge_url=f"{_object_url(ig_comment_id)}/replies",
        message=message,
    )


# ---------------------------------------------------------------------------
# Moderation — hide / unhide + delete
# ---------------------------------------------------------------------------
async def set_hidden(
    channel: InstagramChannel, *, ig_comment_id: str, hide: bool
) -> CommentActionResult:
    """``POST /{ig-comment-id}`` with ``hide=true|false``."""
    if not channel.access_token:
        return CommentActionResult(
            ok=False,
            error_code="missing_access_token",
            error_message="channel has no access token",
        )
    body = {
        "hide": "true" if hide else "false",
        "access_token": channel.access_token,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(_object_url(ig_comment_id), data=body)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        return CommentActionResult(
            ok=False,
            error_code="transport_error",
            error_message=str(exc)[:500],
        )
    if resp.status_code >= 400:
        code, message = _extract_error(resp)
        return CommentActionResult(
            ok=False, error_code=code, error_message=message
        )
    return CommentActionResult(ok=True)


async def delete_comment(
    channel: InstagramChannel, *, ig_comment_id: str
) -> CommentActionResult:
    """``DELETE /{ig-comment-id}`` — owner deletes any comment on its
    media; non-owners only their own."""
    if not channel.access_token:
        return CommentActionResult(
            ok=False,
            error_code="missing_access_token",
            error_message="channel has no access token",
        )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                "DELETE",
                _object_url(ig_comment_id),
                params={"access_token": channel.access_token},
            )
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        return CommentActionResult(
            ok=False,
            error_code="transport_error",
            error_message=str(exc)[:500],
        )
    if resp.status_code >= 400:
        code, message = _extract_error(resp)
        return CommentActionResult(
            ok=False, error_code=code, error_message=message
        )
    return CommentActionResult(ok=True)


__all__ = [
    "CommentActionResult",
    "CommentNode",
    "CommentWriteResult",
    "CommentsListResult",
    "create_comment",
    "create_reply",
    "delete_comment",
    "fetch_comments",
    "set_hidden",
]
