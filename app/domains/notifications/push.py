"""Web-push delivery for notifications — the push counterpart of ``mailer``.

When an in-app notification is created, the listener best-effort enqueues
:func:`send_notification_push_task`. The task re-checks the recipient's push
preference (``NotificationSetting.push_subscriptions``), then encrypts +
POSTs a payload to each of the user's registered
:class:`NotificationSubscription` endpoints (RFC 8291, see
``app.core.webpush``). Dead endpoints (404/410) are pruned.

No-ops cleanly when VAPID isn't configured, so dev without keys is safe.
"""

from __future__ import annotations

import json
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.webpush import send_web_push
from app.domains.conversations.models import Conversation
from app.domains.notifications.models import (
    Notification,
    NotificationSetting,
    NotificationSubscription,
    notification_type_to_str,
)

log = get_logger("app.notifications.push")

# Human push titles per notification type (Spanish — matches the dashboard).
_PUSH_TITLES: dict[str, str] = {
    "conversation_creation": "Nueva conversación",
    "conversation_assignment": "Conversación asignada",
    "assigned_conversation_new_message": "Nuevo mensaje",
    "participating_conversation_new_message": "Nuevo mensaje",
    "conversation_mention": "Te mencionaron",
    "sla_missed_first_response": "SLA incumplido",
    "sla_missed_next_response": "SLA incumplido",
    "sla_missed_resolution": "SLA incumplido",
}


def _push_payload(
    notification: Notification, conversation: Conversation | None
) -> bytes:
    type_str = notification_type_to_str(notification.notification_type)
    title = _PUSH_TITLES.get(type_str, "Notificación")
    body = ""
    url = ""
    if conversation is not None:
        body = f"Conversación #{conversation.display_id}"
        base = get_settings().app_base_url.rstrip("/")
        url = (
            f"{base}/accounts/{conversation.account_id}"
            f"/conversations/{conversation.display_id}"
        )
    return json.dumps(
        {"title": title, "body": body, "url": url}, ensure_ascii=False
    ).encode("utf-8")


async def send_notification_push(
    session: AsyncSession, *, notification_id: int
) -> int:
    """Deliver web-push for ``notification_id`` → number of endpoints reached.

    Returns 0 (not raised) when web-push is unconfigured, the notification is
    gone, the recipient hasn't opted into push for this type, or has no
    registered subscriptions.
    """
    settings = get_settings()
    if not (settings.vapid_private_key and settings.vapid_public_key):
        return 0

    notification = await session.get(Notification, notification_id)
    if notification is None:
        return 0

    type_str = notification_type_to_str(notification.notification_type)
    setting = (
        await session.exec(
            select(NotificationSetting).where(
                NotificationSetting.account_id == notification.account_id,
                NotificationSetting.user_id == notification.user_id,
            )
        )
    ).first()
    if type_str not in ((setting.push_subscriptions if setting else []) or []):
        return 0

    subs = list(
        (
            await session.exec(
                select(NotificationSubscription).where(
                    NotificationSubscription.user_id == notification.user_id
                )
            )
        ).all()
    )
    if not subs:
        return 0

    conversation: Conversation | None = None
    if notification.primary_actor_type == "Conversation":
        conversation = await session.get(
            Conversation, notification.primary_actor_id
        )
    payload = _push_payload(notification, conversation)

    sent = 0
    dead = False
    for sub in subs:
        try:
            status = await send_web_push(
                sub.subscription_attributes,
                payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_public_key=settings.vapid_public_key,
                vapid_subject=settings.vapid_subject,
            )
        except Exception as exc:
            log.warning(
                "notifications.push.send_failed notification_id=%s err=%s",
                notification_id,
                exc,
            )
            continue
        if status in (404, 410):
            # Subscription expired / unsubscribed — prune it.
            await session.delete(sub)
            dead = True
        elif 200 <= status < 300:
            sent += 1
    if dead:
        await session.flush()
    log.info(
        "notifications.push.sent notification_id=%s reached=%s",
        notification_id,
        sent,
    )
    return sent


async def enqueue_notification_push(notification_id: int) -> None:
    """Best-effort enqueue of the push task — never raises (dev w/o worker)."""
    from arq import create_pool
    from arq.connections import RedisSettings

    settings = get_settings()
    if not (settings.vapid_private_key and settings.vapid_public_key):
        return
    try:
        pool = await create_pool(RedisSettings.from_dsn(settings.arq_redis_url))
        try:
            await pool.enqueue_job("send_notification_push_task", notification_id)
        finally:
            await pool.aclose()
    except Exception as exc:
        log.warning(
            "notifications.push.enqueue_failed notification_id=%s err=%s",
            notification_id,
            exc,
        )


async def send_notification_push_task(
    ctx: dict[str, Any], notification_id: int
) -> dict[str, Any]:
    """ARQ task body — opens a session (reusing the worker engine on ``ctx``)
    and delivers the push."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = ctx.get("engine")
    if engine is None:
        engine = create_async_engine(
            get_settings().database_url, pool_pre_ping=True
        )
    sessionmaker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with sessionmaker() as session:
        reached = await send_notification_push(
            session, notification_id=notification_id
        )
        await session.commit()
    return {"notification_id": notification_id, "reached": reached}


__all__ = [
    "enqueue_notification_push",
    "send_notification_push",
    "send_notification_push_task",
]
