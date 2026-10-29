"""Threads adapter: connects Threads profiles and publishes to them.

Written from Meta's Threads API documentation (host ``graph.threads.net``,
version ``v1.0``):

  * Connecting: the Authorization Window (``threads.net/oauth/authorize``),
    ``POST /oauth/access_token`` for a one-hour token, ``GET /access_token``
    (``th_exchange_token``) for a 60-day one and ``GET /me`` for the
    profile. ``GET /refresh_access_token`` (``th_refresh_token``) renews a
    long-lived token that is at least a day old and not yet expired.
  * Publishing: create a media container (``POST /{user}/threads``: TEXT,
    IMAGE, VIDEO, or CAROUSEL over 2–20 item containers), wait until its
    ``status`` is ``FINISHED`` and publish it (``POST /{user}/threads_publish``).
  * Figures: ``GET /{media}/insights`` and ``GET /{user}/threads_insights``
    (``threads_manage_insights``).
  * Plugs: a reply to the channel's own post (a TEXT container with
    ``reply_to_id``, ``threads_manage_replies``) and a repost
    (``POST /{media}/repost``).

The channel keeps the long-lived token in ``credentials["access_token"]``
and the Threads user id in ``external_id``. Like every adapter, nothing
here raises on a Threads-side failure.
"""

from __future__ import annotations

import asyncio
import logging
import unicodedata
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.publishing.adapters.base import (
    ChannelConnectionError,
    ConnectedAccount,
    Credentials,
    MetricsResult,
    PlugKind,
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

AUTHORIZE_URL = "https://threads.net/oauth/authorize"
GRAPH_HOST = "https://graph.threads.net"
GRAPH_VERSION = "v1.0"
SCOPES: tuple[str, ...] = (
    "threads_basic",
    "threads_content_publish",
    "threads_manage_insights",
    "threads_manage_replies",
)

PLUG_REPLY = "reply_after_likes"
PLUG_REPOST = "repost_after_likes"

TEXT_MAX = 500
CAROUSEL_MIN = 2
CAROUSEL_MAX = 20

# Containers need processing before they can be published (videos the
# longest): poll their status this often, for at most this long.
POLL_SECONDS = 5.0
POLL_MAX_SECONDS = 300.0

_TOKEN_CODES = {190}
_PERMISSION_CODES = {10} | set(range(200, 300))
_RATE_LIMIT_CODES = {4, 17, 32, 613}
_TRANSIENT_CODES = {1, 2}

_RECONNECT_MESSAGE = "El acceso a Threads venció o se revocó. Volvé a conectar la cuenta."
_MISSING_CHANNEL = "La cuenta de Threads no está conectada."


def threads_length(text: str) -> int:
    """Length as Threads counts it: emoji by their UTF-8 bytes, any other
    character as one."""
    total = 0
    for char in text:
        emoji = (
            ord(char) > 0xFFFF
            or unicodedata.category(char) in ("So", "Cf")
            or char == "️"
        )
        total += len(char.encode("utf-8")) if emoji else 1
    return total


class _ThreadsError(Exception):
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


def _error_of(resp: httpx.Response, *, doing: str) -> _ThreadsError:
    """Map a Threads error response (Graph shape, or the token endpoints'
    flat ``error_type`` / ``error_message``) to an error the owner can act on."""
    try:
        payload = resp.json()
    except ValueError:
        payload = {}
    err = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(err, dict):
        code, message = err.get("code"), err.get("message")
    elif isinstance(payload, dict):
        code, message = payload.get("code"), payload.get("error_message")
    else:
        code, message = None, None
    number = code if isinstance(code, int) else None
    if number in _TOKEN_CODES:
        return _ThreadsError(_RECONNECT_MESSAGE, code=str(number), reconnect=True)
    if number in _PERMISSION_CODES:
        return _ThreadsError(
            f"Threads no dio permiso para {doing}. Volvé a conectar la cuenta "
            "aceptando todos los permisos.",
            code=str(number),
        )
    if number in _RATE_LIMIT_CODES:
        return _ThreadsError(
            "Threads limitó las solicitudes por ahora; se reintenta más tarde.",
            code=str(number),
            retryable=True,
        )
    if number in _TRANSIENT_CODES or resp.status_code >= 500:
        return _ThreadsError(
            "Threads tuvo un error temporal; se reintenta más tarde.",
            code=str(number or resp.status_code),
            retryable=True,
        )
    return _ThreadsError(
        f"Threads rechazó la solicitud: {message or resp.status_code}".strip(),
        code=str(number or resp.status_code),
    )


class _Threads:
    """Minimal Threads client bound to one user token."""

    def __init__(self, client: httpx.AsyncClient, token: str) -> None:
        self.client = client
        self.token = token
        self.base = f"{GRAPH_HOST}/{GRAPH_VERSION}"

    async def _call(
        self,
        method: str,
        path: str,
        *,
        doing: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # The token rides in the form body on POST (kept out of logged
        # URLs), and in the query on GET.
        if method == "POST":
            data = {**(data or {}), "access_token": self.token}
        else:
            params = {**(params or {}), "access_token": self.token}
        resp = await self.client.request(
            method, f"{self.base}/{path}", data=data, params=params
        )
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        if resp.status_code >= 400 or (isinstance(payload, dict) and "error" in payload):
            raise _error_of(resp, doing=doing)
        return payload if isinstance(payload, dict) else {}

    async def create_container(self, user_id: str, fields: dict[str, Any]) -> str:
        res = await self._call(
            "POST", f"{user_id}/threads", data=fields, doing="publicar"
        )
        return str(res["id"])

    async def wait_until_ready(self, container_id: str) -> None:
        waited = 0.0
        while True:
            res = await self._call(
                "GET",
                container_id,
                params={"fields": "status,error_message"},
                doing="publicar",
            )
            status = res.get("status")
            if status in ("FINISHED", "PUBLISHED"):
                return
            if status in ("ERROR", "EXPIRED"):
                detail = res.get("error_message") or status
                raise _ThreadsError(f"Threads no pudo procesar el contenido ({detail}).")
            if waited >= POLL_MAX_SECONDS:
                raise _ThreadsError(
                    "Threads sigue procesando el contenido; se reintenta más tarde.",
                    retryable=True,
                )
            await asyncio.sleep(POLL_SECONDS)
            waited += POLL_SECONDS

    async def publish(self, user_id: str, container_id: str) -> str:
        res = await self._call(
            "POST",
            f"{user_id}/threads_publish",
            data={"creation_id": container_id},
            doing="publicar",
        )
        return str(res["id"])

    async def permalink(self, media_id: str) -> str | None:
        try:
            res = await self._call(
                "GET", media_id, params={"fields": "permalink"}, doing="publicar"
            )
        except _ThreadsError:
            return None
        link = res.get("permalink")
        return link if isinstance(link, str) else None

    async def insights(
        self, path: str, metrics: tuple[str, ...], **params: Any
    ) -> dict[str, int]:
        res = await self._call(
            "GET",
            path,
            params={"metric": ",".join(metrics), **params},
            doing="leer estadísticas (threads_manage_insights)",
        )
        figures: dict[str, int] = {}
        for item in res.get("data") or []:
            if not isinstance(item, dict):
                continue
            total = item.get("total_value")
            if isinstance(total, dict) and isinstance(total.get("value"), int):
                figures[item.get("name")] = total["value"]
                continue
            values = [
                v.get("value")
                for v in item.get("values") or []
                if isinstance(v, dict) and isinstance(v.get("value"), int)
            ]
            if values:
                # Lifetime metrics carry one value; a time series one per day.
                figures[item.get("name")] = sum(values)
        return figures


def _token_of(channel: PublishingChannel | None) -> str | None:
    token = (channel.credentials or {}).get("access_token") if channel else None
    return token if isinstance(token, str) and token else None


def _expires_at(payload: dict[str, Any]) -> datetime | None:
    seconds = payload.get("expires_in")
    if isinstance(seconds, int):
        return datetime.now(UTC) + timedelta(seconds=seconds)
    return None


class ThreadsAdapter(PublishingAdapter):
    network = "threads"
    label = "Threads"
    plug_kinds = (
        PlugKind(
            kind=PLUG_REPLY,
            label="Responder al llegar a N me gusta",
            description=(
                "Cuando un post llega a esa cantidad de me gusta, publica tu mensaje "
                "como respuesta a ese mismo post (por ejemplo, un link o una oferta)."
            ),
            message_max=TEXT_MAX,
        ),
        PlugKind(
            kind=PLUG_REPOST,
            label="Repostear al llegar a N me gusta",
            description=(
                "Cuando un post llega a esa cantidad de me gusta, lo repostea en tu "
                "perfil para que lo vuelvan a ver tus seguidores."
            ),
        ),
    )

    # -- Connecting ---------------------------------------------------------
    def missing_connection_settings(self) -> list[str]:
        settings = get_settings()
        named = (
            ("THREADS_APP_ID", settings.threads_app_id),
            ("THREADS_APP_SECRET", settings.threads_app_secret),
            ("PUBLISHING_OAUTH_REDIRECT_URI", settings.publishing_oauth_redirect_uri),
        )
        return [name for name, value in named if not value]

    def authorize_url(self, *, state: str, redirect_uri: str) -> str:
        query = urlencode(
            {
                "client_id": get_settings().threads_app_id,
                "redirect_uri": redirect_uri,
                "scope": ",".join(SCOPES),
                "response_type": "code",
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
                    f"{GRAPH_HOST}/oauth/access_token",
                    data={
                        "client_id": settings.threads_app_id,
                        "client_secret": settings.threads_app_secret,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                        "code": code,
                    },
                )
                if resp.status_code >= 400:
                    raise _error_of(resp, doing="conectar la cuenta")
                short = resp.json().get("access_token")
                resp = await client.get(
                    f"{GRAPH_HOST}/access_token",
                    params={
                        "grant_type": "th_exchange_token",
                        "client_secret": settings.threads_app_secret,
                        "access_token": short,
                    },
                )
                if resp.status_code >= 400:
                    raise _error_of(resp, doing="conectar la cuenta")
                long_lived = resp.json()
                token = long_lived.get("access_token")
                if not isinstance(token, str) or not token:
                    raise _ThreadsError("Threads no devolvió un token de acceso.")
                profile = await _Threads(client, token)._call(
                    "GET",
                    "me",
                    params={"fields": "id,username,name,threads_profile_picture_url"},
                    doing="leer el perfil",
                )
        except _ThreadsError as exc:
            raise ChannelConnectionError(exc.message) from exc
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("threads.connect.transport err=%s", exc)
            raise ChannelConnectionError("No se pudo conectar con Threads.") from exc
        return ConnectedAccount(
            credentials={"access_token": token},
            token_expires_at=_expires_at(long_lived),
            external_id=str(profile.get("id") or ""),
            name=profile.get("name") or profile.get("username"),
            username=profile.get("username"),
            avatar_url=profile.get("threads_profile_picture_url"),
        )

    async def refresh_credentials(
        self, channel: PublishingChannel
    ) -> Credentials | None:
        token = _token_of(channel)
        if token is None:
            raise ChannelConnectionError(_MISSING_CHANNEL)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{GRAPH_HOST}/refresh_access_token",
                    params={"grant_type": "th_refresh_token", "access_token": token},
                )
            if resp.status_code >= 400:
                raise _error_of(resp, doing="renovar el acceso")
            payload = resp.json()
        except _ThreadsError as exc:
            if exc.retryable:
                return None
            raise ChannelConnectionError(exc.message) from exc
        except (httpx.HTTPError, ValueError):
            # Tried again on the next run; the token is still valid.
            return None
        fresh = payload.get("access_token")
        if not isinstance(fresh, str) or not fresh:
            return None
        return Credentials(
            credentials={**(channel.credentials or {}), "access_token": fresh},
            token_expires_at=_expires_at(payload),
        )

    # -- Publishing ---------------------------------------------------------
    def text_length(self, text: str) -> int:
        return threads_length(text)

    def validate(
        self, publication: Publication, target: PublicationTarget
    ) -> list[str]:
        errors: list[str] = []
        text = target_text(publication, target)
        media = publication.media or []
        if not text.strip() and not media:
            errors.append("Threads necesita texto o al menos una imagen o video.")
        if self.text_length(text) > TEXT_MAX:
            errors.append(
                f"El texto para Threads supera los {TEXT_MAX} caracteres "
                "(cada emoji cuenta como varios)."
            )
        if len(media) > CAROUSEL_MAX:
            errors.append(
                f"Un carrusel de Threads admite hasta {CAROUSEL_MAX} imágenes o videos."
            )
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
        user_id = channel.external_id
        text = target_text(publication, target)
        media = publication.media or []
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                api = _Threads(client, token)
                container = await self._container(api, user_id, text, media)
                await api.wait_until_ready(container)
                try:
                    media_id = await api.publish(user_id, container)
                except httpx.TimeoutException:
                    # It may have gone out: retrying could post it twice.
                    return PublishResult(
                        ok=False,
                        error_code="publish_timeout",
                        error_message=(
                            "Threads no respondió a tiempo al publicar; revisá el "
                            "perfil antes de reintentar."
                        ),
                    )
                permalink = await api.permalink(media_id)
        except _ThreadsError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return PublishResult(
                ok=False,
                error_code=exc.code,
                error_message=exc.message,
                retryable=exc.retryable,
            )
        except httpx.HTTPError as exc:
            log.warning("threads.publish.transport target_id=%s err=%s", target.id, exc)
            return PublishResult(
                ok=False,
                error_code="network_error",
                error_message="No se pudo conectar con Threads; se reintenta más tarde.",
                retryable=True,
            )
        return PublishResult(ok=True, external_id=media_id, permalink=permalink)

    @staticmethod
    async def _container(
        api: _Threads, user_id: str, text: str, media: list[dict[str, Any]]
    ) -> str:
        def item(entry: dict[str, Any]) -> dict[str, Any]:
            if entry["type"] == "video":
                return {"media_type": "VIDEO", "video_url": entry["url"]}
            return {"media_type": "IMAGE", "image_url": entry["url"]}

        if not media:
            return await api.create_container(
                user_id, {"media_type": "TEXT", "text": text}
            )
        if len(media) < CAROUSEL_MIN:
            fields = item(media[0])
            if text:
                fields["text"] = text
            return await api.create_container(user_id, fields)
        children = []
        for entry in media:
            child = await api.create_container(
                user_id, {**item(entry), "is_carousel_item": "true"}
            )
            # A carousel can only be built from processed items.
            await api.wait_until_ready(child)
            children.append(child)
        fields = {"media_type": "CAROUSEL", "children": ",".join(children)}
        if text:
            fields["text"] = text
        return await api.create_container(user_id, fields)

    # -- Plugs ----------------------------------------------------------------
    async def run_plug(
        self,
        session: AsyncSession,
        *,
        kind: str,
        target: PublicationTarget,
        message: str | None,
    ) -> PublishResult:
        channel = await session.get(PublishingChannel, target.channel_id)
        token = _token_of(channel)
        if channel is None or token is None or not channel.external_id or not target.external_id:
            return PublishResult(
                ok=False, error_code="missing_channel", error_message=_MISSING_CHANNEL
            )
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                api = _Threads(client, token)
                if kind == PLUG_REPOST:
                    res = await api._call(
                        "POST", f"{target.external_id}/repost", doing="repostear"
                    )
                    return PublishResult(ok=True, external_id=str(res.get("id") or ""))
                container = await api.create_container(
                    channel.external_id,
                    {
                        "media_type": "TEXT",
                        "text": message or "",
                        "reply_to_id": target.external_id,
                    },
                )
                await api.wait_until_ready(container)
                reply_id = await api.publish(channel.external_id, container)
        except _ThreadsError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return PublishResult(
                ok=False, error_code=exc.code, error_message=exc.message, retryable=exc.retryable
            )
        except httpx.HTTPError:
            return PublishResult(
                ok=False,
                error_code="network_error",
                error_message="No se pudo conectar con Threads.",
                retryable=True,
            )
        return PublishResult(ok=True, external_id=reply_id)

    # -- Figures --------------------------------------------------------------
    async def fetch_post_metrics(
        self, session: AsyncSession, target: PublicationTarget
    ) -> MetricsResult | None:
        channel = await session.get(PublishingChannel, target.channel_id)
        token = _token_of(channel)
        if token is None or not target.external_id:
            return None
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                raw = await _Threads(client, token).insights(
                    f"{target.external_id}/insights",
                    ("views", "likes", "replies", "reposts", "quotes", "shares"),
                )
        except _ThreadsError as exc:
            if exc.reconnect:
                await mark_reconnect(session, target.channel_id, exc.message)
            return MetricsResult(ok=False, error_message=exc.message)
        except httpx.HTTPError:
            return MetricsResult(ok=False, error_message="No se pudo conectar con Threads.")
        metrics = _normalise(raw)
        if "views" in raw:
            metrics["views"] = raw["views"]
        return MetricsResult(ok=True, metrics=metrics)

    async def fetch_channel_metrics(
        self, session: AsyncSession, channel: PublishingChannel, *, days: list[date]
    ) -> MetricsResult | None:
        token = _token_of(channel)
        if token is None or not channel.external_id:
            return None
        path = f"{channel.external_id}/threads_insights"
        daily: dict[date, dict[str, int]] = {}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                api = _Threads(client, token)
                current = await api.insights(path, ("followers_count",))
                for day in days:
                    start = datetime.combine(day, time.min, tzinfo=UTC)
                    raw = await api.insights(
                        path,
                        ("views", "likes", "replies", "reposts", "quotes"),
                        since=int(start.timestamp()),
                        until=int((start + timedelta(days=1)).timestamp()),
                    )
                    figures: dict[str, int] = {}
                    if "views" in raw:
                        figures["views"] = raw["views"]
                    interactions = _normalise(raw).get("interactions")
                    if interactions is not None:
                        figures["interactions"] = interactions
                    if figures:
                        daily[day] = figures
        except _ThreadsError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return MetricsResult(ok=False, error_message=exc.message)
        except httpx.HTTPError:
            return MetricsResult(ok=False, error_message="No se pudo conectar con Threads.")
        metrics = (
            {"followers": current["followers_count"]} if "followers_count" in current else {}
        )
        return MetricsResult(ok=True, metrics=metrics, daily=daily)


def _normalise(raw: dict[str, int]) -> dict[str, int]:
    """Threads' engagement onto the shared keys: replies are comments, and
    reposts, quotes and shares all spread the post."""
    metrics: dict[str, int] = {}
    if "likes" in raw:
        metrics["likes"] = raw["likes"]
    if "replies" in raw:
        metrics["comments"] = raw["replies"]
    spread = [raw[k] for k in ("reposts", "quotes", "shares") if k in raw]
    if spread:
        metrics["shares"] = sum(spread)
    if metrics:
        metrics["interactions"] = sum(metrics.values())
    return metrics


__all__ = ["ThreadsAdapter", "threads_length"]
