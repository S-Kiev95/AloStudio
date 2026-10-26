"""Facebook Page adapter: publishes to a Page through the Graph API.

Written from Meta's Pages API reference (page feed, photos and videos
endpoints) with the Page access token the Facebook channel already
stores. Shapes:

  * text only            → ``POST /{page-id}/feed`` (``message``, ``link``)
  * one image            → ``POST /{page-id}/photos`` (``url``, ``message``)
  * several images       → each ``POST /{page-id}/photos`` with
                           ``published=false``, then ``POST /{page-id}/feed``
                           with ``attached_media``
  * one video            → ``POST /{page-id}/videos`` (``file_url``,
                           ``description``) on the video host

Publishing needs the ``pages_manage_posts`` permission on the Page token;
without it Meta answers with a permission error, which is reported to the
user in plain words instead of raised.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.inboxes.models import CHANNEL_TYPE_FACEBOOK, FacebookPage, Inbox
from app.domains.publishing.adapters.base import (
    PublishingAdapter,
    PublishResult,
    target_text,
)
from app.domains.publishing.models import Publication, PublicationTarget

log = logging.getLogger(__name__)

GRAPH_HOST = "https://graph.facebook.com"
GRAPH_VIDEO_HOST = "https://graph-video.facebook.com"
MESSAGE_MAX = 63206
IMAGES_MAX = 10

# Graph error codes (see Meta's "Handling Errors" reference).
_TOKEN_ERROR_CODES = {190}
_RATE_LIMIT_CODES = {4, 17, 32, 613, 80001}
_TRANSIENT_CODES = {1, 2}
_PERMISSION_CODES = {10} | set(range(200, 300))

_URL_RE = re.compile(r"https?://\S+")


class _GraphError(Exception):
    def __init__(self, result: PublishResult) -> None:
        super().__init__(result.error_message)
        self.result = result


def _graph_error(status: int, payload: Any) -> PublishResult:
    """Map a Graph error response to a result the user can act on."""
    err = payload.get("error", {}) if isinstance(payload, dict) else {}
    code = err.get("code")
    meta_message = err.get("message") or ""
    if code in _TOKEN_ERROR_CODES:
        return PublishResult(
            ok=False,
            error_code=str(code),
            error_message=(
                "La conexión con la página de Facebook venció. "
                "Volvé a conectarla."
            ),
        )
    if code in _PERMISSION_CODES:
        return PublishResult(
            ok=False,
            error_code=str(code),
            error_message=(
                "La página no dio permiso para publicar (pages_manage_posts). "
                "Volvé a conectarla o esperá la aprobación de Meta."
            ),
        )
    if code in _RATE_LIMIT_CODES:
        return PublishResult(
            ok=False,
            error_code=str(code),
            error_message="Facebook limitó las publicaciones por ahora; se reintenta más tarde.",
            retryable=True,
        )
    if code in _TRANSIENT_CODES or status >= 500:
        return PublishResult(
            ok=False,
            error_code=str(code or status),
            error_message="Facebook tuvo un error temporal; se reintenta más tarde.",
            retryable=True,
        )
    return PublishResult(
        ok=False,
        error_code=str(code or status),
        error_message=f"Facebook rechazó la publicación: {meta_message}".strip(),
    )


class FacebookPageAdapter(PublishingAdapter):
    network = "facebook_page"

    def supports(self, inbox: Inbox) -> bool:
        return inbox.channel_type == CHANNEL_TYPE_FACEBOOK

    def validate(
        self, publication: Publication, target: PublicationTarget
    ) -> list[str]:
        errors: list[str] = []
        media = publication.media or []
        text = target_text(publication, target)
        if not text.strip() and not media:
            errors.append("Facebook necesita texto o al menos una imagen o video.")
        if len(text) > MESSAGE_MAX:
            errors.append(
                f"El texto para Facebook supera los {MESSAGE_MAX} caracteres."
            )
        videos = [m for m in media if m["type"] == "video"]
        if videos and len(media) > 1:
            errors.append(
                "En Facebook un video se publica solo, sin otras imágenes ni videos."
            )
        elif len(media) > IMAGES_MAX:
            errors.append(
                f"Facebook admite hasta {IMAGES_MAX} imágenes por publicación."
            )
        return errors

    async def publish(
        self,
        session: AsyncSession,
        publication: Publication,
        target: PublicationTarget,
    ) -> PublishResult:
        inbox = await session.get(Inbox, target.inbox_id)
        page = (
            await session.get(FacebookPage, inbox.channel_id)
            if inbox is not None
            else None
        )
        if page is None or not page.page_access_token:
            return PublishResult(
                ok=False,
                error_code="missing_page",
                error_message="La página de Facebook ya no está conectada.",
            )

        version = get_settings().meta_graph_api_version
        api = _Graph(
            base=f"{GRAPH_HOST}/{version}",
            video_base=f"{GRAPH_VIDEO_HOST}/{version}",
            token=page.page_access_token,
        )
        text = target_text(publication, target)
        media = publication.media or []
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                api.client = client
                if media and media[0]["type"] == "video":
                    post_id = await api.post_video(
                        page.page_id, media[0]["url"], text
                    )
                elif len(media) == 1:
                    post_id = await api.post_photo(
                        page.page_id, media[0]["url"], text
                    )
                elif media:
                    post_id = await api.post_album(
                        page.page_id, [m["url"] for m in media], text
                    )
                else:
                    post_id = await api.post_text(page.page_id, text)
                permalink = await api.permalink(post_id)
        except _GraphError as exc:
            return exc.result
        except httpx.TimeoutException as exc:
            # The request may have reached Meta: sending it again could
            # publish twice, so this needs a human look, not a retry.
            log.warning(
                "publishing.facebook.timeout target_id=%s err=%s", target.id, exc
            )
            return PublishResult(
                ok=False,
                error_code="timeout",
                error_message=(
                    "Facebook no respondió a tiempo y no se sabe si salió. "
                    "Revisá la página antes de reintentar."
                ),
            )
        except httpx.HTTPError as exc:
            log.warning(
                "publishing.facebook.transport_error target_id=%s err=%s",
                target.id,
                exc,
            )
            return PublishResult(
                ok=False,
                error_code="transport_error",
                error_message="No se pudo conectar con Facebook; se reintenta más tarde.",
                retryable=True,
            )
        return PublishResult(ok=True, external_id=post_id, permalink=permalink)


class _Graph:
    """Minimal Graph client bound to one Page token."""

    def __init__(self, *, base: str, video_base: str, token: str) -> None:
        self.base = base
        self.video_base = video_base
        self.token = token
        self.client: httpx.AsyncClient | None = None

    async def _request(
        self,
        method: str,
        url: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert self.client is not None
        # The token rides in the form body on POST (kept out of logged URLs),
        # and in the query on GET, as the Instagram publisher does.
        if method == "POST":
            data = {**(data or {}), "access_token": self.token}
        else:
            params = {**(params or {}), "access_token": self.token}
        resp = await self.client.request(method, url, params=params, data=data)
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        if resp.status_code >= 400 or (
            isinstance(payload, dict) and "error" in payload
        ):
            raise _GraphError(_graph_error(resp.status_code, payload))
        return payload if isinstance(payload, dict) else {}

    async def post_text(self, page_id: str, text: str) -> str:
        data: dict[str, Any] = {"message": text}
        link = _URL_RE.search(text)
        if link:
            data["link"] = link.group(0)
        res = await self._request("POST", f"{self.base}/{page_id}/feed", data)
        return str(res["id"])

    async def post_photo(self, page_id: str, url: str, text: str) -> str:
        data: dict[str, Any] = {"url": url}
        if text:
            data["message"] = text
        res = await self._request("POST", f"{self.base}/{page_id}/photos", data)
        # ``post_id`` is the feed story; ``id`` alone is the photo object.
        return str(res.get("post_id") or res["id"])

    async def post_album(self, page_id: str, urls: list[str], text: str) -> str:
        data: dict[str, Any] = {}
        for i, url in enumerate(urls):
            photo = await self._request(
                "POST",
                f"{self.base}/{page_id}/photos",
                {"url": url, "published": "false"},
            )
            data[f"attached_media[{i}]"] = json.dumps(
                {"media_fbid": str(photo["id"])}
            )
        if text:
            data["message"] = text
        res = await self._request("POST", f"{self.base}/{page_id}/feed", data)
        return str(res["id"])

    async def post_video(self, page_id: str, url: str, text: str) -> str:
        data: dict[str, Any] = {"file_url": url}
        if text:
            data["description"] = text
        res = await self._request(
            "POST", f"{self.video_base}/{page_id}/videos", data
        )
        return str(res["id"])

    async def permalink(self, object_id: str) -> str | None:
        """Best-effort: the post is already out, so a missing permalink
        (Graph error or network failure) never fails the publish."""
        try:
            res = await self._request(
                "GET",
                f"{self.base}/{object_id}",
                params={"fields": "permalink_url"},
            )
        except (_GraphError, httpx.HTTPError):
            return None
        link = res.get("permalink_url")
        if isinstance(link, str) and link.startswith("/"):
            link = f"https://www.facebook.com{link}"
        return link if isinstance(link, str) else None


__all__ = ["FacebookPageAdapter"]
