"""Outgoing system mail (password resets, confirmations, invitations) through
the installation's SMTP server (``settings.smtp_*``, editable in Ajustes →
Instalación).

Delivery never raises: a mail server that is down or misconfigured is
logged, and the request that asked for the mail carries on.
"""

from __future__ import annotations

import asyncio
import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import get_settings

log = logging.getLogger(__name__)

# Sends started with :func:`send_mail_later`, kept so they aren't
# garbage-collected mid-flight (and so tests can wait for them).
_pending: set[asyncio.Task[bool]] = set()


async def send_mail(msg: EmailMessage, *, context: str) -> bool:
    """Send one message now. False (logged) when it couldn't be delivered."""
    settings = get_settings()
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=settings.smtp_tls,
            start_tls=False,
            timeout=10.0,
        )
    except (aiosmtplib.SMTPException, OSError, TimeoutError) as exc:
        log.warning("mail.send_failed context=%s error=%s", context, exc)
        return False
    log.info("mail.sent context=%s", context)
    return True


def send_mail_later(msg: EmailMessage, *, context: str) -> None:
    """Send in the background, so the request answers as fast whether or not
    a mail goes out (a reset request mustn't reveal which emails exist)."""
    task = asyncio.create_task(send_mail(msg, context=context))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


async def wait_for_pending_mail() -> None:
    """Tests: let background sends finish."""
    while _pending:
        await asyncio.gather(*list(_pending), return_exceptions=True)


def system_message(*, to: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = get_settings().mail_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


__all__ = ["send_mail", "send_mail_later", "system_message", "wait_for_pending_mail"]
