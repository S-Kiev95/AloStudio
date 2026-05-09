"""Shared action executor — used by Macros (6.2) AND AutomationRule (6.3).

Ported from:
  reference/chatwoot/app/services/action_service.rb        (base actions)
  reference/chatwoot/app/services/macros/execution_service.rb (overrides)
  reference/chatwoot/app/services/automation_rules/action_service.rb

Both Macro and AutomationRule walk an array of
``{"action_name": <str>, "action_params": [...]}`` dicts and dispatch
each entry to a method here. The macro-vs-automation differences live
in two thin overrides (e.g. macros resolve the ``"self"`` agent_id
sentinel to the executing user's id, automations don't); we expose
:class:`ActionExecutor` with hooks rather than duplicating the entire
dispatch table.

Scope for 6.2:
  * change_status / change_priority
  * resolve_conversation / snooze_conversation / mute_conversation
  * add_label / remove_label
  * assign_agent / remove_assigned_agent
  * assign_team / remove_assigned_team
  * send_message / add_private_note      (via MessageBuilder)

Deferred (logged, NOT a runtime error — Chatwoot stores the action and
silently skips on execute when the worker isn't wired):
  * send_email_transcript                 (5b's reply_mailer is wired
    but the transcript template hasn't been ported; lands with 6.6)
  * send_attachment                       (Phase 10 — ActiveStorage)
  * send_webhook_event                    (Phase 8 — Integrations)
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.current import current_user_ctx
from app.domains.contacts.models import Contact  # noqa: F401  (mapper)
from app.domains.conversations.models import (
    CONVERSATION_STATUS_OPEN,
    CONVERSATION_STATUS_PENDING,
    CONVERSATION_STATUS_RESOLVED,
    CONVERSATION_STATUS_SNOOZED,
    Conversation,
    conversation_priority_from_str,
)
from app.domains.conversations.service import (
    MessageBuilderParams,
    create_message,
    mute_conversation_with_activity,
    toggle_status,
    update_assignee,
    update_labels,
    update_team,
)
from app.domains.inboxes.models import Inbox, InboxMember
from app.domains.users.models import AccountUser, User

log = logging.getLogger(__name__)

# Status strings the Rails ``change_status`` action accepts —
# Chatwoot stores them as strings in the JSON action_params.
_STATUS_LITERALS = {
    "open": CONVERSATION_STATUS_OPEN,
    "resolved": CONVERSATION_STATUS_RESOLVED,
    "pending": CONVERSATION_STATUS_PENDING,
    "snoozed": CONVERSATION_STATUS_SNOOZED,
}


class ActionExecutor:
    """Runs an action plan against a Conversation.

    Subclass to override per-context behaviours (e.g. Macro resolving
    the ``"self"`` agent sentinel to the executing user)."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        conversation: Conversation,
        executing_user_id: int | None = None,
    ) -> None:
        self.session = session
        self.conversation = conversation
        self.executing_user_id = executing_user_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def execute(self, actions: list[dict[str, Any]]) -> None:
        """Walk every action, swallow per-action errors.

        Mirrors Rails' ``rescue StandardError => e`` per action so a
        single bad action doesn't abort the rest. We log instead of
        forwarding to Sentry — the parity is "no exception escapes",
        not "every error reports identically".
        """
        for raw in actions or []:
            if not isinstance(raw, dict):
                continue
            name = raw.get("action_name")
            params = raw.get("action_params") or []
            if not isinstance(name, str):
                continue
            handler = getattr(self, f"_action_{name}", None)
            if handler is None:
                log.warning(
                    "automation.action.unknown name=%s conversation_id=%s",
                    name,
                    self.conversation.id,
                )
                continue
            try:
                await handler(params)
            except Exception:  # noqa: BLE001
                log.exception(
                    "automation.action.error name=%s conversation_id=%s",
                    name,
                    self.conversation.id,
                )

    # ------------------------------------------------------------------
    # Hooks — overridden by Macro executor for the "self" sentinel.
    # ------------------------------------------------------------------
    def _resolve_agent_id(self, raw: Any) -> int | None:
        """Coerce one entry from the ``assign_agent`` params array.

        Macro's executor overrides this to map the ``"self"`` sentinel
        onto the executing user. AutomationRule keeps the raw int."""
        if isinstance(raw, str) and raw == "nil":
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # State mutations
    # ------------------------------------------------------------------
    async def _action_change_status(self, params: list[Any]) -> None:
        if not params:
            return
        status_raw = params[0]
        if status_raw not in _STATUS_LITERALS:
            return
        await toggle_status(
            self.session, conversation=self.conversation, status=status_raw
        )

    async def _action_resolve_conversation(self, _params: list[Any]) -> None:
        await toggle_status(
            self.session, conversation=self.conversation, status="resolved"
        )

    async def _action_snooze_conversation(self, _params: list[Any]) -> None:
        # Rails ``snoozed!`` flips the status without setting a
        # ``snoozed_until`` — same here.
        await toggle_status(
            self.session, conversation=self.conversation, status="snoozed"
        )

    async def _action_mute_conversation(self, _params: list[Any]) -> None:
        await mute_conversation_with_activity(
            self.session, conversation=self.conversation
        )

    async def _action_change_priority(self, params: list[Any]) -> None:
        from app.domains.conversations.service import toggle_priority

        if not params:
            return
        raw = params[0]
        # Rails: ``priority[0] == 'nil'`` clears the priority.
        priority = None if raw == "nil" else raw
        if priority is not None and not isinstance(priority, str):
            return
        # Validate against the enum; conversion raises ValueError on bad input.
        try:
            conversation_priority_from_str(priority)
        except ValueError:
            return
        await toggle_priority(
            self.session, conversation=self.conversation, priority=priority
        )

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------
    async def _action_assign_agent(self, params: list[Any]) -> None:
        if not params:
            return
        first = params[0]
        if first == "nil":
            await update_assignee(
                self.session,
                conversation=self.conversation,
                assignee_id=None,
            )
            return
        agent_id = self._resolve_agent_id(first)
        if agent_id is None:
            return
        # Mirror ``agent_belongs_to_inbox?`` — agent must be either an
        # inbox member or an administrator on the account.
        if not await self._agent_is_assignable(agent_id):
            return
        await update_assignee(
            self.session,
            conversation=self.conversation,
            assignee_id=agent_id,
        )

    async def _action_remove_assigned_agent(self, _params: list[Any]) -> None:
        await update_assignee(
            self.session,
            conversation=self.conversation,
            assignee_id=None,
        )

    async def _action_assign_team(self, params: list[Any]) -> None:
        # Rails: blank or "nil"/"0" → clear the team.
        if not params:
            await update_team(
                self.session, conversation=self.conversation, team_id=None
            )
            return
        first = params[0]
        if str(first) in {"nil", "0", ""}:
            await update_team(
                self.session, conversation=self.conversation, team_id=None
            )
            return
        try:
            team_id = int(first)
        except (TypeError, ValueError):
            return
        await update_team(
            self.session, conversation=self.conversation, team_id=team_id
        )

    async def _action_remove_assigned_team(self, _params: list[Any]) -> None:
        await update_team(
            self.session, conversation=self.conversation, team_id=None
        )

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------
    async def _action_add_label(self, params: list[Any]) -> None:
        # ``add_label`` adds without clobbering existing labels.
        if not params:
            return
        new_titles = [t for t in params if isinstance(t, str)]
        if not new_titles:
            return
        existing = []
        if self.conversation.cached_label_list:
            existing = [
                t.strip()
                for t in self.conversation.cached_label_list.split(",")
                if t.strip()
            ]
        merged = existing + [t for t in new_titles if t not in existing]
        await update_labels(
            self.session, conversation=self.conversation, titles=merged
        )

    async def _action_remove_label(self, params: list[Any]) -> None:
        if not params or not self.conversation.cached_label_list:
            return
        to_remove = {t for t in params if isinstance(t, str)}
        existing = [
            t.strip()
            for t in self.conversation.cached_label_list.split(",")
            if t.strip()
        ]
        kept = [t for t in existing if t not in to_remove]
        if kept == existing:
            return
        await update_labels(
            self.session, conversation=self.conversation, titles=kept
        )

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------
    async def _action_send_message(self, params: list[Any]) -> None:
        if not params or not isinstance(params[0], str):
            return
        await create_message(
            self.session,
            conversation=self.conversation,
            params=MessageBuilderParams(
                content=params[0],
                message_type="outgoing",
                private=False,
            ),
            user_id=self.executing_user_id,
        )

    async def _action_add_private_note(self, params: list[Any]) -> None:
        if not params or not isinstance(params[0], str):
            return
        await create_message(
            self.session,
            conversation=self.conversation,
            params=MessageBuilderParams(
                content=params[0],
                message_type="outgoing",
                private=True,
            ),
            user_id=self.executing_user_id,
        )

    # ------------------------------------------------------------------
    # Deferred (logged, no-op)
    # ------------------------------------------------------------------
    async def _action_send_email_transcript(self, _params: list[Any]) -> None:
        log.info(
            "automation.action.deferred name=send_email_transcript conversation_id=%s",
            self.conversation.id,
        )

    async def _action_send_attachment(self, _params: list[Any]) -> None:
        log.info(
            "automation.action.deferred name=send_attachment conversation_id=%s",
            self.conversation.id,
        )

    async def _action_send_webhook_event(self, _params: list[Any]) -> None:
        log.info(
            "automation.action.deferred name=send_webhook_event conversation_id=%s",
            self.conversation.id,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _agent_is_assignable(self, agent_id: int) -> bool:
        """Mirror ``agent_belongs_to_inbox?`` + ``account.administrators``.

        An agent_id is assignable when the user is either:
          * a member of the conversation's inbox, OR
          * an administrator of the conversation's account.
        """
        # Inbox membership check.
        inbox = self.conversation.inbox
        if inbox is None:
            inbox = await self.session.get(Inbox, self.conversation.inbox_id)
        if inbox is None:
            return False
        member = (
            await self.session.exec(
                select(InboxMember).where(
                    InboxMember.inbox_id == inbox.id,
                    InboxMember.user_id == agent_id,
                )
            )
        ).first()
        if member is not None:
            return True

        # Administrator fallback — matches ``@account.administrators.ids``.
        admin = (
            await self.session.exec(
                select(AccountUser).where(
                    AccountUser.account_id == self.conversation.account_id,
                    AccountUser.user_id == agent_id,
                    AccountUser.role == 1,  # administrator
                )
            )
        ).first()
        return admin is not None


class MacroExecutor(ActionExecutor):
    """Macro-side overrides on top of :class:`ActionExecutor`.

    Mirrors ``Macros::ExecutionService``:
      * The ``"self"`` sentinel in ``assign_agent`` resolves to the
        executing user (Rails ``Current.user``).
    """

    def _resolve_agent_id(self, raw: Any) -> int | None:
        if raw == "self":
            user = current_user_ctx.get()
            return user.id if user is not None else self.executing_user_id
        return super()._resolve_agent_id(raw)


# Ensure mapper-config picks up User even if this is the first reach-in.
_ = User

__all__ = ["ActionExecutor", "MacroExecutor"]
