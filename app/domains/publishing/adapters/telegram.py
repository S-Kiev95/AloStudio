"""Telegram adapter: publishes to a channel or group through the business's
own bot.

Written from the Telegram Bot API reference (``api.telegram.org``). There is
no app to register: the business creates a bot with @BotFather, adds it as
an administrator of its channel (with permission to post) and pastes the
bot token and the channel here. ``connect_with_fields`` checks both with
``getMe``, ``getChat`` and ``getChatMember``.

Publishing: ``sendMessage`` for text, ``sendPhoto`` / ``sendVideo`` for one
file and ``sendMediaGroup`` for 2–10 (the caption goes on the first). Telegram
downloads the files from their public URLs itself (up to 5 MB for photos and
20 MB for other files). The Bot API reports no views for channel posts, so
the only figure is the channel's member count (``getChatMemberCount``).

The channel keeps the bot token in ``credentials["bot_token"]`` and the
chat id in ``external_id``. The token is part of every request path, so
URLs are never logged.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.publishing.adapters.base import (
    ChannelConnectionError,
    ConnectedAccount,
    ConnectionField,
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

API_HOST = "https://api.telegram.org"
TEXT_MAX = 4096
CAPTION_MAX = 1024
ALBUM_MAX = 10

_RECONNECT_MESSAGE = (
    "El bot ya no puede publicar en el canal (se quitó, perdió el permiso de "
    "administrador o cambió el token). Volvé a conectarlo."
)


class _TelegramError(Exception):
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


async def _call(
    client: httpx.AsyncClient, token: str, method: str, payload: dict[str, Any]
) -> Any:
    """One Bot API call → its ``result``. The token is in the path, so the
    request URL must never reach a log or an error message."""
    resp = await client.post(f"{API_HOST}/bot{token}/{method}", data=payload)
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if isinstance(body, dict) and body.get("ok") is True:
        return body.get("result")
    code = body.get("error_code") if isinstance(body, dict) else None
    description = (body.get("description") if isinstance(body, dict) else None) or ""
    status = code if isinstance(code, int) else resp.status_code
    if status in (401, 403, 404):
        # Bad token (401/404) or the bot was removed from the chat (403).
        raise _TelegramError(_RECONNECT_MESSAGE, code=str(status), reconnect=True)
    if status == 429 or status >= 500:
        raise _TelegramError(
            "Telegram limitó o no respondió los envíos por ahora; se reintenta más tarde.",
            code=str(status),
            retryable=True,
        )
    raise _TelegramError(
        f"Telegram rechazó la publicación: {description or status}".strip(),
        code=str(status),
    )


def _permalink(chat: PublishingChannel, message_id: Any) -> str | None:
    """Public link to a message: ``t.me/<username>/<id>`` for public chats,
    ``t.me/c/<id>/<id>`` (members only) for private channels."""
    if not isinstance(message_id, int):
        return None
    if chat.username:
        return f"https://t.me/{chat.username}/{message_id}"
    chat_id = chat.external_id or ""
    if chat_id.startswith("-100"):
        return f"https://t.me/c/{chat_id[4:]}/{message_id}"
    return None


class TelegramAdapter(PublishingAdapter):
    network = "telegram"
    label = "Telegram"
    connection_fields = (
        ConnectionField(
            name="bot_token",
            label="Token del bot",
            help="Lo da @BotFather cuando creás el bot.",
            secret=True,
        ),
        ConnectionField(
            name="chat",
            label="Canal o grupo",
            help=(
                "El @usuario del canal (por ejemplo @micanal) o su id numérico. "
                "El bot tiene que ser administrador con permiso para publicar."
            ),
        ),
    )

    # -- Connecting ---------------------------------------------------------
    async def connect_with_fields(self, values: dict[str, str]) -> ConnectedAccount:
        token = values["bot_token"]
        # Accept "@micanal", "micanal", "t.me/micanal" or the numeric id.
        chat_ref = values["chat"].removeprefix("https://").removeprefix("http://")
        chat_ref = chat_ref.removeprefix("t.me/").removeprefix("telegram.me/").strip("/")
        if not chat_ref.startswith("@") and not chat_ref.lstrip("-").isdigit():
            chat_ref = f"@{chat_ref}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    bot = await _call(client, token, "getMe", {})
                except _TelegramError as exc:
                    if exc.reconnect:
                        raise ChannelConnectionError(
                            "El token del bot no es válido. Copialo de nuevo de @BotFather."
                        ) from exc
                    raise
                try:
                    chat = await _call(client, token, "getChat", {"chat_id": chat_ref})
                    member = await _call(
                        client,
                        token,
                        "getChatMember",
                        {"chat_id": chat["id"], "user_id": bot["id"]},
                    )
                except _TelegramError as exc:
                    raise ChannelConnectionError(
                        f"El bot no encuentra {chat_ref}: agregalo al canal como "
                        "administrador y revisá el nombre."
                    ) from exc
        except _TelegramError as exc:
            raise ChannelConnectionError(exc.message) from exc
        except (httpx.HTTPError, KeyError, TypeError) as exc:
            log.warning("telegram.connect.failed err=%s", type(exc).__name__)
            raise ChannelConnectionError("No se pudo conectar con Telegram.") from exc

        status = member.get("status") if isinstance(member, dict) else None
        can_post = status == "creator" or (
            status == "administrator"
            # Only channels carry ``can_post_messages``; in groups an
            # administrator can always write.
            and member.get("can_post_messages", True) is not False
        )
        if not can_post:
            raise ChannelConnectionError(
                "El bot está en el canal pero no es administrador con permiso para publicar."
            )
        return ConnectedAccount(
            credentials={"bot_token": token},
            external_id=str(chat["id"]),
            name=chat.get("title") or chat.get("username"),
            username=chat.get("username"),
        )

    # -- Publishing ---------------------------------------------------------
    def validate(
        self, publication: Publication, target: PublicationTarget
    ) -> list[str]:
        errors: list[str] = []
        text = target_text(publication, target)
        media = publication.media or []
        if not text.strip() and not media:
            errors.append("Telegram necesita texto o al menos una imagen o video.")
        if media and len(text) > CAPTION_MAX:
            errors.append(
                f"Con imágenes o videos, el texto para Telegram admite hasta {CAPTION_MAX} caracteres."
            )
        elif len(text) > TEXT_MAX:
            errors.append(f"El texto para Telegram supera los {TEXT_MAX} caracteres.")
        if len(media) > ALBUM_MAX:
            errors.append(f"Un álbum de Telegram admite hasta {ALBUM_MAX} imágenes o videos.")
        return errors

    async def publish(
        self,
        session: AsyncSession,
        publication: Publication,
        target: PublicationTarget,
    ) -> PublishResult:
        channel = await session.get(PublishingChannel, target.channel_id)
        token = (channel.credentials or {}).get("bot_token") if channel else None
        if channel is None or not token or not channel.external_id:
            return PublishResult(
                ok=False,
                error_code="missing_channel",
                error_message="El canal de Telegram no está conectado.",
            )
        chat_id = channel.external_id
        text = target_text(publication, target)
        media = publication.media or []
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                if not media:
                    sent = await _call(
                        client, token, "sendMessage", {"chat_id": chat_id, "text": text}
                    )
                elif len(media) == 1:
                    kind = "video" if media[0]["type"] == "video" else "photo"
                    payload = {"chat_id": chat_id, kind: media[0]["url"]}
                    if text:
                        payload["caption"] = text
                    method = "sendVideo" if kind == "video" else "sendPhoto"
                    sent = await _call(client, token, method, payload)
                else:
                    album = [
                        {
                            "type": "video" if m["type"] == "video" else "photo",
                            "media": m["url"],
                        }
                        for m in media
                    ]
                    if text:
                        album[0]["caption"] = text
                    messages = await _call(
                        client,
                        token,
                        "sendMediaGroup",
                        {"chat_id": chat_id, "media": json.dumps(album)},
                    )
                    sent = messages[0] if isinstance(messages, list) and messages else {}
        except httpx.TimeoutException:
            # It may have gone out: retrying could post it twice.
            return PublishResult(
                ok=False,
                error_code="publish_timeout",
                error_message=(
                    "Telegram no respondió a tiempo; revisá el canal antes de reintentar."
                ),
            )
        except _TelegramError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return PublishResult(
                ok=False,
                error_code=exc.code,
                error_message=exc.message,
                retryable=exc.retryable,
            )
        except httpx.HTTPError as exc:
            log.warning("telegram.publish.transport target_id=%s err=%s", target.id, type(exc).__name__)
            return PublishResult(
                ok=False,
                error_code="network_error",
                error_message="No se pudo conectar con Telegram; se reintenta más tarde.",
                retryable=True,
            )
        message_id = sent.get("message_id") if isinstance(sent, dict) else None
        return PublishResult(
            ok=True,
            external_id=str(message_id) if message_id is not None else None,
            permalink=_permalink(channel, message_id),
        )

    # -- Figures --------------------------------------------------------------
    async def fetch_channel_metrics(
        self, session: AsyncSession, channel: PublishingChannel, *, days: list[date]
    ) -> MetricsResult | None:
        token = (channel.credentials or {}).get("bot_token")
        if not token or not channel.external_id:
            return None
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                count = await _call(
                    client, token, "getChatMemberCount", {"chat_id": channel.external_id}
                )
        except _TelegramError as exc:
            if exc.reconnect:
                await mark_reconnect(session, channel.id, exc.message)  # type: ignore[arg-type]
            return MetricsResult(ok=False, error_message=exc.message)
        except httpx.HTTPError:
            return MetricsResult(ok=False, error_message="No se pudo conectar con Telegram.")
        if not isinstance(count, int):
            return MetricsResult(ok=True)
        return MetricsResult(ok=True, metrics={"followers": count})


__all__ = ["TelegramAdapter"]
