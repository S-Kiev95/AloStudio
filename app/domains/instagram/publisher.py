"""Instagram Graph publishing — HTTP client for the Meta API.

Pure functions that talk to Meta's Graph API. They never raise on
transport / 4xx / 5xx — every call returns a structured result so the
ARQ task can drive the state machine deterministically.

Endpoints (Facebook Login flow, host ``graph.facebook.com``, version
pinned via ``settings.meta_graph_api_version``):

  * ``POST /{ig-user-id}/media``          → create a container
  * ``POST /{ig-user-id}/media_publish``  → publish a FINISHED container
  * ``GET  /{ig-media-id}?fields=permalink`` → fetch the public URL

``ig-user-id`` is the IG Business Account id, stored on
``InstagramChannel.instagram_id`` (Phase 5e). The Page access token
is ``InstagramChannel.access_token``.

Container-param building is generic (takes a dict) so the same
``create_container`` serves single-image (I.2), video/reels (I.3),
carousel children + parent (I.4) and stories (I.5).

References: PLAN.instagram-graph.md (verified spec).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.domains.inboxes.models import InstagramChannel

log = logging.getLogger(__name__)

# Meta throttling error codes (verified spec, PLAN.instagram-graph.md):
#   4     — application-level rate limit
#   17    — user-level rate limit
#   80001 — Page Business-Use-Case rate limit
#   80002 — Instagram Business-Use-Case rate limit
THROTTLE_ERROR_CODES: frozenset[str] = frozenset(
    {"4", "17", "80001", "80002"}
)


def is_throttle_error(error_code: str | None) -> bool:
    """True when ``error_code`` is one of Meta's documented throttle
    codes — the signal for the worker to back off + retry."""
    return error_code in THROTTLE_ERROR_CODES


# ---------------------------------------------------------------------------
# Result objects
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class ContainerResult:
    ok: bool
    container_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class PublishResult:
    ok: bool
    ig_media_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class DeleteResult:
    ok: bool
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class QuotaResult:
    ok: bool
    quota_usage: int | None = None
    quota_total: int | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def exceeded(self) -> bool:
        """True when usage has reached the 24h publishing cap."""
        return (
            self.ok
            and self.quota_usage is not None
            and self.quota_total is not None
            and self.quota_usage >= self.quota_total
        )


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------
def _base() -> str:
    # Host is task-local (Facebook vs Instagram Login) — see graph.py.
    from app.domains.instagram.graph import graph_base

    return graph_base()


def _media_url(channel: InstagramChannel) -> str:
    return f"{_base()}/{channel.instagram_id}/media"


def _publish_url(channel: InstagramChannel) -> str:
    return f"{_base()}/{channel.instagram_id}/media_publish"


def _media_object_url(media_id: str) -> str:
    return f"{_base()}/{media_id}"


# ---------------------------------------------------------------------------
# Error extraction
# ---------------------------------------------------------------------------
def _usage_note(resp: httpx.Response) -> str:
    """Surface Meta's rate-limit usage headers (``X-App-Usage`` +
    ``X-Business-Use-Case-Usage``) so a throttle failure records *how*
    saturated the app/BUC was at the time. Empty when neither header
    is present (the common, non-throttled case)."""
    parts: list[str] = []
    app_usage = resp.headers.get("X-App-Usage")
    buc_usage = resp.headers.get("X-Business-Use-Case-Usage")
    if app_usage:
        parts.append(f"X-App-Usage={app_usage}")
    if buc_usage:
        parts.append(f"X-Business-Use-Case-Usage={buc_usage}")
    return f" [usage {'; '.join(parts)}]" if parts else ""


def _extract_error(resp: httpx.Response) -> tuple[str | None, str | None]:
    """Pull (code, message) from Meta's error envelope.

    Meta returns ``{"error": {"message": "...", "code": N,
    "error_subcode": M, "fbtrace_id": "..."}}``. We surface code +
    message; the subcode is folded into the message for context, and
    rate-limit usage headers are appended when present."""
    usage = _usage_note(resp)
    try:
        payload = resp.json()
    except ValueError:
        return str(resp.status_code), (resp.text[:500] + usage)
    err = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(err, dict):
        return str(resp.status_code), (resp.text[:500] + usage)
    code = err.get("code")
    subcode = err.get("error_subcode")
    message = err.get("message", "")
    code_str = str(code) if code is not None else str(resp.status_code)
    if subcode is not None:
        message = f"{message} (subcode {subcode})"
    return code_str, (message + usage)[:600]


# ---------------------------------------------------------------------------
# Container creation
# ---------------------------------------------------------------------------
def build_image_container_params(
    *,
    image_url: str,
    caption: str | None = None,
    is_carousel_item: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Param dict for a single image (or carousel image child).

    Caption is omitted on carousel children (Meta rejects it there).
    """
    params: dict[str, Any] = {"image_url": image_url}
    if is_carousel_item:
        params["is_carousel_item"] = "true"
    elif caption:
        params["caption"] = caption
    if extra:
        params.update(extra)
    return params


def build_video_container_params(
    *,
    media_type: str,
    video_url: str,
    caption: str | None = None,
    cover_url: str | None = None,
    thumb_offset: int | None = None,
    share_to_feed: bool | None = None,
    audio_name: str | None = None,
    is_carousel_item: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Param dict for a VIDEO or REELS container (or video carousel
    child).

    ``media_type`` is ``"VIDEO"`` or ``"REELS"`` — Meta requires it on
    video containers (unlike single images, where the param is
    omitted). ``video_url`` is mandatory.

    Optional params per the verified spec (PLAN.instagram-graph.md):

      * ``caption``      — feed caption (omitted on carousel children)
      * ``cover_url``    — REELS cover image (overrides ``thumb_offset``)
      * ``thumb_offset`` — VIDEO thumbnail offset in ms
      * ``share_to_feed``— REELS: also surface in the main feed grid
      * ``audio_name``   — REELS: name the audio track (write-once)

    Booleans are serialised to Meta's ``"true"``/``"false"`` strings
    because the request is form-encoded.
    """
    params: dict[str, Any] = {
        "media_type": media_type,
        "video_url": video_url,
    }
    if is_carousel_item:
        params["is_carousel_item"] = "true"
    elif caption:
        params["caption"] = caption
    if cover_url:
        params["cover_url"] = cover_url
    if thumb_offset is not None:
        params["thumb_offset"] = thumb_offset
    if share_to_feed is not None:
        params["share_to_feed"] = "true" if share_to_feed else "false"
    if audio_name:
        params["audio_name"] = audio_name
    if extra:
        params.update(extra)
    return params


def build_story_container_params(
    *,
    image_url: str | None = None,
    video_url: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Param dict for a STORIES container (image or video).

    Stories always carry ``media_type=STORIES`` and take exactly one
    of ``image_url`` / ``video_url`` (video wins if both are present —
    callers validate upstream). Captions don't apply to stories, so
    none is accepted here.
    """
    params: dict[str, Any] = {"media_type": "STORIES"}
    if video_url:
        params["video_url"] = video_url
    elif image_url:
        params["image_url"] = image_url
    if extra:
        params.update(extra)
    return params


async def create_container(
    channel: InstagramChannel,
    *,
    params: dict[str, Any],
) -> ContainerResult:
    """``POST /{ig-user-id}/media`` — create one container.

    ``params`` is the full Meta param set for the media type. The
    access token is appended automatically. Returns a
    :class:`ContainerResult` — never raises.
    """
    if not channel.access_token:
        return ContainerResult(
            ok=False,
            error_code="missing_access_token",
            error_message="channel has no access token",
        )
    if not channel.instagram_id:
        return ContainerResult(
            ok=False,
            error_code="missing_ig_user_id",
            error_message="channel has no instagram_id",
        )

    body = {**params, "access_token": channel.access_token}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(_media_url(channel), data=body)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "instagram.publish.container.transport_error channel_id=%s err=%s",
            channel.id,
            exc,
        )
        return ContainerResult(
            ok=False,
            error_code="transport_error",
            error_message=str(exc)[:500],
        )

    if resp.status_code >= 400:
        code, message = _extract_error(resp)
        log.warning(
            "instagram.publish.container.api_error channel_id=%s code=%s msg=%s",
            channel.id,
            code,
            message,
        )
        return ContainerResult(
            ok=False, error_code=code, error_message=message
        )

    try:
        payload = resp.json()
    except ValueError:
        return ContainerResult(
            ok=False,
            error_code="bad_json",
            error_message=resp.text[:500],
        )
    container_id = (
        payload.get("id") if isinstance(payload, dict) else None
    )
    if not container_id:
        return ContainerResult(
            ok=False,
            error_code="no_container_id",
            error_message=str(payload)[:500],
        )
    return ContainerResult(ok=True, container_id=str(container_id))


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------
async def publish_container(
    channel: InstagramChannel,
    *,
    creation_id: str,
) -> PublishResult:
    """``POST /{ig-user-id}/media_publish`` — publish a FINISHED
    container. Returns the ig_media_id on success."""
    if not channel.access_token:
        return PublishResult(
            ok=False,
            error_code="missing_access_token",
            error_message="channel has no access token",
        )

    body = {
        "creation_id": creation_id,
        "access_token": channel.access_token,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(_publish_url(channel), data=body)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "instagram.publish.media_publish.transport_error channel_id=%s err=%s",
            channel.id,
            exc,
        )
        return PublishResult(
            ok=False,
            error_code="transport_error",
            error_message=str(exc)[:500],
        )

    if resp.status_code >= 400:
        code, message = _extract_error(resp)
        log.warning(
            "instagram.publish.media_publish.api_error channel_id=%s code=%s msg=%s",
            channel.id,
            code,
            message,
        )
        return PublishResult(
            ok=False, error_code=code, error_message=message
        )

    try:
        payload = resp.json()
    except ValueError:
        return PublishResult(
            ok=False,
            error_code="bad_json",
            error_message=resp.text[:500],
        )
    media_id = payload.get("id") if isinstance(payload, dict) else None
    if not media_id:
        return PublishResult(
            ok=False,
            error_code="no_media_id",
            error_message=str(payload)[:500],
        )
    return PublishResult(ok=True, ig_media_id=str(media_id))


# ---------------------------------------------------------------------------
# Delete media (I.6)
# ---------------------------------------------------------------------------
async def delete_media(
    channel: InstagramChannel, *, ig_media_id: str
) -> DeleteResult:
    """``DELETE /{ig-media-id}`` — remove a published media object.

    Per the verified spec this works for organic feed posts, stories,
    reels and **whole** carousels — but Meta rejects deleting an
    individual carousel child, an ad-promoted post, or a live video
    (the call comes back 4xx, surfaced here as ``ok=False`` + the
    Meta error code/message). Never raises.
    """
    if not channel.access_token:
        return DeleteResult(
            ok=False,
            error_code="missing_access_token",
            error_message="channel has no access token",
        )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                "DELETE",
                _media_object_url(ig_media_id),
                params={"access_token": channel.access_token},
            )
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "instagram.delete.transport_error channel_id=%s err=%s",
            channel.id,
            exc,
        )
        return DeleteResult(
            ok=False,
            error_code="transport_error",
            error_message=str(exc)[:500],
        )

    if resp.status_code >= 400:
        code, message = _extract_error(resp)
        log.warning(
            "instagram.delete.api_error channel_id=%s code=%s msg=%s",
            channel.id,
            code,
            message,
        )
        return DeleteResult(ok=False, error_code=code, error_message=message)
    return DeleteResult(ok=True)


# ---------------------------------------------------------------------------
# Publishing quota (I.9) — GET /{ig-user-id}/content_publishing_limit
# ---------------------------------------------------------------------------
async def fetch_publishing_limit(
    channel: InstagramChannel,
) -> QuotaResult:
    """``GET /{ig-user-id}/content_publishing_limit`` — current 24h
    publish usage vs the cap (100/account). Never raises; an
    unreachable / errored quota call comes back ``ok=False`` so the
    caller can treat the check as best-effort and proceed."""
    if not channel.access_token or not channel.instagram_id:
        return QuotaResult(
            ok=False,
            error_code="missing_credentials",
            error_message="channel missing access token or instagram_id",
        )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{_base()}/{channel.instagram_id}/content_publishing_limit",
                params={
                    "fields": "quota_usage,config",
                    "access_token": channel.access_token,
                },
            )
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        return QuotaResult(
            ok=False,
            error_code="transport_error",
            error_message=str(exc)[:500],
        )
    if resp.status_code >= 400:
        code, message = _extract_error(resp)
        return QuotaResult(ok=False, error_code=code, error_message=message)
    try:
        payload = resp.json()
    except ValueError:
        return QuotaResult(
            ok=False, error_code="bad_json", error_message=resp.text[:500]
        )
    data = payload.get("data") if isinstance(payload, dict) else None
    row = data[0] if isinstance(data, list) and data else None
    if not isinstance(row, dict):
        return QuotaResult(
            ok=False,
            error_code="no_quota_data",
            error_message=str(payload)[:500],
        )
    usage = row.get("quota_usage")
    config = row.get("config") if isinstance(row.get("config"), dict) else {}
    total = config.get("quota_total")
    return QuotaResult(
        ok=True,
        quota_usage=int(usage) if usage is not None else None,
        quota_total=int(total) if total is not None else None,
    )


# ---------------------------------------------------------------------------
# Permalink fetch (best-effort — not fatal if it fails)
# ---------------------------------------------------------------------------
async def fetch_permalink(
    channel: InstagramChannel, *, ig_media_id: str
) -> str | None:
    """``GET /{ig-media-id}?fields=permalink`` — best-effort. Returns
    None on any failure (the post is already published; the permalink
    is just a nicety for the dashboard)."""
    if not channel.access_token:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _media_object_url(ig_media_id),
                params={
                    "fields": "permalink",
                    "access_token": channel.access_token,
                },
            )
    except (httpx.RequestError, httpx.TimeoutException):
        return None
    if resp.status_code >= 400:
        return None
    try:
        payload = resp.json()
    except ValueError:
        return None
    return (
        payload.get("permalink") if isinstance(payload, dict) else None
    )


__all__ = [
    "THROTTLE_ERROR_CODES",
    "ContainerResult",
    "DeleteResult",
    "PublishResult",
    "QuotaResult",
    "build_image_container_params",
    "build_story_container_params",
    "build_video_container_params",
    "create_container",
    "delete_media",
    "fetch_permalink",
    "fetch_publishing_limit",
    "is_throttle_error",
    "publish_container",
]
