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
from datetime import date
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.inboxes.models import CHANNEL_TYPE_FACEBOOK, FacebookPage, Inbox
from app.domains.publishing.adapters.base import (
    MetricsResult,
    PublishingAdapter,
    PublishResult,
    channel_inbox,
    target_text,
)
from app.domains.publishing.models import (
    Publication,
    PublicationTarget,
    PublishingChannel,
)

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
_MISSING_PAGE = "La página de Facebook ya no está conectada."


class _GraphError(Exception):
    def __init__(self, result: PublishResult, meta_message: str = "") -> None:
        super().__init__(result.error_message)
        self.result = result
        # Meta's own text, for messages other than the publishing ones.
        self.meta_message = meta_message


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


def _metrics_error(exc: _GraphError) -> str:
    """Like :func:`_graph_error`, worded for reading figures."""
    code = exc.result.error_code
    number = int(code) if code and code.isdigit() else None
    if number in _TOKEN_ERROR_CODES:
        return exc.result.error_message or ""
    if number in _PERMISSION_CODES:
        # Not the publishing permission: reading needs its own.
        return "La página no dio permiso para leer estadísticas (pages_read_engagement)."
    if exc.result.retryable:
        return "Facebook no respondió por ahora; se reintenta más tarde."
    return f"Facebook no devolvió estadísticas: {exc.meta_message}".strip()


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
        page, api = await self._page_api(session, target.channel_id)
        if page is None or api is None:
            return PublishResult(
                ok=False,
                error_code="missing_page",
                error_message=_MISSING_PAGE,
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

    async def fetch_post_metrics(
        self, session: AsyncSession, target: PublicationTarget
    ) -> MetricsResult | None:
        if not target.external_id:
            return None
        _page, api = await self._page_api(session, target.channel_id)
        if api is None:
            return MetricsResult(ok=False, error_message=_MISSING_PAGE)
        publication = await session.get(Publication, target.publication_id)
        is_video = any(
            item.get("type") == "video" for item in (publication.media if publication else [])
        )
        object_id = target.external_id
        return await self._read(api, lambda: api.post_metrics(object_id, is_video=is_video))

    async def fetch_channel_metrics(
        self, session: AsyncSession, channel: PublishingChannel, *, days: list[date]
    ) -> MetricsResult | None:
        # Only the follower count: the Page's daily reach lives in its
        # insights, which need ``read_insights`` (not requested yet).
        page, api = await self._page_api(session, channel.id)  # type: ignore[arg-type]
        if page is None or api is None:
            return MetricsResult(ok=False, error_message=_MISSING_PAGE)
        return await self._read(api, lambda: api.page_metrics(page.page_id))

    @staticmethod
    async def _read(api: _Graph, call: Any) -> MetricsResult:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                api.client = client
                metrics = await call()
        except _GraphError as exc:
            return MetricsResult(ok=False, error_message=_metrics_error(exc))
        except httpx.HTTPError:
            return MetricsResult(
                ok=False, error_message="No se pudo conectar con Facebook."
            )
        return MetricsResult(ok=True, metrics=metrics)

    @staticmethod
    async def _page_api(
        session: AsyncSession, channel_id: int
    ) -> tuple[FacebookPage | None, _Graph | None]:
        inbox = await channel_inbox(session, channel_id)
        page = (
            await session.get(FacebookPage, inbox.channel_id)
            if inbox is not None
            else None
        )
        if page is None or not page.page_access_token:
            return page, None
        version = get_settings().meta_graph_api_version
        return page, _Graph(
            base=f"{GRAPH_HOST}/{version}",
            video_base=f"{GRAPH_VIDEO_HOST}/{version}",
            token=page.page_access_token,
        )


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
            err = payload.get("error", {}) if isinstance(payload, dict) else {}
            raise _GraphError(
                _graph_error(resp.status_code, payload),
                str(err.get("message") or "") if isinstance(err, dict) else "",
            )
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

    async def post_metrics(self, object_id: str, *, is_video: bool) -> dict[str, int]:
        """Reactions, comments and shares from the post's edges (needs
        ``pages_read_engagement``), plus views and reach from its insights
        when ``read_insights`` allows it. Reactions are reported as
        ``likes``. ``post_media_view`` / ``post_total_media_view_unique``
        replace the ``post_impressions*`` metrics Meta retires after v25;
        a video is a video object, which has no ``post_*`` insights."""
        counts = "comments.limit(0).summary(true),reactions.limit(0).summary(true)"
        try:
            res = await self._request(
                "GET", f"{self.base}/{object_id}", params={"fields": f"shares,{counts}"}
            )
            # Facebook leaves ``shares`` out when nobody shared the post.
            shares: int | None = (res.get("shares") or {}).get("count", 0)
        except _GraphError as exc:
            # Videos have no ``shares`` field (error 100); anything else
            # is a real failure.
            if exc.result.error_code != "100":
                raise
            res = await self._request(
                "GET", f"{self.base}/{object_id}", params={"fields": counts}
            )
            shares = None

        metrics: dict[str, int] = {}
        for key, edge in (("likes", "reactions"), ("comments", "comments")):
            total = ((res.get(edge) or {}).get("summary") or {}).get("total_count")
            if isinstance(total, int):
                metrics[key] = total
        if isinstance(shares, int):
            metrics["shares"] = shares
        metrics["interactions"] = sum(
            metrics.get(k, 0) for k in ("likes", "comments", "shares")
        )

        if is_video:
            return metrics
        try:
            insights = await self._request(
                "GET",
                f"{self.base}/{object_id}/insights",
                params={"metric": "post_media_view,post_total_media_view_unique"},
            )
        except _GraphError:
            return metrics
        names = {"post_media_view": "views", "post_total_media_view_unique": "reach"}
        for item in insights.get("data") or []:
            values = item.get("values") if isinstance(item, dict) else None
            value = values[0].get("value") if values else None
            if item.get("name") in names and isinstance(value, int):
                metrics[names[item["name"]]] = value
        return metrics

    async def page_metrics(self, page_id: str) -> dict[str, int]:
        """The Page's follower count (``fan_count`` on older Pages)."""
        res = await self._request(
            "GET",
            f"{self.base}/{page_id}",
            params={"fields": "followers_count,fan_count"},
        )
        followers = res.get("followers_count")
        if not isinstance(followers, int):
            followers = res.get("fan_count")
        return {"followers": followers} if isinstance(followers, int) else {}


__all__ = ["FacebookPageAdapter"]
