"""Discord adapter: publishes to a server channel through a channel webhook.

Written from Discord's webhook documentation. There is no app or bot to
register: in Discord, Channel settings → Integrations → Webhooks → New
webhook → Copy URL, pasted here. ``connect_with_fields`` checks it with
``GET /webhooks/{id}/{token}`` (which also says the server and channel).

Publishing is ``POST /webhooks/{id}/{token}?wait=true`` (``wait`` makes
Discord answer with the message, for its link): the text as ``content``,
each image as an embed and each video as a link in the text, which Discord
previews. Webhooks report no figures.

The channel keeps the webhook URL (it is the credential: anyone holding it
can post) plus the server and channel ids in ``credentials``, and the
webhook id in ``external_id``.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.publishing.adapters.base import (
    ChannelConnectionError,
    ConnectedAccount,
    ConnectionField,
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

CONTENT_MAX = 2000
EMBEDS_MAX = 10
_WEBHOOK_RE = re.compile(
    r"^https://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/api(?:/v\d+)?/webhooks/(\d+)/([\w-]+)/?$"
)
_RECONNECT_MESSAGE = (
    "El webhook de Discord ya no existe (se borró o se regeneró). "
    "Creá uno nuevo y volvé a conectar el canal."
)


def _content(text: str, media: list[dict[str, Any]]) -> str:
    """The message text: the post's own, plus a link per video."""
    videos = [m["url"] for m in media if m["type"] == "video"]
    return "\n".join(part for part in (text, *videos) if part)


def _embeds(media: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"image": {"url": m["url"]}} for m in media if m["type"] != "video"]


class DiscordAdapter(PublishingAdapter):
    network = "discord"
    label = "Discord"
    connection_fields = (
        ConnectionField(
            name="webhook_url",
            label="URL del webhook",
            help=(
                "En Discord: Configuración del canal → Integraciones → Webhooks → "
                "Nuevo webhook → Copiar URL del webhook."
            ),
            secret=True,
        ),
    )

    # -- Connecting ---------------------------------------------------------
    async def connect_with_fields(self, values: dict[str, str]) -> ConnectedAccount:
        url = values["webhook_url"]
        match = _WEBHOOK_RE.match(url)
        if match is None:
            raise ChannelConnectionError(
                "Esa no es una URL de webhook de Discord "
                "(empieza con https://discord.com/api/webhooks/)."
            )
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
        except httpx.HTTPError as exc:
            raise ChannelConnectionError("No se pudo conectar con Discord.") from exc
        if resp.status_code in (401, 404):
            raise ChannelConnectionError(
                "Discord no encontró ese webhook: copialo de nuevo desde el canal."
            )
        if resp.status_code >= 400:
            raise ChannelConnectionError(
                f"Discord rechazó el webhook ({resp.status_code})."
            )
        try:
            hook = resp.json()
        except ValueError as exc:
            raise ChannelConnectionError("Discord respondió algo inesperado.") from exc
        webhook_id = str(hook.get("id") or match.group(1))
        avatar = hook.get("avatar")
        return ConnectedAccount(
            credentials={
                "webhook_url": url.rstrip("/"),
                "guild_id": hook.get("guild_id"),
                "channel_id": hook.get("channel_id"),
            },
            external_id=webhook_id,
            name=hook.get("name"),
            avatar_url=(
                f"https://cdn.discordapp.com/avatars/{webhook_id}/{avatar}.png"
                if avatar
                else None
            ),
        )

    # -- Publishing ---------------------------------------------------------
    def validate(
        self, publication: Publication, target: PublicationTarget
    ) -> list[str]:
        errors: list[str] = []
        text = target_text(publication, target)
        media = publication.media or []
        if not text.strip() and not media:
            errors.append("Discord necesita texto o al menos una imagen o video.")
        if len(_content(text, media)) > CONTENT_MAX:
            errors.append(
                f"El texto para Discord, con los links de los videos, supera los "
                f"{CONTENT_MAX} caracteres."
            )
        if len(_embeds(media)) > EMBEDS_MAX:
            errors.append(f"Discord admite hasta {EMBEDS_MAX} imágenes por mensaje.")
        return errors

    async def publish(
        self,
        session: AsyncSession,
        publication: Publication,
        target: PublicationTarget,
    ) -> PublishResult:
        channel = await session.get(PublishingChannel, target.channel_id)
        credentials = (channel.credentials or {}) if channel else {}
        url = credentials.get("webhook_url")
        if channel is None or not url:
            return PublishResult(
                ok=False,
                error_code="missing_channel",
                error_message="El canal de Discord no está conectado.",
            )
        media = publication.media or []
        body: dict[str, Any] = {"content": _content(target_text(publication, target), media)}
        embeds = _embeds(media)
        if embeds:
            body["embeds"] = embeds
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, params={"wait": "true"}, json=body)
        except httpx.TimeoutException:
            # It may have gone out: retrying could post it twice.
            return PublishResult(
                ok=False,
                error_code="publish_timeout",
                error_message="Discord no respondió a tiempo; revisá el canal antes de reintentar.",
            )
        except httpx.HTTPError as exc:
            log.warning("discord.publish.transport target_id=%s err=%s", target.id, type(exc).__name__)
            return PublishResult(
                ok=False,
                error_code="network_error",
                error_message="No se pudo conectar con Discord; se reintenta más tarde.",
                retryable=True,
            )
        if resp.status_code in (401, 404):
            await mark_reconnect(session, channel.id, _RECONNECT_MESSAGE)  # type: ignore[arg-type]
            return PublishResult(
                ok=False, error_code=str(resp.status_code), error_message=_RECONNECT_MESSAGE
            )
        if resp.status_code == 429 or resp.status_code >= 500:
            return PublishResult(
                ok=False,
                error_code=str(resp.status_code),
                error_message="Discord limitó o no respondió los envíos por ahora; se reintenta más tarde.",
                retryable=True,
            )
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        if resp.status_code >= 400:
            detail = payload.get("message") if isinstance(payload, dict) else None
            return PublishResult(
                ok=False,
                error_code=str(resp.status_code),
                error_message=f"Discord rechazó el mensaje: {detail or resp.status_code}",
            )
        message_id = payload.get("id") if isinstance(payload, dict) else None
        guild_id = credentials.get("guild_id")
        channel_id = payload.get("channel_id") or credentials.get("channel_id")
        permalink = (
            f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
            if message_id and guild_id and channel_id
            else None
        )
        return PublishResult(
            ok=True,
            external_id=str(message_id) if message_id else None,
            permalink=permalink,
        )


__all__ = ["DiscordAdapter"]
