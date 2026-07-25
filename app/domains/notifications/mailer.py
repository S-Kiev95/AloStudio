"""Transactional email delivery for in-app notifications.

When the :mod:`app.domains.notifications.listener` creates a Notification
row, the recipient may also want it by email — gated by their
``NotificationSetting.email_subscriptions``. This module builds + sends
that mail via the installation SMTP config (``settings.smtp_*`` — the
same transport the agent-invite mailer uses) and exposes the ARQ task the
listener enqueues so the send never blocks the triggering request.

Ports the subset of Chatwoot's
``AgentNotifications::ConversationNotificationsMailer`` that maps to the
three notification types we currently emit (creation / assignment /
new-message on an assigned conversation).
"""

from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Any

import aiosmtplib
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.domains.conversations.models import Conversation
from app.domains.notifications.models import (
    Notification,
    NotificationSetting,
    notification_type_to_str,
)
from app.domains.users.models import User

log = logging.getLogger(__name__)

# Per-type subject + one-line lead. ``{n}`` is the conversation display id.
_SUBJECTS: dict[str, str] = {
    "conversation_creation": "Nueva conversación #{n}",
    "conversation_assignment": "Se te asignó la conversación #{n}",
    "assigned_conversation_new_message": "Nuevo mensaje en la conversación #{n}",
}
_LEADS: dict[str, str] = {
    "conversation_creation": (
        "Se creó una nueva conversación en una bandeja de la que sos miembro."
    ),
    "conversation_assignment": "Se te asignó una conversación.",
    "assigned_conversation_new_message": (
        "Recibiste un nuevo mensaje en una conversación asignada a vos."
    ),
}


def build_notification_email(
    *,
    notification: Notification,
    user: User,
    conversation: Conversation | None,
) -> EmailMessage:
    """Compose the plain-text notification email."""
    settings = get_settings()
    type_str = notification_type_to_str(notification.notification_type)
    display_id = conversation.display_id if conversation is not None else 0
    subject = _SUBJECTS.get(type_str, "Nueva notificación").format(n=display_id)
    lead = _LEADS.get(type_str, "Tenés una nueva notificación en AloStudio.")
    link = (
        f"{settings.app_base_url.rstrip('/')}"
        f"/accounts/{notification.account_id}/conversations/{display_id}"
    )
    greeting = user.name or user.email or ""
    msg = EmailMessage()
    msg["From"] = settings.mail_from
    msg["To"] = user.email or ""
    msg["Subject"] = subject
    msg.set_content(
        f"""Hola {greeting},

{lead}

Verla acá:

    {link}

Podés ajustar qué notificaciones recibís por email desde
Ajustes → Notificaciones.

— AloStudio
""",
    )
    return msg


async def send_notification_email(
    session: AsyncSession, *, notification_id: int
) -> bool:
    """Deliver the email for ``notification_id`` when the recipient is
    subscribed to its type.

    Returns ``True`` when a mail was sent, ``False`` otherwise
    (notification gone, not subscribed, no email address, or a transport
    error — all logged, never raised).
    """
    notification = await session.get(Notification, notification_id)
    if notification is None:
        return False

    type_str = notification_type_to_str(notification.notification_type)
    setting = (
        await session.exec(
            select(NotificationSetting).where(
                NotificationSetting.account_id == notification.account_id,
                NotificationSetting.user_id == notification.user_id,
            )
        )
    ).first()
    subscriptions = (setting.email_subscriptions if setting else []) or []
    if type_str not in subscriptions:
        return False

    user = await session.get(User, notification.user_id)
    if user is None or not user.email:
        return False

    conversation: Conversation | None = None
    if notification.primary_actor_type == "Conversation":
        conversation = await session.get(
            Conversation, notification.primary_actor_id
        )

    settings = get_settings()
    mail = build_notification_email(
        notification=notification, user=user, conversation=conversation
    )
    try:
        await aiosmtplib.send(
            mail,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=settings.smtp_tls,
            start_tls=False,
            timeout=10.0,
        )
    except (aiosmtplib.SMTPException, OSError, TimeoutError) as exc:
        log.warning(
            "notifications.email.send_failed notification_id=%s user_id=%s "
            "error=%s",
            notification_id,
            notification.user_id,
            exc,
        )
        return False

    log.info(
        "notifications.email.sent notification_id=%s user_id=%s type=%s",
        notification_id,
        notification.user_id,
        type_str,
    )
    return True


async def enqueue_notification_email(notification_id: int) -> None:
    """Best-effort enqueue of the send task on the ARQ queue.

    Never raises — with no reachable ARQ/Redis (dev without a worker) the
    email is simply skipped so the triggering request is never affected.
    """
    from arq import create_pool
    from arq.connections import RedisSettings

    settings = get_settings()
    try:
        pool = await create_pool(RedisSettings.from_dsn(settings.arq_redis_url))
        try:
            await pool.enqueue_job(
                "send_notification_email_task", notification_id
            )
        finally:
            await pool.aclose()
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "notifications.email.enqueue_failed notification_id=%s err=%s",
            notification_id,
            exc,
        )


async def send_notification_email_task(
    ctx: dict[str, Any], notification_id: int
) -> dict[str, Any]:
    """ARQ task body — opens a session (reusing the worker engine when the
    scheduler set one on ``ctx``) and delivers the email."""
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
        sent = await send_notification_email(
            session, notification_id=notification_id
        )
        await session.commit()
    return {"notification_id": notification_id, "sent": sent}


__all__ = [
    "build_notification_email",
    "enqueue_notification_email",
    "send_notification_email",
    "send_notification_email_task",
]
