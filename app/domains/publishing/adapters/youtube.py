"""YouTube adapter: uploads a video to the owner's YouTube channel.

Written from Google's YouTube Data API v3 documentation:

  * Connecting: Google's OAuth 2.0 for web apps with the installation's
    Google client (the same ``GOOGLE_CLIENT_ID``/``SECRET`` as Google Calendar),
    ``access_type=offline`` and ``prompt=consent`` so a refresh token always
    comes back. Scopes: ``youtube.upload`` (publish) and ``youtube.readonly``
    (who the channel is, figures). The access token lasts an hour; the
    refresh token does not expire unless revoked (or after 7 days while the
    Google project is in "Testing").
  * Publishing: ``videos.insert`` with a resumable upload. The video is read
    from its link (our storage) and sent in one ``PUT``. Title, privacy,
    "made for kids", tags and category come from the target's ``settings``;
    the description is the post's text. Then, when chosen, the thumbnail (an
    image of the media library, ``thumbnails.set``: the channel has to be
    verified by phone) and the playlist (``playlistItems.insert``). Those two
    never fail the post, which is already up: their problems are kept as
    ``warnings``.
  * The editor reads the channel's playlists and YouTube's categories from
    ``compose_info``.
  * Figures: ``videos.list`` (views, likes, comments) and ``channels.list``
    (subscribers), plus the YouTube Analytics API (``yt-analytics.readonly``):
    per day, views, minutes watched, likes, comments, shares and subscribers
    gained and lost, views by traffic source, and the viewers' age, gender
    and country over the last 28 days; per video, minutes watched, average
    view duration and shares. Analytics trails by two or three days, and a
    channel connected before the scope was asked for keeps the basic figures
    until it is connected again.
  * Comments: ``commentThreads.list`` reads them live (newest first, with
    their replies) and ``comments.insert`` answers one as the channel. Both
    need ``youtube.force-ssl``: a channel connected before it was asked for
    gets "reconnect" instead.

Until Google audits the project, uploaded videos stay private, and the
default quota (10,000 units a day, 1,600 per upload) allows about 6 uploads
a day.
"""

from __future__ import annotations

import logging
import tempfile
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import IO, Any
from urllib.parse import urlencode

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.publishing.adapters.base import (
    ChannelConnectionError,
    CommentsResult,
    ConnectedAccount,
    Credentials,
    MetricsResult,
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

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://www.googleapis.com/youtube/v3"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
)
ANALYTICS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
AUDIENCE_DAYS = 28
COUNTRIES_MAX = 10
COMMENTS_MAX = 50
TAGS_MAX_CHARS = 500
DEFAULT_CATEGORY = "22"  # People & Blogs
THUMBNAIL_MAX_BYTES = 2 * 1024 * 1024
THUMBNAIL_TYPES = ("image/jpeg", "image/png")
THUMBNAIL_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
REPLY_MAX = 10000

TITLE_MAX = 100
DESCRIPTION_MAX = 5000
PRIVACY_STATUSES = ("public", "unlisted", "private")
VIDEO_MAX_BYTES = 2 * 1024**3
CHUNK = 1024 * 1024
ACCESS_MARGIN = timedelta(minutes=5)

_RECONNECT_MESSAGE = "El acceso a YouTube venció o se revocó. Volvé a conectar el canal."
_MISSING_CHANNEL = "El canal de YouTube no está conectado."

# ``errors[0].reason`` of the Data API → message in Spanish.
_REASONS = {
    "quotaExceeded": (
        "Se terminó la cuota diaria de YouTube de esta instalación; se reintenta más tarde.",
        True,
    ),
    "uploadLimitExceeded": ("El canal llegó al límite de videos que YouTube deja subir.", False),
    "youtubeSignupRequired": (
        "La cuenta de Google no tiene un canal de YouTube. Creá el canal y volvé a conectarla.",
        False,
    ),
    "invalidTitle": ("YouTube no aceptó el título del video.", False),
    "invalidDescription": ("YouTube no aceptó la descripción del video.", False),
    "insufficientPermissions": (
        "YouTube no dio uno de los permisos (subir videos o manejar comentarios). Volvé a "
        "conectar el canal aceptando todos los permisos.",
        False,
    ),
    "ACCESS_TOKEN_SCOPE_INSUFFICIENT": (
        "Para ver y responder comentarios, volvé a conectar el canal de YouTube y aceptá "
        "el permiso nuevo.",
        False,
    ),
    "commentsDisabled": ("Este video tiene los comentarios desactivados.", False),
    "videoNotFound": ("El video ya no está en YouTube.", False),
    "commentNotFound": ("Ese comentario ya no está en YouTube.", False),
    "processingFailure": ("YouTube no pudo procesar la respuesta; probá de nuevo.", True),
}


class _YouTubeError(Exception):
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


def _error_of(resp: httpx.Response) -> _YouTubeError | None:
    if resp.status_code < 400:
        return None
    try:
        error = resp.json().get("error") or {}
    except (ValueError, AttributeError):
        error = {}
    errors = error.get("errors") if isinstance(error, dict) else None
    reason = errors[0].get("reason") if errors and isinstance(errors[0], dict) else None
    details = error.get("details") if isinstance(error, dict) else None
    if reason is None and isinstance(details, list):
        reason = next(
            (d.get("reason") for d in details if isinstance(d, dict) and d.get("reason")),
            None,
        )
    if resp.status_code == 401:
        return _YouTubeError(_RECONNECT_MESSAGE, code="401", reconnect=True)
    if reason in _REASONS:
        message, retryable = _REASONS[reason]
        return _YouTubeError(message, code=reason, retryable=retryable)
    if resp.status_code == 429 or resp.status_code >= 500:
        return _YouTubeError(
            "YouTube no respondió por ahora; se reintenta más tarde.",
            code=reason or str(resp.status_code),
            retryable=True,
        )
    detail = error.get("message") if isinstance(error, dict) else None
    return _YouTubeError(
        f"YouTube rechazó la solicitud: {detail or reason or resp.status_code}",
        code=reason or str(resp.status_code),
    )


def _now() -> datetime:
    return datetime.now(UTC)


def _credentials_of(
    tokens: dict[str, Any], previous: dict[str, Any] | None = None
) -> dict[str, Any]:
    credentials = {**(previous or {}), "access_token": tokens["access_token"]}
    if isinstance(tokens.get("refresh_token"), str):
        credentials["refresh_token"] = tokens["refresh_token"]
    seconds = tokens.get("expires_in")
    if isinstance(seconds, int):
        credentials["access_expires_at"] = (_now() + timedelta(seconds=seconds)).isoformat()
    return credentials


def _access_expired(credentials: dict[str, Any]) -> bool:
    raw = credentials.get("access_expires_at")
    if not isinstance(raw, str):
        return True
    try:
        return datetime.fromisoformat(raw) - ACCESS_MARGIN <= _now()
    except ValueError:
        return True


def youtube_settings(target: PublicationTarget) -> dict[str, Any]:
    """What the owner chose for this target in the editor."""
    raw = target.settings or {}
    raw_tags = raw.get("tags")
    tags: list[Any] = raw_tags if isinstance(raw_tags, list) else []
    thumb = raw.get("thumbnail_media_id")
    category = str(raw.get("category_id") or DEFAULT_CATEGORY).strip()
    return {
        "title": str(raw.get("title") or "").strip(),
        "privacy_status": raw.get("privacy_status") or "private",
        "made_for_kids": bool(raw.get("made_for_kids")),
        "tags": [str(t).strip() for t in tags if str(t).strip()],
        "category_id": category,
        "playlist_id": str(raw.get("playlist_id") or "").strip() or None,
        "thumbnail_media_id": thumb
        if isinstance(thumb, int) and not isinstance(thumb, bool)
        else None,
    }


def tags_length(tags: list[str]) -> int:
    """How YouTube counts the 500 characters of the tags: their characters,
    a comma between each, and the quotes it adds around a tag with spaces."""
    if not tags:
        return 0
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + len(tags) - 1


async def _chunks(file: IO[bytes]) -> AsyncIterator[bytes]:
    while block := file.read(CHUNK):
        yield block


def _today() -> date:
    return datetime.now(UTC).date()


def _day_of(raw: Any) -> date | None:
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return None


def _comment_of(raw: dict[str, Any]) -> dict[str, Any]:
    """A YouTube comment resource onto the shared comment shape."""
    snippet = raw.get("snippet") or {}
    return {
        "id": str(raw.get("id") or ""),
        "author": snippet.get("authorDisplayName"),
        "author_avatar": snippet.get("authorProfileImageUrl"),
        # textOriginal is what the person wrote; textDisplay is HTML.
        "text": snippet.get("textOriginal") or snippet.get("textDisplay") or "",
        "published_at": snippet.get("publishedAt"),
        "like_count": int(snippet.get("likeCount") or 0),
    }


class YouTubeAdapter(PublishingAdapter):
    network = "youtube"
    label = "YouTube"
    supports_comments = True

    # -- Connecting ---------------------------------------------------------
    def missing_connection_settings(self) -> list[str]:
        settings = get_settings()
        named = (
            ("GOOGLE_CLIENT_ID", settings.google_client_id),
            ("GOOGLE_CLIENT_SECRET", settings.google_client_secret),
            ("PUBLISHING_OAUTH_REDIRECT_URI", settings.publishing_oauth_redirect_uri),
        )
        return [name for name, value in named if not value]

    def authorize_url(self, *, state: str, redirect_uri: str) -> str:
        query = urlencode(
            {
                "client_id": get_settings().google_client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(SCOPES),
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state,
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def complete_authorization(self, *, code: str, redirect_uri: str) -> ConnectedAccount:
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    TOKEN_URL,
                    data={
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                    },
                )
                if resp.status_code >= 400 or not resp.json().get("access_token"):
                    raise _YouTubeError("Google rechazó el acceso a YouTube.", code="oauth")
                tokens = resp.json()
                resp = await client.get(
                    f"{API_BASE}/channels",
                    params={"part": "snippet", "mine": "true"},
                    headers={"Authorization": f"Bearer {tokens['access_token']}"},
                )
                error = _error_of(resp)
                if error is not None:
                    raise error
                items = resp.json().get("items") or []
        except _YouTubeError as exc:
            raise ChannelConnectionError(exc.message) from exc
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            log.warning("youtube.connect.transport err=%s", type(exc).__name__)
            raise ChannelConnectionError("No se pudo conectar con YouTube.") from exc
        if not items:
            raise ChannelConnectionError(_REASONS["youtubeSignupRequired"][0])
        channel = items[0]
        snippet = channel.get("snippet") or {}
        thumbnails = snippet.get("thumbnails") or {}
        avatar = (thumbnails.get("default") or {}).get("url")
        handle = str(snippet.get("customUrl") or "").lstrip("@") or None
        return ConnectedAccount(
            credentials=_credentials_of(tokens),
            external_id=str(channel.get("id") or ""),
            name=snippet.get("title"),
            username=handle,
            avatar_url=avatar,
        )

    async def refresh_credentials(self, channel: PublishingChannel) -> Credentials | None:
        credentials = channel.credentials or {}
        refresh = credentials.get("refresh_token")
        if not refresh:
            raise ChannelConnectionError(_RECONNECT_MESSAGE)
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    TOKEN_URL,
                    data={
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "grant_type": "refresh_token",
                        "refresh_token": refresh,
                    },
                )
        except httpx.HTTPError:
            return None
        if resp.status_code == 429 or resp.status_code >= 500:
            return None
        if resp.status_code >= 400:
            raise ChannelConnectionError(_RECONNECT_MESSAGE)
        return Credentials(credentials=_credentials_of(resp.json(), credentials))

    async def _access_token(self, session: AsyncSession, channel: PublishingChannel) -> str:
        credentials = channel.credentials or {}
        token = credentials.get("access_token")
        if isinstance(token, str) and token and not _access_expired(credentials):
            return token
        try:
            fresh = await self.refresh_credentials(channel)
        except ChannelConnectionError as exc:
            raise _YouTubeError(str(exc), code="refresh_failed", reconnect=True) from exc
        if fresh is None:
            raise _YouTubeError(
                "No se pudo renovar el acceso a YouTube por ahora; se reintenta más tarde.",
                code="refresh_unavailable",
                retryable=True,
            )
        channel.credentials = fresh.credentials
        session.add(channel)
        await session.flush()
        return str(fresh.credentials["access_token"])

    # -- Publishing ---------------------------------------------------------
    def validate(self, publication: Publication, target: PublicationTarget) -> list[str]:
        errors: list[str] = []
        media = publication.media or []
        videos = [m for m in media if m.get("type") == "video"]
        if len(videos) != 1 or len(media) != 1:
            errors.append("YouTube necesita un solo video, sin fotos.")
        chosen = youtube_settings(target)
        if not chosen["title"]:
            errors.append("Poné el título del video de YouTube.")
        elif len(chosen["title"]) > TITLE_MAX:
            errors.append(f"El título de YouTube no puede pasar de {TITLE_MAX} caracteres.")
        if any(c in chosen["title"] for c in "<>"):
            errors.append("El título de YouTube no puede tener los signos < ni >.")
        text = target_text(publication, target)
        if len(text) > DESCRIPTION_MAX:
            errors.append(f"La descripción de YouTube supera los {DESCRIPTION_MAX} caracteres.")
        if any(c in text for c in "<>"):
            errors.append("La descripción de YouTube no puede tener los signos < ni >.")
        if chosen["privacy_status"] not in PRIVACY_STATUSES:
            errors.append("Elegí quién puede ver el video en YouTube.")
        if tags_length(chosen["tags"]) > TAGS_MAX_CHARS:
            errors.append(
                f"Las etiquetas de YouTube no pueden pasar de {TAGS_MAX_CHARS} caracteres."
            )
        if any(c in t for t in chosen["tags"] for c in "<>,"):
            errors.append("Las etiquetas de YouTube no pueden tener los signos <, > ni comas.")
        if not chosen["category_id"].isdigit():
            errors.append("Elegí la categoría del video de YouTube.")
        return errors

    async def publish(
        self,
        session: AsyncSession,
        publication: Publication,
        target: PublicationTarget,
    ) -> PublishResult:
        channel = await session.get(PublishingChannel, target.channel_id)
        if channel is None or not (channel.credentials or {}).get("refresh_token"):
            return PublishResult(
                ok=False, error_code="missing_channel", error_message=_MISSING_CHANNEL
            )
        chosen = youtube_settings(target)
        video = (publication.media or [{}])[0]
        body = {
            "snippet": {
                "title": chosen["title"],
                "description": target_text(publication, target),
                "categoryId": chosen["category_id"],
                **({"tags": chosen["tags"]} if chosen["tags"] else {}),
            },
            "status": {
                "privacyStatus": chosen["privacy_status"],
                "selfDeclaredMadeForKids": chosen["made_for_kids"],
            },
        }
        try:
            token = await self._access_token(session, channel)
            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, write=600.0)) as client:
                with tempfile.TemporaryFile() as file:
                    size, mime = await self._download(client, str(video.get("url") or ""), file)
                    resp = await client.post(
                        UPLOAD_URL,
                        params={"uploadType": "resumable", "part": "snippet,status"},
                        headers={
                            **headers,
                            "X-Upload-Content-Length": str(size),
                            "X-Upload-Content-Type": mime,
                        },
                        json=body,
                    )
                    error = _error_of(resp)
                    if error is not None:
                        raise error
                    location = resp.headers.get("location")
                    if not location:
                        raise _YouTubeError("YouTube no devolvió dónde subir el video.")
                    file.seek(0)
                    resp = await client.put(
                        location,
                        headers={**headers, "Content-Length": str(size), "Content-Type": mime},
                        content=_chunks(file),
                    )
                    error = _error_of(resp)
                    if error is not None:
                        raise error
                    video_id = resp.json().get("id")
        except _YouTubeError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return PublishResult(
                ok=False, error_code=exc.code, error_message=exc.message, retryable=exc.retryable
            )
        except httpx.HTTPError as exc:
            log.warning(
                "youtube.publish.transport target_id=%s err=%s", target.id, type(exc).__name__
            )
            return PublishResult(
                ok=False,
                error_code="network_error",
                error_message="No se pudo conectar con YouTube; se reintenta más tarde.",
                retryable=True,
            )
        if not video_id:
            return PublishResult(
                ok=False, error_code="no_id", error_message="YouTube no devolvió el video subido."
            )
        warnings = await self._finish_video(session, publication, channel, str(video_id), chosen)
        return PublishResult(
            ok=True,
            external_id=str(video_id),
            permalink=f"https://www.youtube.com/watch?v={video_id}",
            extra={"warnings": warnings} if warnings else {},
        )

    async def _finish_video(
        self,
        session: AsyncSession,
        publication: Publication,
        channel: PublishingChannel,
        video_id: str,
        chosen: dict[str, Any],
    ) -> list[str]:
        """Thumbnail and playlist, after the video is up. Problems come back
        as warnings: the post itself already went out."""
        warnings: list[str] = []
        if chosen["thumbnail_media_id"] is None and not chosen["playlist_id"]:
            return warnings
        try:
            token = await self._access_token(session, channel)
        except _YouTubeError as exc:
            return [exc.message]
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            if chosen["thumbnail_media_id"] is not None:
                problem = await self._set_thumbnail(
                    session,
                    client,
                    headers,
                    publication.account_id,
                    video_id,
                    chosen["thumbnail_media_id"],
                )
                if problem:
                    warnings.append(problem)
            if chosen["playlist_id"]:
                try:
                    resp = await client.post(
                        f"{API_BASE}/playlistItems",
                        params={"part": "snippet"},
                        headers=headers,
                        json={
                            "snippet": {
                                "playlistId": chosen["playlist_id"],
                                "resourceId": {"kind": "youtube#video", "videoId": video_id},
                            }
                        },
                    )
                    error = _error_of(resp)
                    if error is not None:
                        warnings.append(f"No se pudo agregar a la lista: {error.message}")
                except httpx.HTTPError:
                    warnings.append("No se pudo agregar el video a la lista de YouTube.")
        return warnings

    @staticmethod
    async def _set_thumbnail(
        session: AsyncSession,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        account_id: int,
        video_id: str,
        media_id: int,
    ) -> str | None:
        from app.domains.media_library import service as media_library

        assets = await media_library.get_assets(
            session, account_id=account_id, asset_ids=[media_id]
        )
        asset = assets.get(media_id)
        if asset is None or asset.kind != "image":
            return "La miniatura ya no está en la biblioteca de medios."
        try:
            resp = await client.get(media_library.asset_public_url(asset), follow_redirects=True)
            data = resp.content if resp.status_code < 400 else b""
            mime = resp.headers.get("content-type", "").split(";")[0] or "image/jpeg"
            if not data:
                return "No se pudo leer la miniatura para subirla a YouTube."
            if mime not in THUMBNAIL_TYPES:
                return "La miniatura de YouTube tiene que ser JPG o PNG."
            if len(data) > THUMBNAIL_MAX_BYTES:
                return "La miniatura de YouTube no puede pasar de 2 MB."
            resp = await client.post(
                THUMBNAIL_URL,
                params={"videoId": video_id},
                headers={**headers, "Content-Type": mime},
                content=data,
            )
        except httpx.HTTPError:
            return "No se pudo subir la miniatura a YouTube."
        if resp.status_code == 403:
            return (
                "YouTube no dejó poner la miniatura: el canal tiene que estar verificado "
                "por teléfono (youtube.com/verify)."
            )
        error = _error_of(resp)
        return f"No se pudo poner la miniatura: {error.message}" if error is not None else None

    async def compose_info(
        self, session: AsyncSession, channel: PublishingChannel
    ) -> dict[str, Any]:
        """The channel's playlists and YouTube's categories, for the editor."""
        try:
            token = await self._access_token(session, channel)
            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{API_BASE}/playlists",
                    params={"part": "snippet", "mine": "true", "maxResults": 50},
                    headers=headers,
                )
                error = _error_of(resp)
                if error is not None:
                    raise error
                playlists = [
                    {"id": p.get("id"), "title": (p.get("snippet") or {}).get("title")}
                    for p in resp.json().get("items") or []
                    if p.get("id")
                ]
                resp = await client.get(
                    f"{API_BASE}/videoCategories",
                    params={"part": "snippet", "regionCode": "US", "hl": "es"},
                    headers=headers,
                )
                error = _error_of(resp)
                if error is not None:
                    raise error
                categories = [
                    {"id": c.get("id"), "title": (c.get("snippet") or {}).get("title")}
                    for c in resp.json().get("items") or []
                    if (c.get("snippet") or {}).get("assignable")
                ]
        except _YouTubeError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return {"can_post": False, "message": exc.message}
        except (httpx.HTTPError, ValueError):
            return {"can_post": False, "message": "No se pudo consultar YouTube."}
        return {"can_post": True, "message": None, "playlists": playlists, "categories": categories}

    @staticmethod
    async def _download(client: httpx.AsyncClient, url: str, file: IO[bytes]) -> tuple[int, str]:
        """Copy the video into ``file``; returns its size and type."""
        if not url:
            raise _YouTubeError("La publicación no tiene el link del video.", code="no_media")
        size = 0
        try:
            async with client.stream("GET", url, follow_redirects=True) as resp:
                if resp.status_code >= 400:
                    raise _YouTubeError(
                        "No se pudo leer el video para subirlo a YouTube.",
                        code="media_unreadable",
                        retryable=resp.status_code >= 500,
                    )
                mime = resp.headers.get("content-type", "video/*").split(";")[0]
                async for block in resp.aiter_bytes(CHUNK):
                    size += len(block)
                    if size > VIDEO_MAX_BYTES:
                        raise _YouTubeError(
                            "El video pasa de 2 GB, el máximo para subirlo desde AloStudio.",
                            code="media_too_big",
                        )
                    file.write(block)
        except httpx.HTTPError as exc:
            raise _YouTubeError(
                "No se pudo leer el video para subirlo a YouTube.",
                code="media_unreadable",
                retryable=True,
            ) from exc
        if not mime.startswith("video/") and mime != "application/octet-stream":
            mime = "video/*"
        return size, mime

    # -- Comments -----------------------------------------------------------
    async def list_comments(
        self, session: AsyncSession, target: PublicationTarget
    ) -> CommentsResult:
        channel = await session.get(PublishingChannel, target.channel_id)
        if channel is None or not target.external_id:
            return CommentsResult(ok=False, error_message="El video todavía no está en YouTube.")
        try:
            token = await self._access_token(session, channel)
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{API_BASE}/commentThreads",
                    params={
                        "part": "snippet,replies",
                        "videoId": target.external_id,
                        "maxResults": COMMENTS_MAX,
                        "order": "time",
                        "textFormat": "plainText",
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
            error = _error_of(resp)
            if error is not None:
                raise error
            items = resp.json().get("items") or []
        except _YouTubeError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return CommentsResult(ok=False, error_message=exc.message)
        except (httpx.HTTPError, ValueError):
            return CommentsResult(ok=False, error_message="No se pudo consultar YouTube.")
        comments = []
        for thread in items:
            top = (thread.get("snippet") or {}).get("topLevelComment") or {}
            comment = _comment_of(top)
            comment["id"] = str(thread.get("id") or comment["id"])
            replies = ((thread.get("replies") or {}).get("comments")) or []
            # The API lists replies newest first; read them in order.
            comment["replies"] = [_comment_of(r) for r in reversed(replies)]
            comments.append(comment)
        return CommentsResult(ok=True, comments=comments)

    async def reply_to_comment(
        self,
        session: AsyncSession,
        target: PublicationTarget,
        *,
        comment_id: str,
        text: str,
    ) -> CommentsResult:
        body_text = text.strip()
        if not body_text:
            return CommentsResult(ok=False, error_message="Escribí la respuesta.")
        if len(body_text) > REPLY_MAX:
            return CommentsResult(
                ok=False, error_message=f"La respuesta no puede pasar de {REPLY_MAX} caracteres."
            )
        channel = await session.get(PublishingChannel, target.channel_id)
        if channel is None:
            return CommentsResult(ok=False, error_message=_MISSING_CHANNEL)
        try:
            token = await self._access_token(session, channel)
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{API_BASE}/comments",
                    params={"part": "snippet"},
                    headers={"Authorization": f"Bearer {token}"},
                    json={"snippet": {"parentId": comment_id, "textOriginal": body_text}},
                )
            error = _error_of(resp)
            if error is not None:
                raise error
            reply = _comment_of(resp.json())
        except _YouTubeError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return CommentsResult(ok=False, error_message=exc.message)
        except (httpx.HTTPError, ValueError):
            return CommentsResult(ok=False, error_message="No se pudo conectar con YouTube.")
        return CommentsResult(ok=True, comments=[reply])

    # -- Figures ------------------------------------------------------------
    async def fetch_post_metrics(
        self, session: AsyncSession, target: PublicationTarget
    ) -> MetricsResult | None:
        channel = await session.get(PublishingChannel, target.channel_id)
        if channel is None or not target.external_id:
            return None
        try:
            token = await self._access_token(session, channel)
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{API_BASE}/videos",
                    params={"part": "statistics", "id": target.external_id},
                    headers={"Authorization": f"Bearer {token}"},
                )
            error = _error_of(resp)
            if error is not None:
                raise error
            items = resp.json().get("items") or []
        except _YouTubeError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return MetricsResult(ok=False, error_message=exc.message)
        except (httpx.HTTPError, ValueError):
            return MetricsResult(ok=False, error_message="No se pudo consultar YouTube.")
        if not items:
            return MetricsResult(ok=False, error_message="El video ya no está en YouTube.")
        stats = items[0].get("statistics") or {}
        names = {"views": "viewCount", "likes": "likeCount", "comments": "commentCount"}
        metrics = {k: int(stats[v]) for k, v in names.items() if str(stats.get(v, "")).isdigit()}
        published = target.published_at.date() if target.published_at else date(2005, 4, 23)
        rows = await self._report(
            session,
            channel,
            {
                "startDate": published.isoformat(),
                "endDate": _today().isoformat(),
                "metrics": "estimatedMinutesWatched,averageViewDuration,shares",
                "filters": f"video=={target.external_id}",
            },
        )
        if rows:
            minutes, avg_seconds, shares = (rows[0] + [0, 0, 0])[:3]
            metrics["watch_time_ms"] = int(float(minutes) * 60_000)
            metrics["avg_watch_time_ms"] = int(float(avg_seconds) * 1000)
            metrics["shares"] = int(shares)
        return MetricsResult(ok=True, metrics=metrics)

    async def _report(
        self, session: AsyncSession, channel: PublishingChannel, params: dict[str, Any]
    ) -> list[list[Any]] | None:
        """Rows of a YouTube Analytics report for the channel, or ``None``
        when it can't be read (the channel lacks the scope, Analytics is off
        in the project…): the basic figures still go out."""
        try:
            token = await self._access_token(session, channel)
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    ANALYTICS_URL,
                    params={"ids": "channel==MINE", **params},
                    headers={"Authorization": f"Bearer {token}"},
                )
        except (_YouTubeError, httpx.HTTPError) as exc:
            log.info("youtube.analytics.unavailable channel_id=%s err=%s", channel.id, exc)
            return None
        if resp.status_code >= 400:
            log.info(
                "youtube.analytics.refused channel_id=%s status=%s", channel.id, resp.status_code
            )
            return None
        try:
            rows = resp.json().get("rows") or []
        except ValueError:
            return None
        return [list(r) for r in rows if isinstance(r, list)]

    async def fetch_channel_metrics(
        self, session: AsyncSession, channel: PublishingChannel, *, days: list[Any]
    ) -> MetricsResult | None:
        try:
            token = await self._access_token(session, channel)
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{API_BASE}/channels",
                    params={"part": "statistics", "mine": "true"},
                    headers={"Authorization": f"Bearer {token}"},
                )
            error = _error_of(resp)
            if error is not None:
                raise error
            items = resp.json().get("items") or []
        except _YouTubeError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return MetricsResult(ok=False, error_message=exc.message)
        except (httpx.HTTPError, ValueError):
            return MetricsResult(ok=False, error_message="No se pudo consultar YouTube.")
        stats = (items[0].get("statistics") or {}) if items else {}
        subscribers = str(stats.get("subscriberCount", ""))
        metrics = {"followers": int(subscribers)} if subscribers.isdigit() else {}
        wanted = sorted(d for d in days if isinstance(d, date))
        daily = await self._daily(session, channel, wanted) if wanted else {}
        audience = await self._audience(session, channel)
        return MetricsResult(ok=True, metrics=metrics, daily=daily, audience=audience)

    async def _daily(
        self, session: AsyncSession, channel: PublishingChannel, days: list[date]
    ) -> dict[date, dict[str, Any]]:
        wanted = set(days)
        span = {"startDate": days[0].isoformat(), "endDate": days[-1].isoformat()}
        daily: dict[date, dict[str, Any]] = {}
        rows = await self._report(
            session,
            channel,
            {
                **span,
                "dimensions": "day",
                "metrics": (
                    "views,estimatedMinutesWatched,likes,comments,shares,"
                    "subscribersGained,subscribersLost"
                ),
                "sort": "day",
            },
        )
        for row in rows or []:
            day = _day_of(row[0])
            if day is None or day not in wanted:
                continue
            views, _minutes, likes, comments, shares, gained, lost = (
                [int(float(v)) for v in row[1:8]] + [0] * 7
            )[:7]
            daily[day] = {
                "views": views,
                "watch_time_ms": int(float(row[2]) * 60_000),
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "interactions": likes + comments + shares,
                "follows": gained,
                "unfollows": lost,
            }
        rows = await self._report(
            session,
            channel,
            {**span, "dimensions": "day,insightTrafficSourceType", "metrics": "views"},
        )
        for row in rows or []:
            day = _day_of(row[0])
            if day is None or day not in wanted or len(row) < 3:
                continue
            split = daily.setdefault(day, {}).setdefault("views_by_traffic_source", {})
            split[str(row[1])] = split.get(str(row[1]), 0) + int(float(row[2]))
        return daily

    async def _audience(self, session: AsyncSession, channel: PublishingChannel) -> dict[str, Any]:
        """Who watched in the last 28 days: age and gender (share of the
        viewers, in percent) and the countries with most views."""
        end = _today()
        span = {
            "startDate": (end - timedelta(days=AUDIENCE_DAYS)).isoformat(),
            "endDate": end.isoformat(),
        }
        engaged: dict[str, dict[str, float]] = {}
        rows = await self._report(
            session,
            channel,
            {**span, "dimensions": "ageGroup,gender", "metrics": "viewerPercentage"},
        )
        for row in rows or []:
            if len(row) < 3:
                continue
            age = str(row[0]).removeprefix("age")
            pct = round(float(row[2]), 1)
            ages = engaged.setdefault("age", {})
            ages[age] = round(ages.get(age, 0) + pct, 1)
            # Same codes as the other networks' audiences.
            gender = {"female": "F", "male": "M"}.get(str(row[1]), "U")
            genders = engaged.setdefault("gender", {})
            genders[gender] = round(genders.get(gender, 0) + pct, 1)
        rows = await self._report(
            session,
            channel,
            {
                **span,
                "dimensions": "country",
                "metrics": "views",
                "sort": "-views",
                "maxResults": COUNTRIES_MAX,
            },
        )
        for row in rows or []:
            if len(row) >= 2 and int(float(row[1])) > 0:
                engaged.setdefault("country", {})[str(row[0])] = int(float(row[1]))
        return {"engaged": engaged} if engaged else {}


__all__ = ["YouTubeAdapter", "tags_length", "youtube_settings"]
