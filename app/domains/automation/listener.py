"""AutomationRuleListener — dispatcher hook that fires rules on events.

Ported from:
  reference/chatwoot/app/listeners/automation_rule_listener.rb

Subscribes to five dispatcher events and maps each to the
AutomationRule.event_name string Chatwoot uses:

  * conversation.created    → ``conversation_created``
  * conversation.updated    → ``conversation_updated``
  * conversation.opened     → ``conversation_opened``
  * conversation.resolved   → ``conversation_resolved``
  * message.created         → ``message_created``

For each event, the listener:
  1. Skips events fired by an automation rule itself (loop prevention —
     mirrors Rails' ``performed_by_automation?`` guard via a ContextVar
     set during action execution).
  2. Skips ``message.created`` events where the message is an activity
     row or an auto-reply email (mirrors ``ignore_message_created_event?``).
  3. Loads every ``active`` ``AutomationRule`` for the account matching
     the event_name.
  4. Evaluates each rule's conditions and runs its actions on match,
     using the shared :class:`app.domains.automation.actions.ActionExecutor`
     from 6.2.

Failure isolation: per-rule errors are caught and logged so a broken
rule never breaks the request cycle (parity with Rails'
``SyncDispatcher`` rescue).
"""

from __future__ import annotations

import contextvars
import logging
from contextlib import contextmanager
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.automation.models import AutomationRule
from app.domains.automation.service import run_rule_on_conversation
from app.domains.conversations import events as ev
from app.domains.conversations.models import (
    MESSAGE_TYPE_ACTIVITY,
    Conversation,
    Message,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Loop-prevention marker (ContextVar)
# ---------------------------------------------------------------------------
# Set to the AutomationRule.id while actions are running so any events
# the actions dispatch (e.g. ``CONVERSATION_UPDATED`` from a
# ``change_priority`` action) can be skipped by the listener.
# Mirrors Rails' ``event.data[:performed_by].instance_of?(AutomationRule)``
# check — we use a ContextVar instead of a per-event payload key to
# avoid threading the marker through every dispatch site.
_current_automation_rule_id_ctx: contextvars.ContextVar[int | None] = (
    contextvars.ContextVar("current_automation_rule_id", default=None)
)


@contextmanager
def automation_rule_run_marker(rule_id: int):
    """Mark the running stack as "inside an automation rule's actions".

    The listener consults this marker to skip dispatcher events fired
    by the actions themselves, preventing infinite loops where a rule
    on ``conversation_updated`` changes priority and re-triggers
    itself. Mirrors Rails ``Current.executed_by = automation_rule``.
    """
    token = _current_automation_rule_id_ctx.set(rule_id)
    try:
        yield
    finally:
        _current_automation_rule_id_ctx.reset(token)


def _performed_by_automation() -> bool:
    return _current_automation_rule_id_ctx.get() is not None


# ---------------------------------------------------------------------------
# Dispatcher event name -> AutomationRule.event_name
# ---------------------------------------------------------------------------
_EVENT_NAME_MAP: dict[str, str] = {
    ev.CONVERSATION_CREATED: "conversation_created",
    ev.CONVERSATION_UPDATED: "conversation_updated",
    ev.CONVERSATION_OPENED: "conversation_opened",
    ev.CONVERSATION_RESOLVED: "conversation_resolved",
    ev.MESSAGE_CREATED: "message_created",
}


# ---------------------------------------------------------------------------
# Listener entry point
# ---------------------------------------------------------------------------
async def fan_out_to_automation(
    session: AsyncSession,
    event_name: str,
    **payload: Any,
) -> None:
    """Single entry point called from :func:`broadcast_event`.

    Returns silently for events the rule engine doesn't subscribe to,
    for self-triggered events, and for messages the engine ignores
    (activity / auto-reply email).
    """
    rule_event_name = _EVENT_NAME_MAP.get(event_name)
    if rule_event_name is None:
        return
    if _performed_by_automation():
        return

    conversation, message = _resolve_subject(rule_event_name, payload)
    if conversation is None:
        return
    if rule_event_name == "message_created" and _ignore_message(message):
        return
    # v2.8 suppression: an external AI agent has claimed this
    # conversation (via ``set_ai_mode(on=true)`` over MCP). Standing
    # down here matches the contract — automation rules and the AI
    # would otherwise fight over assignments, status flips, replies,
    # etc. Macros invoked MANUALLY by a human stay unaffected; only
    # rules chained automatically through this listener short-circuit.
    if bool(conversation.ai_mode):
        log.debug(
            "automation.listener.ai_mode_suppressed conversation_id=%s",
            conversation.id,
        )
        return

    rules = await _active_rules_for(
        session,
        account_id=conversation.account_id,
        event_name=rule_event_name,
    )
    if not rules:
        return

    for rule in rules:
        try:
            with automation_rule_run_marker(rule.id or 0):
                await run_rule_on_conversation(
                    session,
                    rule=rule,
                    conversation=conversation,
                    message=message,
                )
        except Exception:
            log.exception(
                "automation.listener.rule_error rule_id=%s conversation_id=%s",
                rule.id,
                conversation.id,
            )


def _resolve_subject(
    rule_event_name: str, payload: dict[str, Any]
) -> tuple[Conversation | None, Message | None]:
    """Extract Conversation (+ optionally Message) from the dispatch
    payload for the rule engine's event family.

    ``conversation_*`` events carry ``conversation=`` directly.
    ``message_created`` carries ``message=`` and we follow
    ``message.conversation``.
    """
    if rule_event_name == "message_created":
        message = payload.get("message")
        if not isinstance(message, Message):
            return None, None
        conversation = message.conversation
        return (conversation if isinstance(conversation, Conversation) else None), message
    conversation = payload.get("conversation")
    if not isinstance(conversation, Conversation):
        return None, None
    return conversation, None


def _ignore_message(message: Message | None) -> bool:
    """Mirror ``ignore_message_created_event?`` (minus the
    ``performed_by_automation`` check — that's covered globally above).

    Skips activity messages and auto-reply email messages."""
    if message is None:
        return True
    if message.message_type == MESSAGE_TYPE_ACTIVITY:
        return True
    ca = message.content_attributes or {}
    # Email auto-reply: Chatwoot stamps ``is_auto_reply`` in
    # ``content_attributes['email']`` when the IMAP fetcher detects an
    # ``Auto-Submitted`` header. Mirror that gate.
    email_meta = ca.get("email")
    if isinstance(email_meta, dict) and email_meta.get("is_auto_reply"):
        return True
    return False


async def _active_rules_for(
    session: AsyncSession,
    *,
    account_id: int,
    event_name: str,
) -> list[AutomationRule]:
    stmt = (
        select(AutomationRule)
        .where(
            AutomationRule.account_id == account_id,
            AutomationRule.event_name == event_name,
            AutomationRule.active.is_(True),
        )
        .order_by(AutomationRule.id.asc())
    )
    return list((await session.exec(stmt)).all())


__all__ = [
    "automation_rule_run_marker",
    "fan_out_to_automation",
]
