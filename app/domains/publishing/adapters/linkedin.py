"""LinkedIn adapter: publishes on a member's own profile.

Written from LinkedIn's documentation (Microsoft Learn):

  * Connecting: "Sign In with LinkedIn using OpenID Connect" for who the
    member is (``GET /v2/userinfo`` → ``sub``, name, picture) plus
    ``w_member_social`` ("Share on LinkedIn") to post. Both products are
    self-serve: no review. Tokens last 60 days; refresh tokens are only
    issued to approved partners, so without one the owner reconnects.
  * Publishing: the versioned Posts API (``POST /rest/posts``, headers
    ``Linkedin-Version`` and ``X-Restli-Protocol-Version: 2.0.0``) with the
    author ``urn:li:person:{sub}``; the new post's URN comes back in the
    ``x-restli-id`` header. Images are uploaded first with the Images API
    (``initializeUpload`` → PUT of the bytes to ``uploadUrl``): one goes as
    ``content.media``, 2–20 as ``content.multiImage``. A video (one, on its
    own) goes through the Videos API: ``initializeUpload`` says which byte
    range goes to each URL, the ETag of each PUT goes to ``finalizeUpload``,
    and LinkedIn processes it before it can be posted as ``content.media``.
  * ``commentary`` is in LinkedIn's "little" text format: its reserved
    characters are escaped so the text goes out as written, except a ``#``
    that starts a word, which LinkedIn turns into a hashtag.

Figures (``r_member_social`` is restricted) are not covered yet.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.publishing.adapters.base import (
    ChannelConnectionError,
    ConnectedAccount,
    Credentials,
    PublishingAdapter,
    PublishResult,
    mark_reconnect,
    target_text,
)
from app.domains.publishing.models import (
    Publication,
    PublicationTarget,
    PublishingChannel,
)

log = logging.getLogger(__name__)

AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
REST_BASE = "https://api.linkedin.com/rest"
SCOPES: tuple[str, ...] = ("openid", "profile", "w_member_social")

TEXT_MAX = 3000
IMAGES_MAX = 20
VIDEO_TITLE_MAX = 100
VIDEO_POLL_SECONDS = 5
VIDEO_POLL_MAX_SECONDS = 300

_RESERVED = set("|{}@[]()<>\\*_~")
_RECONNECT_MESSAGE = "El acceso a LinkedIn venció o se revocó. Volvé a conectar el perfil."
_MISSING_CHANNEL = "El perfil de LinkedIn no está conectado."


def escape_little(text: str) -> str:
    """Escape LinkedIn's reserved characters so ``text`` is posted as written.
    A ``#`` right before a word stays a hashtag; any other ``#`` is escaped."""
    out: list[str] = []
    for i, char in enumerate(text):
        if char in _RESERVED:
            out.append("\\" + char)
        elif char == "#":
            following = text[i + 1] if i + 1 < len(text) else ""
            out.append("#" if following.isalnum() else "\\#")
        else:
            out.append(char)
    return "".join(out)


class _LinkedInError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        retryable: bool = False,
        reconnect: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable
        self.reconnect = reconnect


def _error_of(resp: httpx.Response, *, doing: str) -> _LinkedInError:
    try:
        payload = resp.json()
    except ValueError:
        payload = {}
    detail = payload.get("message") or payload.get("error_description") if isinstance(payload, dict) else None
    status = resp.status_code
    if status == 401:
        return _LinkedInError(_RECONNECT_MESSAGE, code="401", reconnect=True)
    if status == 403:
        return _LinkedInError(
            f"LinkedIn no dio permiso para {doing}. Volvé a conectar el perfil aceptando "
            "todos los permisos.",
            code="403",
        )
    if status == 429 or status >= 500:
        return _LinkedInError(
            "LinkedIn limitó o no respondió las solicitudes por ahora; se reintenta más tarde.",
            code=str(status),
            retryable=True,
        )
    return _LinkedInError(
        f"LinkedIn rechazó la solicitud: {detail or status}".strip(), code=str(status)
    )


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Linkedin-Version": get_settings().linkedin_api_version,
        "X-Restli-Protocol-Version": "2.0.0",
    }


def _token_of(channel: PublishingChannel | None) -> str | None:
    token = (channel.credentials or {}).get("access_token") if channel else None
    return token if isinstance(token, str) and token else None


def _expires_at(payload: dict[str, Any]) -> datetime | None:
    seconds = payload.get("expires_in")
    if isinstance(seconds, int):
        return datetime.now(UTC) + timedelta(seconds=seconds)
    return None


def _video_title(text: str) -> str:
    lines = text.strip().splitlines()
    return lines[0][:VIDEO_TITLE_MAX] if lines else "Video"


async def _upload_parts(
    client: httpx.AsyncClient, source: httpx.Response, parts: list[dict[str, Any]]
) -> list[str]:
    """PUT each part's byte range as the file comes in; the ETags, in order,
    are what ``finalizeUpload`` asks for."""
    stream = source.aiter_bytes()
    buffer = bytearray()
    part_ids: list[str] = []
    for part in parts:
        size = int(part["lastByte"]) - int(part["firstByte"]) + 1
        async for chunk in stream:
            buffer += chunk
            if len(buffer) >= size:
                break
        upload = await client.put(
            part["uploadUrl"],
            content=bytes(buffer[:size]),
            headers={"Content-Type": "application/octet-stream"},
        )
        if upload.status_code >= 400:
            raise _error_of(upload, doing="subir el video")
        etag = upload.headers.get("etag")
        if not etag:
            raise _LinkedInError("LinkedIn no confirmó una parte del video.")
        part_ids.append(etag.strip('"'))
        del buffer[:size]
    return part_ids


async def _wait_until_available(client: httpx.AsyncClient, token: str, video: str) -> None:
    waited = 0
    while True:
        resp = await client.get(
            f"{REST_BASE}/videos/{quote(video, safe='')}", headers=_headers(token)
        )
        if resp.status_code >= 400:
            raise _error_of(resp, doing="revisar el video")
        payload = resp.json() or {}
        status = payload.get("status")
        if status == "AVAILABLE":
            return
        if status == "PROCESSING_FAILED":
            reason = payload.get("processingFailureReason") or "error desconocido"
            raise _LinkedInError(f"LinkedIn no pudo procesar el video: {reason}")
        waited += VIDEO_POLL_SECONDS
        if waited > VIDEO_POLL_MAX_SECONDS:
            raise _LinkedInError(
                "LinkedIn tardó demasiado en procesar el video; se reintenta más tarde.",
                code="processing_timeout",
                retryable=True,
            )
        await asyncio.sleep(VIDEO_POLL_SECONDS)


class LinkedInAdapter(PublishingAdapter):
    network = "linkedin"
    label = "LinkedIn"

    # -- Connecting ---------------------------------------------------------
    def missing_connection_settings(self) -> list[str]:
        settings = get_settings()
        named = (
            ("LINKEDIN_CLIENT_ID", settings.linkedin_client_id),
            ("LINKEDIN_CLIENT_SECRET", settings.linkedin_client_secret),
            ("PUBLISHING_OAUTH_REDIRECT_URI", settings.publishing_oauth_redirect_uri),
        )
        return [name for name, value in named if not value]

    def authorize_url(self, *, state: str, redirect_uri: str) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": get_settings().linkedin_client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "scope": " ".join(SCOPES),
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def complete_authorization(
        self, *, code: str, redirect_uri: str
    ) -> ConnectedAccount:
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "client_id": settings.linkedin_client_id,
                        "client_secret": settings.linkedin_client_secret,
                    },
                )
                if resp.status_code >= 400:
                    raise _error_of(resp, doing="conectar el perfil")
                tokens = resp.json()
                token = tokens.get("access_token")
                if not isinstance(token, str) or not token:
                    raise _LinkedInError("LinkedIn no devolvió un token de acceso.")
                resp = await client.get(
                    USERINFO_URL, headers={"Authorization": f"Bearer {token}"}
                )
                if resp.status_code >= 400:
                    raise _error_of(resp, doing="leer el perfil")
                profile = resp.json()
        except _LinkedInError as exc:
            raise ChannelConnectionError(exc.message) from exc
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("linkedin.connect.transport err=%s", type(exc).__name__)
            raise ChannelConnectionError("No se pudo conectar con LinkedIn.") from exc
        credentials = {"access_token": token}
        if isinstance(tokens.get("refresh_token"), str):
            credentials["refresh_token"] = tokens["refresh_token"]
        return ConnectedAccount(
            credentials=credentials,
            token_expires_at=_expires_at(tokens),
            external_id=str(profile.get("sub") or ""),
            name=profile.get("name"),
            avatar_url=profile.get("picture"),
        )

    async def refresh_credentials(
        self, channel: PublishingChannel
    ) -> Credentials | None:
        refresh = (channel.credentials or {}).get("refresh_token")
        if not refresh:
            # Self-serve apps get no refresh token: the member reconnects
            # once the 60 days are over, not before.
            expires = channel.token_expires_at
            if expires is not None and expires <= datetime.now(UTC):
                raise ChannelConnectionError(
                    "El acceso a LinkedIn dura 60 días y venció. Volvé a conectar el perfil."
                )
            return None
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh,
                        "client_id": settings.linkedin_client_id,
                        "client_secret": settings.linkedin_client_secret,
                    },
                )
            if resp.status_code >= 400:
                error = _error_of(resp, doing="renovar el acceso")
                if error.retryable:
                    return None
                raise ChannelConnectionError(error.message)
            payload = resp.json()
        except (httpx.HTTPError, ValueError):
            return None
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            return None
        return Credentials(
            credentials={
                **(channel.credentials or {}),
                "access_token": token,
                **(
                    {"refresh_token": payload["refresh_token"]}
                    if isinstance(payload.get("refresh_token"), str)
                    else {}
                ),
            },
            token_expires_at=_expires_at(payload),
        )

    # -- Publishing ---------------------------------------------------------
    def validate(
        self, publication: Publication, target: PublicationTarget
    ) -> list[str]:
        errors: list[str] = []
        text = target_text(publication, target)
        media = publication.media or []
        if not text.strip() and not media:
            errors.append("LinkedIn necesita texto o al menos una imagen o video.")
        if len(escape_little(text)) > TEXT_MAX:
            errors.append(f"El texto para LinkedIn supera los {TEXT_MAX} caracteres.")
        if any(m.get("type") == "video" for m in media) and len(media) > 1:
            errors.append("LinkedIn admite 1 video solo, sin otras imágenes o videos.")
        elif len(media) > IMAGES_MAX:
            errors.append(f"LinkedIn admite hasta {IMAGES_MAX} imágenes por publicación.")
        return errors

    async def publish(
        self,
        session: AsyncSession,
        publication: Publication,
        target: PublicationTarget,
    ) -> PublishResult:
        channel = await session.get(PublishingChannel, target.channel_id)
        token = _token_of(channel)
        if channel is None or token is None or not channel.external_id:
            return PublishResult(
                ok=False, error_code="missing_channel", error_message=_MISSING_CHANNEL
            )
        author = f"urn:li:person:{channel.external_id}"
        text = target_text(publication, target)
        body: dict[str, Any] = {
            "author": author,
            "commentary": escape_little(text),
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                media = publication.media or []
                images = [
                    await self._upload_image(client, token, author, m["url"])
                    for m in media
                    if m.get("type") != "video"
                ]
                for video in (m for m in media if m.get("type") == "video"):
                    body["content"] = {
                        "media": {
                            "title": _video_title(text),
                            "id": await self._upload_video(client, token, author, video["url"]),
                        }
                    }
                if len(images) == 1:
                    body["content"] = {"media": {"id": images[0]}}
                elif images:
                    body["content"] = {"multiImage": {"images": [{"id": i} for i in images]}}
                try:
                    resp = await client.post(
                        f"{REST_BASE}/posts", headers=_headers(token), json=body
                    )
                except httpx.TimeoutException:
                    # It may have gone out: retrying could post it twice.
                    return PublishResult(
                        ok=False,
                        error_code="publish_timeout",
                        error_message=(
                            "LinkedIn no respondió a tiempo al publicar; revisá el perfil "
                            "antes de reintentar."
                        ),
                    )
                if resp.status_code >= 400:
                    raise _error_of(resp, doing="publicar")
        except _LinkedInError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return PublishResult(
                ok=False,
                error_code=exc.code,
                error_message=exc.message,
                retryable=exc.retryable,
            )
        except httpx.HTTPError as exc:
            log.warning("linkedin.publish.transport target_id=%s err=%s", target.id, type(exc).__name__)
            return PublishResult(
                ok=False,
                error_code="network_error",
                error_message="No se pudo conectar con LinkedIn; se reintenta más tarde.",
                retryable=True,
            )
        urn = resp.headers.get("x-restli-id")
        return PublishResult(
            ok=True,
            external_id=urn,
            permalink=f"https://www.linkedin.com/feed/update/{quote(urn, safe=':')}/" if urn else None,
        )

    @staticmethod
    async def _upload_image(
        client: httpx.AsyncClient, token: str, owner: str, url: str
    ) -> str:
        """Register an image with LinkedIn, upload its bytes (read from the
        file's public link) and return its ``urn:li:image``."""
        resp = await client.post(
            f"{REST_BASE}/images",
            params={"action": "initializeUpload"},
            headers=_headers(token),
            json={"initializeUploadRequest": {"owner": owner}},
        )
        if resp.status_code >= 400:
            raise _error_of(resp, doing="subir la imagen")
        value = (resp.json() or {}).get("value") or {}
        upload_url, image = value.get("uploadUrl"), value.get("image")
        if not upload_url or not image:
            raise _LinkedInError("LinkedIn no devolvió dónde subir la imagen.")
        source = await client.get(url, follow_redirects=True)
        if source.status_code >= 400:
            raise _LinkedInError("No se pudo leer la imagen para subirla a LinkedIn.")
        upload = await client.put(
            upload_url,
            content=source.content,
            headers={"Authorization": f"Bearer {token}"},
        )
        if upload.status_code >= 400:
            raise _error_of(upload, doing="subir la imagen")
        return str(image)

    @staticmethod
    async def _upload_video(
        client: httpx.AsyncClient, token: str, owner: str, url: str
    ) -> str:
        """Upload a video (read from its public link, without holding it all
        in memory) by the parts LinkedIn asks for, and return its
        ``urn:li:video`` once LinkedIn has finished processing it."""
        async with client.stream("GET", url, follow_redirects=True) as source:
            total = source.headers.get("content-length")
            if source.status_code >= 400 or not total:
                raise _LinkedInError("No se pudo leer el video para subirlo a LinkedIn.")
            resp = await client.post(
                f"{REST_BASE}/videos",
                params={"action": "initializeUpload"},
                headers=_headers(token),
                json={
                    "initializeUploadRequest": {
                        "owner": owner,
                        "fileSizeBytes": int(total),
                        "uploadCaptions": False,
                        "uploadThumbnail": False,
                    }
                },
            )
            if resp.status_code >= 400:
                raise _error_of(resp, doing="subir el video")
            value = (resp.json() or {}).get("value") or {}
            video, parts = value.get("video"), value.get("uploadInstructions")
            if not video or not parts:
                raise _LinkedInError("LinkedIn no devolvió dónde subir el video.")
            part_ids = await _upload_parts(client, source, parts)
        resp = await client.post(
            f"{REST_BASE}/videos",
            params={"action": "finalizeUpload"},
            headers=_headers(token),
            json={
                "finalizeUploadRequest": {
                    "video": video,
                    "uploadToken": value.get("uploadToken") or "",
                    "uploadedPartIds": part_ids,
                }
            },
        )
        if resp.status_code >= 400:
            raise _error_of(resp, doing="subir el video")
        await _wait_until_available(client, token, str(video))
        return str(video)


__all__ = ["LinkedInAdapter", "escape_little"]
