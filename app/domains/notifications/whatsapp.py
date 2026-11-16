"""WhatsApp delivery for notifications — the WhatsApp counterpart of ``push``.

Only bot handoffs go out this way: each send is a paid Meta template, so it
is opt-in per user (``NotificationSetting.whatsapp_subscriptions`` plus
``whatsapp_number``) and the listener only enqueues it for
``conversation_bot_handoff``.

The notice leaves from the conversation's own WhatsApp number when it is a
WhatsApp inbox, otherwise from any WhatsApp number of the account. That
number needs the approved template :data:`TEMPLATE_NAME`, synced into
``WhatsappChannel.message_templates``; without it nothing is sent. It goes
in the recipient's language when that variant of the template is approved,
else in Spanish.

Body variables: ``{{1}}`` contact name, ``{{2}}`` inbox name, ``{{3}}``
conversation number.
"""

from __future__ import annotations

import re
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.i18n import DEFAULT_LOCALE, t, user_locale
from app.core.logging import get_logger
from app.domains.contacts.models import Contact
from app.domains.conversations.models import Conversation
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WHATSAPP,
    WHATSAPP_PROVIDER_CLOUD,
    Inbox,
    WhatsappChannel,
)
from app.domains.notifications.models import (
    Notification,
    NotificationSetting,
    notification_type_to_str,
)
from app.domains.users.models import User
from app.domains.whatsapp.template_processor import process_template_params
from app.domains.whatsapp.templates import send_template_message

log = get_logger("app.notifications.whatsapp")

TEMPLATE_NAME = "aviso_derivacion"
TEMPLATE_LANGUAGE = "es"
# The profile language → the code Meta uses for that template variant.
_META_LANGUAGE = {
    "es": "es",
    "en": "en",
    "pt": "pt_BR",
    "fr": "fr",
    "de": "de",
    "ja": "ja",
    "ko": "ko",
}
WHATSAPP_TYPES = frozenset({"conversation_bot_handoff"})


def _param(value: str | None, fallback: str) -> str:
    """Meta refuses parameters with newlines, tabs or long space runs."""
    text = re.sub(r"\s+", " ", value or "").strip()[:60]
    return text or fallback


async def _candidate_channels(
    session: AsyncSession, conversation: Conversation
) -> list[WhatsappChannel]:
    """The conversation's WhatsApp number first, then the account's others."""
    candidates: list[WhatsappChannel] = []
    inbox = await session.get(Inbox, conversation.inbox_id)
    if inbox is not None and inbox.channel_type == CHANNEL_TYPE_WHATSAPP:
        own = await session.get(WhatsappChannel, inbox.channel_id)
        if own is not None:
            candidates.append(own)
    candidates.extend(
        (
            await session.exec(
                select(WhatsappChannel)
                .where(WhatsappChannel.account_id == conversation.account_id)
                .order_by(WhatsappChannel.id)
            )
        ).all()
    )
    return [c for c in candidates if c.provider == WHATSAPP_PROVIDER_CLOUD]


async def send_notification_whatsapp(session: AsyncSession, *, notification_id: int) -> bool:
    """Send the WhatsApp notice for ``notification_id`` → whether it went out.

    Returns False (not raised) when the notification is gone, its type isn't
    offered on WhatsApp, the recipient hasn't opted in or has no number, or
    no WhatsApp number of the account has the approved template.
    """
    notification = await session.get(Notification, notification_id)
    if notification is None:
        return False
    type_str = notification_type_to_str(notification.notification_type)
    if type_str not in WHATSAPP_TYPES:
        return False

    setting = (
        await session.exec(
            select(NotificationSetting).where(
                NotificationSetting.account_id == notification.account_id,
                NotificationSetting.user_id == notification.user_id,
            )
        )
    ).first()
    if setting is None or not setting.whatsapp_number:
        return False
    if type_str not in (setting.whatsapp_subscriptions or []):
        return False
    if notification.primary_actor_type != "Conversation":
        return False
    conversation = await session.get(Conversation, notification.primary_actor_id)
    if conversation is None:
        return False

    contact = (
        await session.get(Contact, conversation.contact_id)
        if conversation.contact_id is not None
        else None
    )
    inbox = await session.get(Inbox, conversation.inbox_id)
    user = await session.get(User, notification.user_id)
    locale = user_locale(user)
    # (profile language, Meta template language) to try, in order.
    attempts = [(locale, _META_LANGUAGE.get(locale, TEMPLATE_LANGUAGE))]
    if attempts[0][1] != TEMPLATE_LANGUAGE:
        attempts.append((DEFAULT_LOCALE, TEMPLATE_LANGUAGE))

    def template_params(text_locale: str, language: str) -> dict[str, Any]:
        return {
            "name": TEMPLATE_NAME,
            "language": language,
            "processed_params": {
                "body": {
                    # The fallback is written in the template's language.
                    "1": _param(
                        contact.name if contact else None,
                        t(text_locale, "whatsapp.contact_fallback"),
                    ),
                    "2": _param(inbox.name if inbox else None, "AloStudio"),
                    "3": str(conversation.display_id),
                }
            },
        }

    # First number whose synced templates include the approved notice, in
    # the recipient's language if that variant exists, else in Spanish.
    channels = await _candidate_channels(session, conversation)
    template_info = None
    for text_locale, language in attempts:
        for channel in channels:
            template_info = process_template_params(
                template_params(text_locale, language), channel.message_templates
            )
            if template_info is not None:
                break
        if template_info is not None:
            break
    if template_info is None:
        log.info(
            "notifications.whatsapp.no_template notification_id=%s account_id=%s",
            notification_id,
            notification.account_id,
        )
        return False

    sent = await send_template_message(
        session,
        channel=channel,
        message=None,
        to_phone=setting.whatsapp_number,
        template_info=template_info,
    )
    log.info(
        "notifications.whatsapp.sent notification_id=%s channel_id=%s ok=%s",
        notification_id,
        channel.id,
        sent,
    )
    return sent


async def enqueue_notification_whatsapp(notification_id: int) -> None:
    """Best-effort enqueue of the WhatsApp task — never raises."""
    from arq import create_pool
    from arq.connections import RedisSettings

    try:
        pool = await create_pool(RedisSettings.from_dsn(get_settings().arq_redis_url))
        try:
            await pool.enqueue_job("send_notification_whatsapp_task", notification_id)
        finally:
            await pool.aclose()
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "notifications.whatsapp.enqueue_failed notification_id=%s err=%s",
            notification_id,
            exc,
        )


async def send_notification_whatsapp_task(
    ctx: dict[str, Any], notification_id: int
) -> dict[str, Any]:
    """ARQ task body — opens a session (reusing the worker engine on ``ctx``)
    and sends the notice."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = ctx.get("engine")
    if engine is None:
        engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    sessionmaker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with sessionmaker() as session:
        sent = await send_notification_whatsapp(session, notification_id=notification_id)
        await session.commit()
    return {"notification_id": notification_id, "sent": sent}


__all__ = [
    "TEMPLATE_NAME",
    "enqueue_notification_whatsapp",
    "send_notification_whatsapp",
    "send_notification_whatsapp_task",
]
