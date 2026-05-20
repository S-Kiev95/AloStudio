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

from app.core.config import get_settings
from app.domains.inboxes.models import InstagramChannel

log = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------
def _base() -> str:
    settings = get_settings()
    return f"https://graph.facebook.com/{settings.meta_graph_api_version}"


def _media_url(channel: InstagramChannel) -> str:
    return f"{_base()}/{channel.instagram_id}/media"


def _publish_url(channel: InstagramChannel) -> str:
    return f"{_base()}/{channel.instagram_id}/media_publish"


def _media_object_url(media_id: str) -> str:
    return f"{_base()}/{media_id}"


# ---------------------------------------------------------------------------
# Error extraction
# ---------------------------------------------------------------------------
def _extract_error(resp: httpx.Response) -> tuple[str | None, str | None]:
    """Pull (code, message) from Meta's error envelope.

    Meta returns ``{"error": {"message": "...", "code": N,
    "error_subcode": M, "fbtrace_id": "..."}}``. We surface code +
    message; the subcode is folded into the message for context."""
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
    "ContainerResult",
    "PublishResult",
    "build_image_container_params",
    "create_container",
    "fetch_permalink",
    "publish_container",
]
