"""X adapter: publishes posts on the connected account.

Written from X's API documentation:

  * Connecting: OAuth 2.0 Authorization Code with PKCE as a confidential
    client (HTTP Basic with the Client ID and Secret at the token endpoint).
    The code verifier isn't stored: it's derived from the signed ``state``
    and the app's secret, so only this installation can produce it and each
    flow gets its own. Access tokens last 2 hours; ``offline.access`` gives a
    refresh token, replaced on each renewal, so a renewal is saved right away.
  * Publishing: ``POST /2/tweets``. Media is uploaded first with
    ``/2/media/upload/initialize``, ``/{id}/append`` (segments of at most
    5 MB) and ``/{id}/finalize``, then polled while X processes it. Up to 4
    images or 1 video.

The API is paid per request and a post with a link costs much more than one
without, so the editor warns about links. Reading figures is paid as well, so
none are fetched.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import re
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

AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
API_BASE = "https://api.x.com/2"
TOKEN_URL = f"{API_BASE}/oauth2/token"
SCOPES: tuple[str, ...] = (
    "tweet.read",
    "tweet.write",
    "users.read",
    "media.write",
    "offline.access",
)

TEXT_MAX = 280
URL_LENGTH = 23
IMAGES_MAX = 4
SEGMENT_BYTES = 5 * 1024 * 1024
ACCESS_MARGIN = timedelta(minutes=5)
PROCESSING_MAX_SECONDS = 300

_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
# Code points X counts as one character; the rest (emoji, CJK…) count as two.
_LIGHT_RANGES = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))
_RECONNECT_MESSAGE = "El acceso a X venció o se revocó. Volvé a conectar la cuenta."
_MISSING_CHANNEL = "La cuenta de X no está conectada."


def x_length(text: str) -> int:
    """``text`` as X counts it against the limit: each link is 23 characters,
    and characters outside the light ranges count double."""
    total = 0
    position = 0
    for match in _URL_RE.finditer(text):
        total += _weighted(text[position : match.start()]) + URL_LENGTH
        position = match.end()
    return total + _weighted(text[position:])


def _weighted(text: str) -> int:
    return sum(
        1 if any(low <= ord(char) <= high for low, high in _LIGHT_RANGES) else 2
        for char in text
    )


def _code_verifier(state: str) -> str:
    digest = hmac.new(
        get_settings().secret_key.encode(), f"x-pkce:{state}".encode(), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _client_auth() -> tuple[str, str]:
    settings = get_settings()
    return (settings.x_client_id, settings.x_client_secret)


def _now() -> datetime:
    return datetime.now(UTC)


class _XError(Exception):
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


def _error_of(resp: httpx.Response) -> _XError:
    try:
        payload = resp.json()
    except ValueError:
        payload = {}
    detail = None
    if isinstance(payload, dict):
        detail = (
            payload.get("detail")
            or payload.get("error_description")
            or payload.get("title")
            or payload.get("message")
        )
    status = resp.status_code
    if status == 401:
        return _XError(_RECONNECT_MESSAGE, code="401", reconnect=True)
    if status == 402:
        return _XError(
            "La cuenta de desarrollador de X se quedó sin crédito. Cargá crédito en "
            "console.x.com y reintentá.",
            code="402",
        )
    if status == 429 or status >= 500:
        return _XError(
            "X limitó o no respondió las solicitudes por ahora; se reintenta más tarde.",
            code=str(status),
            retryable=True,
        )
    return _XError(f"X rechazó la solicitud: {detail or status}", code=str(status))


def _credentials_of(
    tokens: dict[str, Any], *, previous: dict[str, Any] | None = None
) -> Credentials:
    credentials = {**(previous or {}), "access_token": tokens["access_token"]}
    if isinstance(tokens.get("refresh_token"), str):
        credentials["refresh_token"] = tokens["refresh_token"]
    if isinstance(tokens.get("expires_in"), int):
        credentials["access_expires_at"] = (
            _now() + timedelta(seconds=tokens["expires_in"])
        ).isoformat()
    return Credentials(credentials=credentials)


def _access_expired(credentials: dict[str, Any]) -> bool:
    raw = credentials.get("access_expires_at")
    if not isinstance(raw, str):
        return True
    try:
        expires = datetime.fromisoformat(raw)
    except ValueError:
        return True
    return expires - ACCESS_MARGIN <= _now()


def _media_category(media_type: str, kind: str) -> str:
    if kind == "video":
        return "tweet_video"
    return "tweet_gif" if media_type == "image/gif" else "tweet_image"


class XAdapter(PublishingAdapter):
    network = "x"
    label = "X"

    # -- Connecting ---------------------------------------------------------
    def missing_connection_settings(self) -> list[str]:
        settings = get_settings()
        named = (
            ("X_CLIENT_ID", settings.x_client_id),
            ("X_CLIENT_SECRET", settings.x_client_secret),
            ("PUBLISHING_OAUTH_REDIRECT_URI", settings.publishing_oauth_redirect_uri),
        )
        return [name for name, value in named if not value]

    def authorize_url(self, *, state: str, redirect_uri: str) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": get_settings().x_client_id,
                "redirect_uri": redirect_uri,
                "scope": " ".join(SCOPES),
                "state": state,
                "code_challenge": _code_challenge(_code_verifier(state)),
                "code_challenge_method": "S256",
            },
            quote_via=quote,
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def complete_authorization_for_state(
        self, *, code: str, redirect_uri: str, state: str
    ) -> ConnectedAccount:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    TOKEN_URL,
                    auth=_client_auth(),
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "code_verifier": _code_verifier(state),
                    },
                )
                if resp.status_code >= 400:
                    raise _error_of(resp)
                tokens = resp.json()
                token = tokens.get("access_token")
                if not isinstance(token, str) or not token:
                    raise _XError("X no devolvió un token de acceso.")
                resp = await client.get(
                    f"{API_BASE}/users/me",
                    params={"user.fields": "profile_image_url"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code >= 400:
                    raise _error_of(resp)
                user = (resp.json() or {}).get("data") or {}
        except _XError as exc:
            raise ChannelConnectionError(exc.message) from exc
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("x.connect.transport err=%s", type(exc).__name__)
            raise ChannelConnectionError("No se pudo conectar con X.") from exc
        fresh = _credentials_of(tokens)
        return ConnectedAccount(
            credentials=fresh.credentials,
            external_id=str(user.get("id") or ""),
            name=user.get("name"),
            username=user.get("username"),
            avatar_url=user.get("profile_image_url"),
        )

    async def refresh_credentials(
        self, channel: PublishingChannel
    ) -> Credentials | None:
        credentials = channel.credentials or {}
        refresh = credentials.get("refresh_token")
        if not refresh:
            raise ChannelConnectionError(_RECONNECT_MESSAGE)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    TOKEN_URL,
                    auth=_client_auth(),
                    data={"grant_type": "refresh_token", "refresh_token": refresh},
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                return None
            if resp.status_code >= 400:
                raise ChannelConnectionError(_RECONNECT_MESSAGE)
            tokens = resp.json()
        except (httpx.HTTPError, ValueError):
            return None
        if not isinstance(tokens.get("access_token"), str):
            return None
        return _credentials_of(tokens, previous=credentials)

    async def _access_token(self, session: AsyncSession, channel: PublishingChannel) -> str:
        """A usable access token, renewed first when its 2 hours are over. The
        renewal is saved right away: X has already replaced the refresh token."""
        credentials = channel.credentials or {}
        token = credentials.get("access_token")
        if isinstance(token, str) and token and not _access_expired(credentials):
            return token
        try:
            fresh = await self.refresh_credentials(channel)
        except ChannelConnectionError as exc:
            raise _XError(str(exc), code="refresh_failed", reconnect=True) from exc
        if fresh is None:
            raise _XError(
                "No se pudo renovar el acceso a X por ahora; se reintenta más tarde.",
                code="refresh_unavailable",
                retryable=True,
            )
        channel.credentials = fresh.credentials
        session.add(channel)
        await session.flush()
        return str(fresh.credentials["access_token"])

    # -- Publishing ---------------------------------------------------------
    def text_length(self, text: str) -> int:
        return x_length(text)

    def validate(
        self, publication: Publication, target: PublicationTarget
    ) -> list[str]:
        errors: list[str] = []
        text = target_text(publication, target)
        media = publication.media or []
        if not text.strip() and not media:
            errors.append("X necesita texto o al menos una imagen o video.")
        if x_length(text) > TEXT_MAX:
            errors.append(
                f"El texto para X supera los {TEXT_MAX} caracteres (cada link cuenta "
                f"como {URL_LENGTH} y cada emoji como 2)."
            )
        videos = [m for m in media if m.get("type") == "video"]
        if videos and len(media) > 1:
            errors.append("X admite 1 video solo, sin otras imágenes o videos.")
        elif len(media) > IMAGES_MAX:
            errors.append(f"X admite hasta {IMAGES_MAX} imágenes por publicación.")
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
        body: dict[str, Any] = {}
        text = target_text(publication, target)
        if text:
            body["text"] = text
        try:
            token = await self._access_token(session, channel)
            async with httpx.AsyncClient(timeout=120.0) as client:
                media_ids = [
                    await self._upload(client, token, m) for m in publication.media or []
                ]
                if media_ids:
                    body["media"] = {"media_ids": media_ids}
                try:
                    resp = await client.post(
                        f"{API_BASE}/tweets",
                        headers={"Authorization": f"Bearer {token}"},
                        json=body,
                    )
                except httpx.TimeoutException:
                    # It may have gone out: retrying could post it twice.
                    return PublishResult(
                        ok=False,
                        error_code="publish_timeout",
                        error_message=(
                            "X no respondió a tiempo al publicar; revisá la cuenta antes "
                            "de reintentar."
                        ),
                    )
                if resp.status_code >= 400:
                    raise _error_of(resp)
                post_id = ((resp.json() or {}).get("data") or {}).get("id")
        except _XError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return PublishResult(
                ok=False,
                error_code=exc.code,
                error_message=exc.message,
                retryable=exc.retryable,
            )
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("x.publish.transport target_id=%s err=%s", target.id, type(exc).__name__)
            return PublishResult(
                ok=False,
                error_code="network_error",
                error_message="No se pudo conectar con X; se reintenta más tarde.",
                retryable=True,
            )
        author = channel.username or "i"
        return PublishResult(
            ok=True,
            external_id=str(post_id) if post_id else None,
            permalink=f"https://x.com/{author}/status/{post_id}" if post_id else None,
        )

    async def _upload(
        self, client: httpx.AsyncClient, token: str, media: dict[str, Any]
    ) -> str:
        """Upload a file (read from its public link) by segments, without
        holding a whole video in memory, and return its media id once X has
        finished processing it."""
        headers = {"Authorization": f"Bearer {token}"}
        async with client.stream("GET", media["url"], follow_redirects=True) as source:
            total = source.headers.get("content-length")
            if source.status_code >= 400 or not total:
                raise _XError("No se pudo leer el archivo para subirlo a X.")
            media_type = source.headers.get("content-type", "").split(";")[0].strip()
            resp = await client.post(
                f"{API_BASE}/media/upload/initialize",
                headers=headers,
                json={
                    "media_type": media_type,
                    "total_bytes": int(total),
                    "media_category": _media_category(media_type, str(media.get("type"))),
                },
            )
            if resp.status_code >= 400:
                raise _error_of(resp)
            media_id = ((resp.json() or {}).get("data") or {}).get("id")
            if not media_id:
                raise _XError("X no devolvió dónde subir el archivo.")
            index = 0
            async for segment in source.aiter_bytes(chunk_size=SEGMENT_BYTES):
                resp = await client.post(
                    f"{API_BASE}/media/upload/{media_id}/append",
                    headers=headers,
                    data={"segment_index": str(index)},
                    files={"media": ("segment", segment, "application/octet-stream")},
                )
                if resp.status_code >= 400:
                    raise _error_of(resp)
                index += 1
        resp = await client.post(
            f"{API_BASE}/media/upload/{media_id}/finalize", headers=headers
        )
        if resp.status_code >= 400:
            raise _error_of(resp)
        await self._wait_until_processed(
            client, headers, str(media_id), ((resp.json() or {}).get("data") or {})
        )
        return str(media_id)

    @staticmethod
    async def _wait_until_processed(
        client: httpx.AsyncClient,
        headers: dict[str, str],
        media_id: str,
        data: dict[str, Any],
    ) -> None:
        waited = 0
        while True:
            info = data.get("processing_info")
            state = info.get("state") if isinstance(info, dict) else None
            if state is None or state == "succeeded":
                return
            if state == "failed":
                detail = (info.get("error") or {}).get("message")
                raise _XError(f"X no pudo procesar el archivo: {detail or 'error desconocido'}")
            seconds = max(int(info.get("check_after_secs") or 0), 0)
            waited += max(seconds, 1)
            if waited > PROCESSING_MAX_SECONDS:
                raise _XError(
                    "X tardó demasiado en procesar el archivo; se reintenta más tarde.",
                    code="processing_timeout",
                    retryable=True,
                )
            await asyncio.sleep(seconds)
            resp = await client.get(
                f"{API_BASE}/media/upload",
                headers=headers,
                params={"command": "STATUS", "media_id": media_id},
            )
            if resp.status_code >= 400:
                raise _error_of(resp)
            data = (resp.json() or {}).get("data") or {}


__all__ = ["XAdapter", "x_length"]
