"""Conversation event dispatcher.

Port of ``Rails.configuration.dispatcher.dispatch(event_name,
Time.zone.now, **payload)``. Phase 4a shipped a no-op stub that only
logged; Phase 4b.1 wires **real Redis pub/sub fan-out** via
:class:`~app.domains.conversations.listeners.ActionCableListener`.

Rails fans the event to many listeners (ActionCable, Notifications,
Webhooks, Reporting, AgentBot, AutomationRule, Campaign, CsatSurvey).
We port them phase-by-phase — 4b.1 ships only the ActionCable branch.
The remaining listeners' event_name ↔ handler_method names all stay
identical to Chatwoot's constants so each future listener plugs into
the same dispatch path.

Signature change from the 4a stub:

  4a:  ``dispatcher.dispatch(event_name, **payload)`` — synchronous, no-op.
  4b:  ``await dispatcher.dispatch(session, event_name, **payload)`` —
       async, requires the request's :class:`AsyncSession` because the
       listener issues read queries (inbox members, administrators,
       contact_inbox tokens) on that connection. Mirrors Rails' pattern
       of running SyncDispatcher listeners on the request's AR connection.

Event-name constants stay verbatim from ``lib/events/types.rb``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from sqlmodel.ext.asyncio.session import AsyncSession

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event name constants (verbatim from Chatwoot ``lib/events/types.rb``)
# ---------------------------------------------------------------------------
CONVERSATION_CREATED = "conversation.created"
CONVERSATION_UPDATED = "conversation.updated"
CONVERSATION_OPENED = "conversation.opened"
CONVERSATION_RESOLVED = "conversation.resolved"
CONVERSATION_STATUS_CHANGED = "conversation.status_changed"
CONVERSATION_READ = "conversation.read"
CONVERSATION_CONTACT_CHANGED = "conversation.contact_changed"
CONVERSATION_BOT_HANDOFF = "conversation.bot_handoff"
ASSIGNEE_CHANGED = "assignee.changed"
TEAM_CHANGED = "team.changed"
CONVERSATION_MENTIONED = "conversation.mentioned"
CONVERSATION_TYPING_ON = "conversation.typing_on"
CONVERSATION_TYPING_OFF = "conversation.typing_off"

MESSAGE_CREATED = "message.created"
MESSAGE_UPDATED = "message.updated"
FIRST_REPLY_CREATED = "first.reply.created"
REPLY_CREATED = "reply.created"


@dataclass
class Event:
    """Unified dispatcher payload.

    Mirrors the Rails calling convention:
        ``dispatcher.dispatch(event_name, Time.zone.now, payload_kwargs)``

    We carry ``timestamp`` for parity — listeners that care about the
    event wall-clock (Reporting, AutomationRule) will use it in later
    phases. ``payload`` holds model references + ``changed_attributes``
    / ``previous_changes`` when the event has them.
    """

    name: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    payload: dict[str, Any] = field(default_factory=dict)


class EventDispatcher:
    """4b dispatcher — fans out to the :class:`ActionCableListener`.

    We keep the class so later phases can register additional listeners
    on the same object (NotificationListener, WebhookListener, ...). The
    current implementation simply forwards to
    :func:`~app.domains.conversations.listeners.broadcast_event`.

    Failure isolation: the listener wraps its work in a try/except so a
    Redis outage or schema drift cannot break the request. The dispatch
    method itself stays simple; the listener is responsible for keeping
    the request cycle alive.
    """

    async def dispatch(
        self, session: AsyncSession, name: str, **payload: Any
    ) -> None:
        log.debug(
            "dispatcher.dispatch name=%s payload_keys=%s",
            name,
            list(payload.keys()),
        )
        # Late import keeps this module import-safe for tooling that
        # loads ``events.py`` (for the name constants) before the full
        # app is wired. Also sidesteps a cycle:
        # listeners.py imports the constants from this module.
        from app.domains.conversations.listeners import broadcast_event

        await broadcast_event(session, name, **payload)


# Singleton — matches ``Rails.configuration.dispatcher``. Tests that
# want to capture events instead of fanning them out can monkeypatch
# ``dispatcher.dispatch`` directly.
dispatcher = EventDispatcher()


__all__ = [
    "ASSIGNEE_CHANGED",
    "CONVERSATION_BOT_HANDOFF",
    "CONVERSATION_CONTACT_CHANGED",
    "CONVERSATION_CREATED",
    "CONVERSATION_MENTIONED",
    "CONVERSATION_OPENED",
    "CONVERSATION_READ",
    "CONVERSATION_RESOLVED",
    "CONVERSATION_STATUS_CHANGED",
    "CONVERSATION_TYPING_OFF",
    "CONVERSATION_TYPING_ON",
    "CONVERSATION_UPDATED",
    "FIRST_REPLY_CREATED",
    "MESSAGE_CREATED",
    "MESSAGE_UPDATED",
    "REPLY_CREATED",
    "TEAM_CHANGED",
    "Event",
    "EventDispatcher",
    "dispatcher",
]
