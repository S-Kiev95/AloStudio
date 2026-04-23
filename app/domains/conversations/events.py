"""Event dispatcher stub for Phase 4a.

Rails routes every state change through
``Rails.configuration.dispatcher.dispatch(event_name, Time.zone.now,
**payload)``. The dispatcher then fans out to listeners:

  * ``ActionCableListener``   — WebSocket broadcasts (Phase 4b)
  * ``NotificationListener``  — in-app + email notifications (Phase 4b)
  * ``WebhookListener``       — outbound webhooks
  * ``ReportingEventListener``— analytics (Phase 7)
  * ``AgentBotListener``      — bot invocations (Phase 8)
  * ``AutomationRuleListener``— rule engine (Phase 6)
  * ``CampaignListener``      — campaign tracking (Phase 6)
  * ``CsatSurveyListener``    — CSAT (Phase 5)

Phase 4a ships a **no-op dispatcher** that only logs. Each later phase
registers a real listener by importing the module. The callsites in
services use the same event name + payload shape as Chatwoot, so when a
real backend arrives we only swap the ``dispatch`` implementation.

Event names match Chatwoot's constants exactly (uppercase snake_case):
``reference/chatwoot/lib/events/types.rb`` is the canonical list.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

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
    ``payload`` carries model references + ``changed_attributes`` /
    ``previous_changes`` when the event has them.
    """

    name: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    payload: dict[str, Any] = field(default_factory=dict)


class EventDispatcher:
    """No-op dispatcher for Phase 4a.

    Phase 4b swaps the implementation for one that publishes to Redis
    pub/sub and a WebSocket broadcast layer. Phase 4a logs at DEBUG so
    the call-graph is visible without cluttering test output.
    """

    def dispatch(self, name: str, **payload: Any) -> None:
        event = Event(name=name, payload=payload)
        log.debug("dispatcher.dispatch name=%s payload_keys=%s", event.name, list(payload.keys()))


# Singleton — matches ``Rails.configuration.dispatcher``. Tests can
# monkeypatch ``dispatcher.dispatch`` to capture events.
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
    "Event",
    "EventDispatcher",
    "FIRST_REPLY_CREATED",
    "MESSAGE_CREATED",
    "MESSAGE_UPDATED",
    "REPLY_CREATED",
    "TEAM_CHANGED",
    "dispatcher",
]
