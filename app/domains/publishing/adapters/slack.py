"""Slack adapter: publishes to a workspace channel through an incoming webhook.

Written from Slack's incoming webhooks and Block Kit documentation. In Slack,
api.slack.com/apps → Create New App → From scratch → Incoming Webhooks →
on → Add New Webhook to Workspace → pick the channel → copy the URL, pasted
here with the channel's name (the webhook doesn't say it).
``connect_with_fields`` checks the URL by posting an empty message: Slack
answers ``no_text`` (400) for a live webhook, without posting anything, and
403/404/410 for a revoked one or a gone channel.

Publishing is ``POST`` to the webhook: the text (plus a link per video, which
Slack unfurls) as a ``section`` block in mrkdwn and each image as an
``image`` block; the top-level ``text`` is the notification's fallback.
Slack answers ``ok`` and no message id, so there is no link to the post, and
webhooks report no figures.

The channel keeps the webhook URL (it is the credential: anyone holding it
can post) in ``credentials`` and the webhook id (``B…``) in ``external_id``.
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

# A section block's text holds up to 3000 characters.
CONTENT_MAX = 3000
IMAGES_MAX = 10
FALLBACK_MAX = 150
_WEBHOOK_RE = re.compile(r"^https://hooks\.slack\.com/services/(T\w+)/(B\w+)/(\w+)/?$")
_RECONNECT_MESSAGE = (
    "El webhook de Slack ya no funciona (se revocó, o el canal se archivó o borró). "
    "Creá uno nuevo y volvé a conectar el canal."
)


def _content(text: str, media: list[dict[str, Any]]) -> str:
    """The message text: the post's own, plus a link per video."""
    videos = [m["url"] for m in media if m["type"] == "video"]
    return "\n".join(part for part in (text, *videos) if part)


def _mrkdwn(text: str) -> str:
    """Slack reads ``&``, ``<`` and ``>`` as markup: escape them."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _images(media: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [m for m in media if m["type"] != "video"]


def _body(text: str, media: list[dict[str, Any]]) -> dict[str, Any]:
    content = _content(text, media)
    blocks: list[dict[str, Any]] = []
    if content:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": _mrkdwn(content)}})
    blocks += [
        {"type": "image", "image_url": m["url"], "alt_text": "imagen"} for m in _images(media)
    ]
    fallback = content[:FALLBACK_MAX] or "Imagen"
    return {"text": _mrkdwn(fallback), "blocks": blocks}


class SlackAdapter(PublishingAdapter):
    network = "slack"
    label = "Slack"
    connection_fields = (
        ConnectionField(
            name="webhook_url",
            label="URL del webhook",
            help=(
                "En api.slack.com/apps: Create New App → From scratch → Incoming "
                "Webhooks → activar → Add New Webhook to Workspace → elegir el canal "
                "→ copiar la URL (https://hooks.slack.com/services/…)."
            ),
            secret=True,
        ),
        ConnectionField(
            name="channel_name",
            label="Nombre del canal",
            help="El canal que elegiste en Slack, por ejemplo #novedades.",
        ),
    )

    # -- Connecting ---------------------------------------------------------
    async def connect_with_fields(self, values: dict[str, str]) -> ConnectedAccount:
        url = values["webhook_url"].rstrip("/")
        match = _WEBHOOK_RE.match(url)
        if match is None:
            raise ChannelConnectionError(
                "Esa no es una URL de webhook de Slack "
                "(empieza con https://hooks.slack.com/services/)."
            )
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json={})
        except httpx.HTTPError as exc:
            raise ChannelConnectionError("No se pudo conectar con Slack.") from exc
        # An empty message: a live webhook refuses it as ``no_text``.
        if resp.status_code in (403, 404, 410):
            raise ChannelConnectionError(
                "Slack no reconoce ese webhook (revocado, o el canal se archivó): "
                "copialo de nuevo desde la app de Slack."
            )
        if resp.status_code >= 500:
            raise ChannelConnectionError(f"Slack no respondió bien ({resp.status_code}).")
        name = values["channel_name"].strip()
        return ConnectedAccount(
            credentials={"webhook_url": url, "team_id": match.group(1)},
            external_id=match.group(2),
            name=name if name.startswith("#") else f"#{name}",
        )

    # -- Publishing ---------------------------------------------------------
    def validate(
        self, publication: Publication, target: PublicationTarget
    ) -> list[str]:
        errors: list[str] = []
        text = target_text(publication, target)
        media = publication.media or []
        if not text.strip() and not media:
            errors.append("Slack necesita texto o al menos una imagen o video.")
        if len(_content(text, media)) > CONTENT_MAX:
            errors.append(
                f"El texto para Slack, con los links de los videos, supera los "
                f"{CONTENT_MAX} caracteres."
            )
        if len(_images(media)) > IMAGES_MAX:
            errors.append(f"Slack admite hasta {IMAGES_MAX} imágenes por mensaje.")
        return errors

    async def publish(
        self,
        session: AsyncSession,
        publication: Publication,
        target: PublicationTarget,
    ) -> PublishResult:
        channel = await session.get(PublishingChannel, target.channel_id)
        url = ((channel.credentials or {}) if channel else {}).get("webhook_url")
        if channel is None or not url:
            return PublishResult(
                ok=False,
                error_code="missing_channel",
                error_message="El canal de Slack no está conectado.",
            )
        body = _body(target_text(publication, target), publication.media or [])
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=body)
        except httpx.TimeoutException:
            # It may have gone out: retrying could post it twice.
            return PublishResult(
                ok=False,
                error_code="publish_timeout",
                error_message="Slack no respondió a tiempo; revisá el canal antes de reintentar.",
            )
        except httpx.HTTPError as exc:
            log.warning("slack.publish.transport target_id=%s err=%s", target.id, type(exc).__name__)
            return PublishResult(
                ok=False,
                error_code="network_error",
                error_message="No se pudo conectar con Slack; se reintenta más tarde.",
                retryable=True,
            )
        if resp.status_code in (403, 404, 410):
            await mark_reconnect(session, channel.id, _RECONNECT_MESSAGE)  # type: ignore[arg-type]
            return PublishResult(
                ok=False, error_code=str(resp.status_code), error_message=_RECONNECT_MESSAGE
            )
        if resp.status_code == 429 or resp.status_code >= 500:
            return PublishResult(
                ok=False,
                error_code=str(resp.status_code),
                error_message="Slack limitó o no respondió los envíos por ahora; se reintenta más tarde.",
                retryable=True,
            )
        if resp.status_code >= 400:
            # Slack answers errors as plain text, e.g. ``invalid_blocks``.
            return PublishResult(
                ok=False,
                error_code=str(resp.status_code),
                error_message=f"Slack rechazó el mensaje: {resp.text.strip()[:200] or resp.status_code}",
            )
        return PublishResult(ok=True)


__all__ = ["SlackAdapter"]
