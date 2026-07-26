"""Email threading — match an inbound mail to an existing conversation.

Ports the Chatwoot threading logic from ``Imap::ImapMailbox#find_conversation``
(roughly):

  * Look at the mail's ``In-Reply-To`` header.
  * Fall back to walking the ``References`` header (RFC-2822 list of
    Message-IDs in chronological order, oldest last).
  * Match any of those values against ``messages.source_id`` — that's
    where we stamp the Message-ID on outbound replies (5b.3) and on
    inbound mails (5b.4).

The matching is case-sensitive on the mid+domain part — Message-IDs
are technically case-sensitive per RFC-2822 §3.6.4, even though most
mail servers normalize. Following the spec keeps us safe against a
server that treats them strictly.

Pure parsing — no DB I/O at the helper layer; the ``find_conversation
_by_thread`` entry point takes a session and runs the lookup.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Conversation, Message

# RFC-2822 §3.6.4: msg-id = "<" id-left "@" id-right ">". We accept the
# bare-`@` form too (old servers ship them without brackets); production
# data has both.
_MID_RE = re.compile(r"<([^<>\s]+@[^<>\s]+)>|([^\s,;<>]+@[^\s,;<>]+)")


def extract_message_ids(header_value: str | None) -> list[str]:
    """Pull every Message-ID out of an ``In-Reply-To`` / ``References``
    header value.

    Returns an empty list for ``None`` or whitespace-only input. The
    return preserves source order — the head is the most recent
    reference, the tail the chain root, mirroring the order in
    which mail clients write the ``References`` header.

    Real-world mail headers can carry malformed garbage; we strip
    quoted-printable encoded-words but otherwise do a best-effort
    regex pass. Anything that doesn't look like an addr-spec is
    silently dropped.
    """
    if not header_value:
        return []
    out: list[str] = []
    for match in _MID_RE.finditer(header_value):
        mid = match.group(1) or match.group(2)
        if mid and mid not in out:
            out.append(mid)
    return out


@dataclass(slots=True)
class ThreadingHeaders:
    """Bundle of the headers the threading lookup cares about.

    Keep it dataclass-shaped so tests can construct one from a literal
    dict without needing a real ``email.message.EmailMessage``.
    """

    in_reply_to: str | None = None
    references: str | None = None
    message_id: str | None = None

    def candidate_ids(self) -> list[str]:
        """Ordered list of Message-IDs to try, dedupe-preserving order.

        Order matches Rails' lookup: ``In-Reply-To`` first (one parent),
        then everything in ``References`` (oldest last but we keep the
        textual order).
        """
        seen: set[str] = set()
        out: list[str] = []
        for value in (self.in_reply_to, self.references):
            for mid in extract_message_ids(value):
                if mid not in seen:
                    seen.add(mid)
                    out.append(mid)
        return out


async def find_conversation_by_thread(
    session: AsyncSession,
    *,
    account_id: int,
    headers: ThreadingHeaders,
) -> Conversation | None:
    """Look up the conversation a mail belongs to.

    Iterates every candidate Message-ID and returns the first match's
    Conversation. Scoped by ``account_id`` because Message-IDs are
    only unique within an inbox in theory, but in practice we want to
    avoid cross-account collisions on a shared mail server.

    Returns ``None`` when nothing matches — the caller treats that as
    "start a new conversation".
    """
    candidates = headers.candidate_ids()
    if not candidates:
        return None

    stmt = (
        select(Message)
        .where(
            Message.account_id == account_id,
            Message.source_id.in_(candidates),
        )
        .limit(1)
    )
    msg = (await session.exec(stmt)).first()
    if msg is None or msg.conversation_id is None:
        return None
    return await session.get(Conversation, msg.conversation_id)


__all__ = [
    "ThreadingHeaders",
    "extract_message_ids",
    "find_conversation_by_thread",
]
