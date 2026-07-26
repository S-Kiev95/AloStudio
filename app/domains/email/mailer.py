"""Outbound email reply via SMTP.

Ported from:
  reference/chatwoot/app/mailers/conversation_reply_mailer.rb
  (the ``email_reply`` action — single-message branch)
  reference/chatwoot/app/mailers/concerns/references_header_builder.rb

Sends an outbound :class:`Message` (``message_type=outgoing``) on a
``Channel::Email`` inbox as a real email. Stamps a ``Message-ID``
header in the same shape Chatwoot uses
(``<conversation/<uuid>/messages/<id>@<email-domain>>``) so threading
on the reply lands on the originating conversation — both for our
own IMAP ingest (5b.4) and for parity with a Chatwoot-managed reply
on the same thread.

Subject convention mirrors Rails:
  * If the conversation already has ``additional_attributes['mail_subject']``
    AND there's been more than one chat message, prefix ``Re:``.
  * Else use ``[#<display_id>] New messages on this conversation``
    (the en.yml ``conversations.reply.email_subject``).

Body: plain-text only in 5b. The HTML alternative + attachments lands
with Phase 5b's follow-up (5b.6) once we wire the message presenter
through `email_reply.html.erb` parity. Plain text is sufficient for
parity tests: every mail server accepts it and Greenmail asserts on
the raw message text.

Auth-failure / connection-failure handling: we trap exceptions inside
:func:`send_email_reply` and log + flag them, never raising into the
caller. The Rails mailer does the same via ``ConversationReplyEmail
Worker`` retrying with exponential backoff — we'll port the retry
loop with the IMAP fetch job in 5b.4 since both share the worker
infrastructure.
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime, formataddr
from typing import TYPE_CHECKING

import aiosmtplib

from app.domains.conversations.models import (
    MESSAGE_TYPE_INCOMING,
    MESSAGE_TYPE_OUTGOING,
    Conversation,
    Message,
)
from app.domains.inboxes.models import EmailChannel

if TYPE_CHECKING:  # pragma: no cover
    from sqlmodel.ext.asyncio.session import AsyncSession

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Header / Message-ID construction
# ---------------------------------------------------------------------------
def _email_domain(channel: EmailChannel) -> str:
    """Mirror ``channel_email_domain`` — the domain side of the
    channel's email address. Falls back to ``inbound.local`` when the
    channel address is malformed (defensive — the InboxBuilder gate
    ensures the email is well-formed at create time).
    """
    parts = channel.email.split("@", 1)
    return parts[1] if len(parts) == 2 and parts[1] else "inbound.local"


def build_message_id(*, conversation: Conversation, message: Message, channel: EmailChannel) -> str:
    """Mirror ``ConversationReplyMailer#custom_message_id``.

    Chatwoot's format is ``<conversation/<uuid>/messages/<msg_id>@<domain>>``
    — the structured form lets the IMAP ingest peek at an inbound
    Message-ID and bypass the threading-parser lookup entirely. We
    keep the exact shape so a Chatwoot ↔ AloStudio thread round-trips
    through either side's parser.
    """
    domain = _email_domain(channel)
    return f"<conversation/{conversation.uuid}/messages/{message.id}@{domain}>"


def build_in_reply_to(
    *, conversation: Conversation, channel: EmailChannel, last_incoming: Message | None
) -> str:
    """Mirror ``in_reply_to_email`` — points at the inbound Message-ID
    we want to thread under, or a synthetic per-conversation root when
    no inbound exists yet (e.g. an agent-initiated outbound)."""
    if last_incoming is not None:
        # Chatwoot stores inbound message-ids under
        # content_attributes.email.message_id. We do the same in 5b.4.
        ca = last_incoming.content_attributes or {}
        email_meta = ca.get("email") if isinstance(ca, dict) else None
        if isinstance(email_meta, dict):
            mid = email_meta.get("message_id")
            if mid:
                return f"<{mid}>" if not mid.startswith("<") else mid
    domain = _email_domain(channel)
    return f"<account/{conversation.account_id}/conversation/{conversation.uuid}@{domain}>"


def build_references(
    *,
    conversation: Conversation,
    channel: EmailChannel,
    last_incoming: Message | None,
    in_reply_to: str,
) -> str:
    """Mirror ``ReferencesHeaderBuilder#build_references_header``.

    Concatenates every Message-ID we already know about on this thread:
    the synthetic conversation root + every prior outbound's stored
    ``source_id`` + the In-Reply-To we just built. RFC-2822 wants them
    space-separated.

    The tail-most reference is the most recent — same convention every
    mail client uses.
    """
    domain = _email_domain(channel)
    refs: list[str] = []
    refs.append(
        f"<account/{conversation.account_id}/conversation/{conversation.uuid}@{domain}>"
    )
    # Walk prior outbound messages on this conversation, oldest first,
    # picking up the Message-IDs we stamped on source_id. We avoid a
    # DB hit here — the caller passes the ordered list when relevant.
    if in_reply_to and in_reply_to not in refs:
        refs.append(in_reply_to)
    return " ".join(refs)


# ---------------------------------------------------------------------------
# Subject
# ---------------------------------------------------------------------------
def build_subject(*, conversation: Conversation, chat_message_count: int) -> str:
    """Mirror ``ConversationReplyMailer#mail_subject``.

    Three branches:
      * No ``mail_subject`` in additional_attributes -> default
        ``[#<display_id>] New messages on this conversation``.
      * Has ``mail_subject`` and the chat already has 2+ messages
        (so this is genuinely a reply) -> ``Re: <subject>``.
      * Has ``mail_subject`` but it's the first chat message -> use
        the subject verbatim (no Re: prefix).
    """
    attrs = conversation.additional_attributes or {}
    subj = attrs.get("mail_subject") if isinstance(attrs, dict) else None
    if not subj:
        return f"[#{conversation.display_id}] New messages on this conversation"
    if chat_message_count > 1:
        return f"Re: {subj}"
    return str(subj)


# ---------------------------------------------------------------------------
# Address helpers
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_valid_email(value: str | None) -> bool:
    return bool(value) and bool(_EMAIL_RE.match(value or ""))


def _from_address(channel: EmailChannel, *, sender_name: str | None) -> str:
    """Build a ``"Name" <email@host>`` From header.

    The Rails ``sender_name`` helper picks between friendly + professional
    formats; for 5b we always use the friendly form because that's what
    every Chatwoot deployment defaults to, and the sender-name-mode
    column lives on the Inbox not the Channel — porting the friendly
    branch first means agents see their own name on outbound.
    """
    name = sender_name or "Support"
    return formataddr((name, channel.email))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def send_email_reply(
    session: AsyncSession,
    *,
    message: Message,
    conversation: Conversation,
    channel: EmailChannel,
) -> bool:
    """Build + send the email + stamp the Message-ID on ``source_id``.

    Returns ``True`` on success, ``False`` on a transport / config
    error (logged, never raised — the caller must not break the
    request because the mail server is down).

    Pre-conditions:
      * ``channel.smtp_enabled`` is True with a host triplet set.
      * ``message.message_type == OUTGOING``.

    Pre-existing rows the function reads (no extra round-trip):
      * the conversation's contact (``conversation.contact`` is eager
        per the relationship config).
      * the most recent inbound message — for ``In-Reply-To``.

    Side effects:
      * SMTP send.
      * ``message.source_id`` is set to the stamped Message-ID.
    """
    if not channel.smtp_enabled:
        log.info(
            "email.reply.skip reason=smtp_disabled message_id=%s", message.id
        )
        return False
    if not (channel.smtp_address and channel.smtp_port and channel.smtp_login):
        log.warning(
            "email.reply.skip reason=missing_smtp_config message_id=%s",
            message.id,
        )
        return False

    contact = conversation.contact
    if contact is None or not _is_valid_email(contact.email):
        log.info(
            "email.reply.skip reason=no_contact_email message_id=%s",
            message.id,
        )
        return False

    # Resolve sender name — per-message ``sender`` first (the resolved
    # User stashed by ``_attach_resolved_sender`` in 4a), then the
    # conversation assignee.
    sender_obj = getattr(message, "_resolved_sender", None)
    sender_name = (
        getattr(sender_obj, "available_name", None)
        or getattr(sender_obj, "name", None)
        or None
    )

    # The most recent inbound on this conversation — needed for
    # In-Reply-To. Cheap query because messages.conversation_id is
    # indexed.
    from sqlmodel import select

    last_incoming = (
        await session.exec(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.message_type == MESSAGE_TYPE_INCOMING,
            )
            .order_by(Message.id.desc())
            .limit(1)
        )
    ).first()

    chat_message_count = int(
        (
            await session.exec(
                select(__import__("sqlalchemy", fromlist=["func"]).func.count())
                .select_from(Message)
                .where(
                    Message.conversation_id == conversation.id,
                    Message.message_type.in_(  # type: ignore[attr-defined]
                        [MESSAGE_TYPE_INCOMING, MESSAGE_TYPE_OUTGOING]
                    ),
                )
            )
        ).one()
        or 0
    )

    msg_id_header = build_message_id(
        conversation=conversation, message=message, channel=channel
    )
    in_reply_to = build_in_reply_to(
        conversation=conversation,
        channel=channel,
        last_incoming=last_incoming,
    )
    references = build_references(
        conversation=conversation,
        channel=channel,
        last_incoming=last_incoming,
        in_reply_to=in_reply_to,
    )
    subject = build_subject(
        conversation=conversation, chat_message_count=chat_message_count
    )

    mail = EmailMessage()
    mail["From"] = _from_address(channel, sender_name=sender_name)
    mail["To"] = formataddr((contact.name or "", contact.email or ""))
    mail["Subject"] = subject
    mail["Date"] = format_datetime(datetime.now(UTC))
    mail["Message-ID"] = msg_id_header
    mail["In-Reply-To"] = in_reply_to
    mail["References"] = references
    mail.set_content(message.content or "")

    try:
        await aiosmtplib.send(
            mail,
            hostname=channel.smtp_address,
            port=channel.smtp_port,
            username=channel.smtp_login or None,
            password=channel.smtp_password or None,
            use_tls=channel.smtp_enable_ssl_tls,
            start_tls=channel.smtp_enable_starttls_auto
            and not channel.smtp_enable_ssl_tls,
            timeout=20.0,
        )
    except (aiosmtplib.SMTPException, OSError, TimeoutError) as exc:
        log.warning(
            "email.reply.send_failed channel_id=%s message_id=%s error=%s",
            channel.id,
            message.id,
            exc,
        )
        return False

    # Stamp the Message-ID (without the angle brackets — the ingest
    # parser strips them too) so the reply threads under the same
    # conversation when it bounces back via IMAP.
    bare_mid = msg_id_header.strip("<>")
    message.source_id = bare_mid
    session.add(message)
    await session.flush()
    log.info(
        "email.reply.sent channel_id=%s conversation_id=%s message_id=%s",
        channel.id,
        conversation.id,
        message.id,
    )
    return True


def fresh_message_id_token() -> str:
    """A short random token suitable for the local-part of a synthetic
    Message-ID. Used by tests that need a stable Message-ID without
    actually persisting a Message row."""
    return secrets.token_hex(8)


__all__ = [
    "build_in_reply_to",
    "build_message_id",
    "build_references",
    "build_subject",
    "fresh_message_id_token",
    "send_email_reply",
]
