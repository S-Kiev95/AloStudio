"""TikTok adapter: publishes videos and photo posts on a creator's account.

Written from TikTok for Developers' documentation:

  * Connecting: Login Kit for web (``/v2/auth/authorize/`` → code →
    ``POST /v2/oauth/token/``) with ``user.info.basic`` (who the creator
    is, ``GET /v2/user/info/``) and ``video.publish`` (Direct Post). The
    access token lasts 2 hours and the refresh token 180 days; every
    refresh returns a new refresh token that replaces the old one.
  * Publishing (Content Posting API, Direct Post): the creator's current
    info is read first (``creator_info/query``: who posts, which privacy
    levels they may pick, whether they can post now). Videos go to
    ``video/init`` and photos (JPEG/WebP, up to 35) to ``content/init``,
    both as ``PULL_FROM_URL``: TikTok downloads the files from their public
    links, whose URL prefix has to be verified in the app (the signature
    file is served by ``app/domains/uploads/public_router.py``). Publishing is
    asynchronous: ``status/fetch`` is polled until it completes or fails.
  * Per target, ``settings`` carries what the creator chose in the editor,
    as TikTok requires: ``privacy_level`` (no default), ``allow_comment``,
    ``allow_duet``, ``allow_stitch`` and the commercial content disclosure
    (``brand_organic``: their own brand, ``brand_content``: a paid
    partnership).

Until TikTok audits the app, posts can only be private (``SELF_ONLY``),
on private accounts, for up to 5 creators a day. Figures (``video.list``)
are not covered yet.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

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

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
API_BASE = "https://open.tiktokapis.com/v2"
SCOPES: tuple[str, ...] = ("user.info.basic", "video.publish")

VIDEO_TEXT_MAX = 2200
PHOTO_TEXT_MAX = 4000
PHOTOS_MAX = 35
PHOTO_EXTENSIONS = ("jpg", "jpeg", "webp")
PRIVACY_LEVELS = (
    "PUBLIC_TO_EVERYONE",
    "MUTUAL_FOLLOW_FRIENDS",
    "FOLLOWER_OF_CREATOR",
    "SELF_ONLY",
)

# TikTok processes the post after the call: poll its status this often,
# for at most this long.
POLL_SECONDS = 5.0
POLL_MAX_SECONDS = 300.0
# Renew the 2-hour access token when less than this is left.
ACCESS_MARGIN = timedelta(minutes=5)

_RECONNECT_MESSAGE = "El acceso a TikTok venció o se revocó. Volvé a conectar la cuenta."
_MISSING_CHANNEL = "La cuenta de TikTok no está conectada."

# ``error.code`` of the Content Posting API → message in Spanish.
_ERROR_MESSAGES = {
    "scope_not_authorized": (
        "TikTok no dio permiso para publicar. Volvé a conectar la cuenta aceptando "
        "todos los permisos."
    ),
    "spam_risk_too_many_posts": "La cuenta llegó al límite diario de publicaciones de TikTok.",
    "spam_risk_user_banned_from_posting": "TikTok no deja publicar a esta cuenta por ahora.",
    "reached_active_user_cap": (
        "La app de TikTok llegó a su límite diario de cuentas que publican; se puede "
        "reintentar mañana."
    ),
    "unaudited_client_can_only_post_to_private_accounts": (
        "Mientras TikTok no apruebe la app, solo se puede publicar en cuentas privadas "
        "y con visibilidad «Solo yo»."
    ),
    "url_ownership_unverified": (
        "TikTok no pudo descargar los archivos: falta verificar la URL de los medios en la "
        "app de TikTok."
    ),
    "privacy_level_option_mismatch": (
        "La visibilidad elegida ya no está disponible para esta cuenta de TikTok. Elegila "
        "de nuevo en el editor."
    ),
}

# ``fail_reason`` of a post that TikTok couldn't process.
_FAIL_REASONS = {
    "file_format_check_failed": "TikTok no aceptó el formato del archivo.",
    "duration_check_failed": "El video es más largo de lo que la cuenta puede publicar.",
    "frame_rate_check_failed": "TikTok no aceptó la cantidad de cuadros por segundo del video.",
    "picture_size_check_failed": "TikTok no aceptó el tamaño de la imagen.",
    "video_pull_failed": "TikTok no pudo descargar el video.",
    "photo_pull_failed": "TikTok no pudo descargar las fotos.",
    "publish_cancelled": "La publicación se canceló en TikTok.",
    "auth_removed": _RECONNECT_MESSAGE,
    "spam_risk_too_many_posts": _ERROR_MESSAGES["spam_risk_too_many_posts"],
    "spam_risk_user_banned_from_posting": _ERROR_MESSAGES["spam_risk_user_banned_from_posting"],
    "spam_risk_text": "TikTok rechazó el texto de la publicación.",
    "spam_risk": "TikTok rechazó la publicación por riesgo de spam.",
}


class _TikTokError(Exception):
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


def _error_of(resp: httpx.Response) -> _TikTokError | None:
    """The failure an API response carries, or ``None`` when it succeeded.
    Some failures come with HTTP 200 and only ``error.code`` tells."""
    try:
        payload = resp.json()
    except ValueError:
        payload = {}
    error = payload.get("error") if isinstance(payload, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    if resp.status_code < 400 and code in (None, "ok"):
        return None
    if code == "access_token_invalid" or (
        resp.status_code == 401 and code != "scope_not_authorized"
    ):
        return _TikTokError(_RECONNECT_MESSAGE, code=code or "401", reconnect=True)
    if code == "rate_limit_exceeded" or resp.status_code == 429 or resp.status_code >= 500:
        return _TikTokError(
            "TikTok limitó o no respondió las solicitudes por ahora; se reintenta más tarde.",
            code=code or str(resp.status_code),
            retryable=True,
        )
    if code in _ERROR_MESSAGES:
        return _TikTokError(_ERROR_MESSAGES[code], code=code)
    detail = error.get("message") if isinstance(error, dict) else None
    return _TikTokError(
        f"TikTok rechazó la solicitud: {detail or code or resp.status_code}".strip(),
        code=code or str(resp.status_code),
    )


def _token_error(resp: httpx.Response) -> _TikTokError | None:
    """The OAuth endpoint answers errors as ``{"error", "error_description"}``."""
    try:
        payload = resp.json()
    except ValueError:
        payload = {}
    if resp.status_code < 400 and isinstance(payload, dict) and payload.get("access_token"):
        return None
    if resp.status_code == 429 or resp.status_code >= 500:
        return _TikTokError(
            "TikTok no respondió por ahora; se reintenta más tarde.",
            code=str(resp.status_code),
            retryable=True,
        )
    detail = payload.get("error_description") or payload.get("error") if isinstance(payload, dict) else None
    return _TikTokError(f"TikTok rechazó el acceso: {detail or resp.status_code}", code="oauth")


def _now() -> datetime:
    return datetime.now(UTC)


def _credentials_of(tokens: dict[str, Any], *, previous: dict[str, Any] | None = None) -> Credentials:
    """Stored credentials from a token response: the refresh token's expiry
    is the channel's (``token_expires_at``), the access token's goes along."""
    now = _now()
    access_seconds = tokens.get("expires_in")
    refresh_seconds = tokens.get("refresh_expires_in")
    credentials = {
        **(previous or {}),
        "access_token": tokens["access_token"],
        "open_id": tokens.get("open_id") or (previous or {}).get("open_id"),
    }
    if isinstance(tokens.get("refresh_token"), str):
        credentials["refresh_token"] = tokens["refresh_token"]
    if isinstance(access_seconds, int):
        credentials["access_expires_at"] = (now + timedelta(seconds=access_seconds)).isoformat()
    return Credentials(
        credentials=credentials,
        token_expires_at=(
            now + timedelta(seconds=refresh_seconds) if isinstance(refresh_seconds, int) else None
        ),
    )


def _access_expired(credentials: dict[str, Any]) -> bool:
    raw = credentials.get("access_expires_at")
    if not isinstance(raw, str):
        return True
    try:
        expires = datetime.fromisoformat(raw)
    except ValueError:
        return True
    return expires - ACCESS_MARGIN <= _now()


def _extension(url: str) -> str:
    """File extension of a media link: of its ``key`` (our signed links
    carry the object key in the query) or of its path."""
    parsed = urlparse(url)
    name = (parse_qs(parsed.query).get("key") or [parsed.path])[0]
    tail = name.rsplit("/", 1)[-1]
    return tail.rsplit(".", 1)[-1].lower() if "." in tail else ""


def tiktok_settings(target: PublicationTarget) -> dict[str, Any]:
    """What the creator chose for this target in the editor."""
    raw = target.settings or {}
    return {
        "privacy_level": raw.get("privacy_level"),
        "allow_comment": bool(raw.get("allow_comment")),
        "allow_duet": bool(raw.get("allow_duet")),
        "allow_stitch": bool(raw.get("allow_stitch")),
        "disclose": bool(raw.get("disclose")),
        "brand_organic": bool(raw.get("brand_organic")),
        "brand_content": bool(raw.get("brand_content")),
    }


class TikTokAdapter(PublishingAdapter):
    network = "tiktok"
    label = "TikTok"

    # -- Connecting ---------------------------------------------------------
    def missing_connection_settings(self) -> list[str]:
        settings = get_settings()
        named = (
            ("TIKTOK_CLIENT_KEY", settings.tiktok_client_key),
            ("TIKTOK_CLIENT_SECRET", settings.tiktok_client_secret),
            ("PUBLISHING_OAUTH_REDIRECT_URI", settings.publishing_oauth_redirect_uri),
        )
        return [name for name, value in named if not value]

    def authorize_url(self, *, state: str, redirect_uri: str) -> str:
        query = urlencode(
            {
                "client_key": get_settings().tiktok_client_key,
                "response_type": "code",
                "scope": ",".join(SCOPES),
                "redirect_uri": redirect_uri,
                "state": state,
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
                    f"{API_BASE}/oauth/token/",
                    data={
                        "client_key": settings.tiktok_client_key,
                        "client_secret": settings.tiktok_client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                    },
                )
                error = _token_error(resp)
                if error is not None:
                    raise error
                tokens = resp.json()
                resp = await client.get(
                    f"{API_BASE}/user/info/",
                    params={"fields": "open_id,avatar_url,display_name"},
                    headers={"Authorization": f"Bearer {tokens['access_token']}"},
                )
                error = _error_of(resp)
                if error is not None:
                    raise error
                user = (resp.json().get("data") or {}).get("user") or {}
        except _TikTokError as exc:
            raise ChannelConnectionError(exc.message) from exc
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            log.warning("tiktok.connect.transport err=%s", type(exc).__name__)
            raise ChannelConnectionError("No se pudo conectar con TikTok.") from exc
        fresh = _credentials_of(tokens)
        return ConnectedAccount(
            credentials=fresh.credentials,
            token_expires_at=fresh.token_expires_at,
            external_id=str(user.get("open_id") or tokens.get("open_id") or ""),
            name=user.get("display_name"),
            avatar_url=user.get("avatar_url"),
        )

    async def refresh_credentials(
        self, channel: PublishingChannel
    ) -> Credentials | None:
        credentials = channel.credentials or {}
        refresh = credentials.get("refresh_token")
        if not refresh:
            raise ChannelConnectionError(_RECONNECT_MESSAGE)
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{API_BASE}/oauth/token/",
                    data={
                        "client_key": settings.tiktok_client_key,
                        "client_secret": settings.tiktok_client_secret,
                        "grant_type": "refresh_token",
                        "refresh_token": refresh,
                    },
                )
        except httpx.HTTPError:
            return None
        error = _token_error(resp)
        if error is not None:
            if error.retryable:
                return None
            raise ChannelConnectionError(_RECONNECT_MESSAGE)
        return _credentials_of(resp.json(), previous=credentials)

    async def _access_token(self, session: AsyncSession, channel: PublishingChannel) -> str:
        """A usable access token, renewed first when its 2 hours are over.
        The renewal is saved right away: TikTok has already replaced the
        refresh token, so the old one no longer works."""
        credentials = channel.credentials or {}
        token = credentials.get("access_token")
        if isinstance(token, str) and token and not _access_expired(credentials):
            return token
        try:
            fresh = await self.refresh_credentials(channel)
        except ChannelConnectionError as exc:
            raise _TikTokError(str(exc), code="refresh_failed", reconnect=True) from exc
        if fresh is None:
            raise _TikTokError(
                "No se pudo renovar el acceso a TikTok por ahora; se reintenta más tarde.",
                code="refresh_unavailable",
                retryable=True,
            )
        channel.credentials = fresh.credentials
        channel.token_expires_at = fresh.token_expires_at
        session.add(channel)
        await session.flush()
        return str(fresh.credentials["access_token"])

    @staticmethod
    async def _creator_info(client: httpx.AsyncClient, token: str) -> dict[str, Any]:
        resp = await client.post(
            f"{API_BASE}/post/publish/creator_info/query/",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        error = _error_of(resp)
        if error is not None:
            raise error
        return resp.json().get("data") or {}

    async def compose_info(
        self, session: AsyncSession, channel: PublishingChannel
    ) -> dict[str, Any]:
        """The creator's current info, which the editor shows and builds the
        privacy and interaction options from, as TikTok requires."""
        try:
            token = await self._access_token(session, channel)
            async with httpx.AsyncClient(timeout=30.0) as client:
                info = await self._creator_info(client, token)
        except _TikTokError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return {"can_post": False, "message": exc.message}
        except (httpx.HTTPError, ValueError):
            return {"can_post": False, "message": "No se pudo consultar la cuenta de TikTok."}
        return {
            "can_post": True,
            "message": None,
            "nickname": info.get("creator_nickname"),
            "username": info.get("creator_username"),
            "avatar_url": info.get("creator_avatar_url"),
            "privacy_level_options": [
                p for p in info.get("privacy_level_options") or [] if p in PRIVACY_LEVELS
            ],
            "comment_disabled": bool(info.get("comment_disabled")),
            "duet_disabled": bool(info.get("duet_disabled")),
            "stitch_disabled": bool(info.get("stitch_disabled")),
            "max_video_post_duration_sec": info.get("max_video_post_duration_sec"),
        }

    # -- Publishing ---------------------------------------------------------
    def validate(
        self, publication: Publication, target: PublicationTarget
    ) -> list[str]:
        errors: list[str] = []
        media = publication.media or []
        videos = [m for m in media if m.get("type") == "video"]
        images = [m for m in media if m.get("type") == "image"]
        text = target_text(publication, target)
        if not media:
            errors.append("TikTok necesita un video o al menos una foto.")
        elif videos and images:
            errors.append("En TikTok se publica un video o fotos, sin mezclarlos.")
        elif len(videos) > 1:
            errors.append("TikTok publica un solo video por publicación.")
        elif len(images) > PHOTOS_MAX:
            errors.append(f"TikTok admite hasta {PHOTOS_MAX} fotos por publicación.")
        elif any(_extension(m.get("url") or "") not in PHOTO_EXTENSIONS for m in images):
            errors.append("TikTok solo acepta fotos en JPG o WebP.")
        limit = PHOTO_TEXT_MAX if images and not videos else VIDEO_TEXT_MAX
        if len(text) > limit:
            errors.append(f"El texto para TikTok supera los {limit} caracteres.")
        chosen = tiktok_settings(target)
        if chosen["privacy_level"] not in PRIVACY_LEVELS:
            errors.append("Elegí quién puede ver la publicación en TikTok.")
        if chosen["disclose"] and not (chosen["brand_organic"] or chosen["brand_content"]):
            errors.append(
                "Indicá si el contenido de TikTok promociona tu marca, a un tercero o ambos."
            )
        if chosen["brand_content"] and chosen["privacy_level"] == "SELF_ONLY":
            errors.append("En TikTok, el contenido de marca no puede tener visibilidad «Solo yo».")
        return errors

    async def publish(
        self,
        session: AsyncSession,
        publication: Publication,
        target: PublicationTarget,
    ) -> PublishResult:
        channel = await session.get(PublishingChannel, target.channel_id)
        if channel is None or not (channel.credentials or {}).get("access_token"):
            return PublishResult(
                ok=False, error_code="missing_channel", error_message=_MISSING_CHANNEL
            )
        chosen = tiktok_settings(target)
        media = publication.media or []
        text = target_text(publication, target)
        try:
            token = await self._access_token(session, channel)
            async with httpx.AsyncClient(timeout=60.0) as client:
                info = await self._creator_info(client, token)
                if chosen["privacy_level"] not in (info.get("privacy_level_options") or []):
                    raise _TikTokError(
                        _ERROR_MESSAGES["privacy_level_option_mismatch"],
                        code="privacy_level_option_mismatch",
                    )
                headers = {"Authorization": f"Bearer {token}"}
                post_info: dict[str, Any] = {
                    "privacy_level": chosen["privacy_level"],
                    "disable_comment": not chosen["allow_comment"]
                    or bool(info.get("comment_disabled")),
                    "brand_organic_toggle": chosen["disclose"] and chosen["brand_organic"],
                    "brand_content_toggle": chosen["disclose"] and chosen["brand_content"],
                }
                if media and media[0].get("type") == "video":
                    post_info.update(
                        title=text,
                        disable_duet=not chosen["allow_duet"] or bool(info.get("duet_disabled")),
                        disable_stitch=not chosen["allow_stitch"]
                        or bool(info.get("stitch_disabled")),
                    )
                    url = f"{API_BASE}/post/publish/video/init/"
                    body: dict[str, Any] = {
                        "post_info": post_info,
                        "source_info": {"source": "PULL_FROM_URL", "video_url": media[0]["url"]},
                    }
                else:
                    post_info["description"] = text
                    url = f"{API_BASE}/post/publish/content/init/"
                    body = {
                        "post_info": post_info,
                        "source_info": {
                            "source": "PULL_FROM_URL",
                            "photo_cover_index": 0,
                            "photo_images": [m["url"] for m in media],
                        },
                        "post_mode": "DIRECT_POST",
                        "media_type": "PHOTO",
                    }
                resp = await client.post(url, headers=headers, json=body)
                error = _error_of(resp)
                if error is not None:
                    raise error
                publish_id = (resp.json().get("data") or {}).get("publish_id")
                if not publish_id:
                    raise _TikTokError("TikTok no devolvió el identificador de la publicación.")
                post_id = await self._wait_until_published(client, headers, str(publish_id))
        except _TikTokError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return PublishResult(
                ok=False,
                error_code=exc.code,
                error_message=exc.message,
                retryable=exc.retryable,
            )
        except httpx.HTTPError as exc:
            log.warning("tiktok.publish.transport target_id=%s err=%s", target.id, type(exc).__name__)
            return PublishResult(
                ok=False,
                error_code="network_error",
                error_message="No se pudo conectar con TikTok; se reintenta más tarde.",
                retryable=True,
            )
        username = info.get("creator_username")
        return PublishResult(
            ok=True,
            external_id=post_id or str(publish_id),
            # Private posts have no public id: no link to them.
            permalink=(
                f"https://www.tiktok.com/@{username}/video/{post_id}"
                if post_id and username
                else None
            ),
            extra={"publish_id": str(publish_id)},
        )

    @staticmethod
    async def _wait_until_published(
        client: httpx.AsyncClient, headers: dict[str, str], publish_id: str
    ) -> str | None:
        """Poll the post until TikTok finishes it. Returns its public id
        (``None`` while it isn't public). It can't be retried once TikTok
        took it, so a post still processing after the wait fails without
        retry, asking to check the profile first."""
        waited = 0.0
        while True:
            resp = await client.post(
                f"{API_BASE}/post/publish/status/fetch/",
                headers=headers,
                json={"publish_id": publish_id},
            )
            error = _error_of(resp)
            if error is not None and not error.retryable:
                raise error
            data = (resp.json().get("data") or {}) if error is None else {}
            status = data.get("status")
            if status == "PUBLISH_COMPLETE":
                ids = data.get("publicaly_available_post_id") or []
                return str(ids[0]) if ids else None
            if status == "FAILED":
                reason = str(data.get("fail_reason") or "")
                raise _TikTokError(
                    _FAIL_REASONS.get(reason, f"TikTok no pudo publicar: {reason or 'sin detalle'}."),
                    code=reason or "failed",
                    reconnect=reason == "auth_removed",
                )
            if waited >= POLL_MAX_SECONDS:
                raise _TikTokError(
                    "TikTok sigue procesando la publicación; revisá la cuenta antes de "
                    "reintentar.",
                    code="publish_timeout",
                )
            await asyncio.sleep(POLL_SECONDS)
            waited += POLL_SECONDS


__all__ = ["TikTokAdapter", "tiktok_settings"]
