"""ActionCableListener — Chatwoot's event -> Redis pub/sub bridge.

Port of ``reference/chatwoot/app/listeners/action_cable_listener.rb``.

Rails registers this listener on the ``SyncDispatcher``: when the
``EventDispatcher`` fires, the method runs inline in the request cycle,
uses the request's ActiveRecord connection to resolve tokens, then
enqueues ``ActionCableBroadcastJob.perform_later(tokens, event, data)``
which later publishes to Redis pub/sub.

We collapse the job-queue hop: this listener resolves tokens AND
publishes directly to Redis. The wire shape on the Redis channel stays
identical to Chatwoot's — ``{event, data}`` with the standard
``account_id`` + ``performer`` merge — so a subscriber sees the same
frames whether the listener ran inline or queued. Re-introducing arq
for the broadcast step is a drop-in optimization we can take later if
broadcast volume ever justifies it.

Channel naming (matches RoomChannel subscribe params):

  * ``<pubsub_token>`` — per-user channel for agents/admins.
  * ``<pubsub_token>`` — per-contact-inbox channel for widget visitors.
  * ``account_<id>``   — broadcast channel; used for ``CONTACT_*``
    events in Chatwoot (Phase 4b.1 doesn't ship those handlers yet —
    Contacts live in Phase 3 scope without realtime fan-out).

Covered events in 4b.1 (subset of Ruby listener's 18):

  * ``CONVERSATION_CREATED``
  * ``CONVERSATION_UPDATED``
  * ``CONVERSATION_STATUS_CHANGED``
  * ``MESSAGE_CREATED``
  * ``FIRST_REPLY_CREATED``

The other events (assignee_changed/team_changed/typing/read/mentioned/
notification_*) land when their source-side callers are ported in
4b.3/4b.4/9/etc. Unknown events are a no-op — matches Rails'
``ActionCableListener`` silently ignoring events it has no method for.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.current import current_user_ctx
from app.core.realtime import RealtimeBroadcaster, get_broadcaster
from app.domains.conversations import events as ev
from app.domains.conversations.models import (
    MESSAGE_TYPE_ACTIVITY,
    Conversation,
    Message,
)
from app.domains.conversations.presenters import (
    _user_push_event_data,
    present_conversation,
    present_message_push_event,
)
from app.domains.contacts.models import ContactInbox
from app.domains.inboxes.models import InboxMember
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_ADMINISTRATOR,
    AccountUser,
    User,
)

log = logging.getLogger(__name__)


class ActionCableListener:
    """One-shot listener bound to a single dispatch.

    Instantiated per-event by :func:`broadcast_event` rather than kept
    as a singleton because each dispatch carries its own session +
    performer context.
    """

    def __init__(
        self,
        session: AsyncSession,
        broadcaster: RealtimeBroadcaster,
        performer: User | None = None,
    ) -> None:
        self._session = session
        self._broadcaster = broadcaster
        self._performer = performer

    # ---------------------------------------------------------------- entry
    async def dispatch(self, event_name: str, **data: Any) -> None:
        """Route ``event_name`` to its handler. Unknown names are a
        no-op, like Rails ``ActionCableListener`` silently ignoring
        methods it doesn't declare.

        Listener errors must NEVER break the request — mirrors Rails'
        ``SyncDispatcher#rescue_from_any_error``. Broken pub/sub should
        log loud and let the HTTP response succeed.
        """
        handler = _HANDLERS.get(event_name)
        if handler is None:
            return
        try:
            await handler(self, **data)
        except Exception:
            log.exception("action_cable_listener.error event=%s", event_name)

    # ---------------------------------------------------------- event impls
    async def _conversation_created(self, *, conversation: Conversation) -> None:
        tokens = await self._conversation_tokens(conversation, include_contact=True)
        await self._broadcast(
            conversation.account_id,
            tokens,
            ev.CONVERSATION_CREATED,
            present_conversation(conversation),
        )

    async def _conversation_updated(
        self,
        *,
        conversation: Conversation,
        changed_attributes: dict[str, Any] | None = None,
    ) -> None:
        tokens = await self._conversation_tokens(conversation, include_contact=True)
        data = present_conversation(conversation)
        if changed_attributes is not None:
            # Mirror Rails' ``conversation.push_event_data.merge(
            #   changed_attributes: event.data[:changed_attributes])``
            # in ``conversation_updated``.
            data = {**data, "changed_attributes": changed_attributes}
        await self._broadcast(
            conversation.account_id,
            tokens,
            ev.CONVERSATION_UPDATED,
            data,
        )

    async def _conversation_status_changed(self, *, conversation: Conversation) -> None:
        tokens = await self._conversation_tokens(conversation, include_contact=True)
        await self._broadcast(
            conversation.account_id,
            tokens,
            ev.CONVERSATION_STATUS_CHANGED,
            present_conversation(conversation),
        )

    async def _message_created(self, *, message: Message) -> None:
        conversation = message.conversation
        if conversation is None:
            return
        # ``present_message_push_event`` reads ``message.attachments``. On an
        # AsyncSession a lazy-load raises MissingGreenlet, and inbound paths
        # (e.g. the WhatsApp webhook) don't preload it the way create_message
        # does — so load it here before the sync presenter touches it.
        await self._session.refresh(message, ["attachments"])
        user_tokens = await self._user_tokens(conversation)
        # ``contact_tokens`` guards private + activity messages.
        contact_tokens = await self._contact_tokens(conversation, message)
        tokens = list({*user_tokens, *contact_tokens})
        await self._broadcast(
            message.account_id,
            tokens,
            ev.MESSAGE_CREATED,
            present_message_push_event(message),
        )

    async def _conversation_typing_on(
        self,
        *,
        conversation: Conversation,
        user: Any,
        is_private: bool = False,
    ) -> None:
        await self._broadcast_typing(
            conversation=conversation,
            user=user,
            is_private=is_private,
            event_name=ev.CONVERSATION_TYPING_ON,
        )

    async def _conversation_typing_off(
        self,
        *,
        conversation: Conversation,
        user: Any,
        is_private: bool = False,
    ) -> None:
        await self._broadcast_typing(
            conversation=conversation,
            user=user,
            is_private=is_private,
            event_name=ev.CONVERSATION_TYPING_OFF,
        )

    async def _broadcast_typing(
        self,
        *,
        conversation: Conversation,
        user: Any,
        is_private: bool,
        event_name: str,
    ) -> None:
        """Mirror ``ActionCableListener#typing_event_listener_tokens``.

        Tokens = inbox-member user tokens + the contact_inbox token,
        MINUS the actor's own token (so the typer doesn't see their
        own bubble). The payload is the conversation push-event +
        the typer's push-event + ``is_private``.
        """
        from app.domains.users.models import User as _User

        user_tokens = await self._user_tokens(conversation)
        contact_tokens: list[str] = []
        if conversation.contact_inbox is not None:
            contact_tokens = await self._contact_inbox_tokens(
                conversation.contact_inbox
            )
        all_tokens = list({*user_tokens, *contact_tokens})

        # Determine the actor's token (User -> pubsub_token; Contact ->
        # the contact_inbox pubsub_token). Contacts never trigger typing
        # in 4b but Rails accepts it, so we mirror.
        actor_token: str | None = None
        if isinstance(user, _User):
            actor_token = user.pubsub_token
        elif conversation.contact_inbox is not None:
            actor_token = conversation.contact_inbox.pubsub_token

        if actor_token in all_tokens:
            all_tokens = [t for t in all_tokens if t != actor_token]

        payload = {
            "conversation": present_conversation(conversation),
            "user": _user_push_event_data(user) if user is not None else None,
            "is_private": bool(is_private),
        }
        await self._broadcast(
            conversation.account_id, all_tokens, event_name, payload
        )

    async def _first_reply_created(self, *, message: Message) -> None:
        conversation = message.conversation
        if conversation is None:
            return
        tokens = await self._user_tokens(conversation)
        await self._broadcast(
            message.account_id,
            tokens,
            ev.FIRST_REPLY_CREATED,
            present_message_push_event(message),
        )

    # --------------------------------------------------------- token helpers
    async def _conversation_tokens(
        self, conversation: Conversation, *, include_contact: bool
    ) -> list[str]:
        """Mirror of ``user_tokens + contact_inbox_tokens`` merge used
        for conversation_* + message_* broadcasts.
        """
        user_tokens = await self._user_tokens(conversation)
        if not include_contact or conversation.contact_inbox is None:
            return user_tokens
        contact_tokens = await self._contact_inbox_tokens(conversation.contact_inbox)
        return list({*user_tokens, *contact_tokens})

    async def _user_tokens(self, conversation: Conversation) -> list[str]:
        """Tokens for inbox members + account administrators.

        Rails path:
          ``(inbox.members.pluck(:pubsub_token) +
             account.administrators.pluck(:pubsub_token)).uniq``
        """
        member_tokens = await self._inbox_member_tokens(conversation.inbox_id)
        admin_tokens = await self._administrator_tokens(conversation.account_id)
        return list({*member_tokens, *admin_tokens})

    async def _inbox_member_tokens(self, inbox_id: int | None) -> list[str]:
        if inbox_id is None:
            return []
        stmt = (
            select(User.pubsub_token)
            .join(InboxMember, InboxMember.user_id == User.id)  # type: ignore[arg-type]
            .where(InboxMember.inbox_id == inbox_id)
        )
        rows = (await self._session.exec(stmt)).all()
        return [t for t in rows if t]

    async def _administrator_tokens(self, account_id: int | None) -> list[str]:
        if account_id is None:
            return []
        stmt = (
            select(User.pubsub_token)
            .join(AccountUser, AccountUser.user_id == User.id)  # type: ignore[arg-type]
            .where(
                AccountUser.account_id == account_id,
                AccountUser.role == ACCOUNT_USER_ROLE_ADMINISTRATOR,
            )
        )
        rows = (await self._session.exec(stmt)).all()
        return [t for t in rows if t]

    async def _contact_inbox_tokens(self, contact_inbox: ContactInbox) -> list[str]:
        """Mirror of ``contact_inbox_tokens(contact_inbox)``.

        Rails ternary:
          ``contact_inbox.hmac_verified? ?
             contact.contact_inboxes.where(hmac_verified: true)
                 .filter_map(&:pubsub_token) :
             [contact_inbox.pubsub_token]``
        """
        if not contact_inbox.hmac_verified:
            return [contact_inbox.pubsub_token] if contact_inbox.pubsub_token else []
        stmt = select(ContactInbox.pubsub_token).where(
            ContactInbox.contact_id == contact_inbox.contact_id,
            ContactInbox.hmac_verified.is_(True),  # type: ignore[union-attr]
        )
        rows = (await self._session.exec(stmt)).all()
        return [t for t in rows if t]

    async def _contact_tokens(
        self, conversation: Conversation, message: Message
    ) -> list[str]:
        """Mirror of ``contact_tokens(contact_inbox, message)`` — the
        guard for MESSAGE_CREATED that drops contact delivery for
        private + activity messages.
        """
        if message.private:
            return []
        if message.message_type == MESSAGE_TYPE_ACTIVITY:
            return []
        if conversation.contact_inbox is None:
            return []
        return await self._contact_inbox_tokens(conversation.contact_inbox)

    # --------------------------------------------------------------- broadcast
    async def _broadcast(
        self,
        account_id: int | None,
        tokens: list[str],
        event_name: str,
        data: dict[str, Any],
    ) -> None:
        """Mirror of ``broadcast(account, tokens, event_name, data)`` in
        the Ruby listener.

        Merges ``account_id`` + optional ``performer`` onto the payload,
        then publishes once per token.
        """
        if not tokens:
            return
        payload: dict[str, Any] = {**data, "account_id": account_id}
        if self._performer is not None:
            payload["performer"] = _user_push_event_data(self._performer)
        await self._broadcaster.publish(tokens, event_name, payload)


# Populated below the class so each handler is visible as a function.
# Signature: ``async def(listener, **event_payload) -> None``.
_HANDLERS: dict[str, Callable[..., Awaitable[None]]] = {
    ev.CONVERSATION_CREATED: ActionCableListener._conversation_created,
    ev.CONVERSATION_UPDATED: ActionCableListener._conversation_updated,
    ev.CONVERSATION_STATUS_CHANGED: ActionCableListener._conversation_status_changed,
    ev.CONVERSATION_TYPING_ON: ActionCableListener._conversation_typing_on,
    ev.CONVERSATION_TYPING_OFF: ActionCableListener._conversation_typing_off,
    ev.MESSAGE_CREATED: ActionCableListener._message_created,
    ev.FIRST_REPLY_CREATED: ActionCableListener._first_reply_created,
}


async def broadcast_event(
    session: AsyncSession,
    name: str,
    **payload: Any,
) -> None:
    """Entry point called from :class:`EventDispatcher.dispatch`.

    Fans out to every registered listener — currently:

      * :class:`ActionCableListener` — the realtime broadcast layer.
      * :func:`app.domains.automation.listener.fan_out_to_automation`
        — runs matching AutomationRules (Phase 6.4).

    Each listener wraps its own work in a try/except so a failure on
    one side never blocks the other.
    """
    broadcaster = await get_broadcaster()
    performer = current_user_ctx.get()
    listener = ActionCableListener(session, broadcaster, performer)
    await listener.dispatch(name, **payload)
    # Automation rules subscribe to the same events. Late-import so the
    # `conversations` package stays import-clean when automation isn't
    # used (and avoids any circular reference from automation_listener
    # touching ``app.domains.conversations`` indirectly).
    from app.domains.automation.listener import fan_out_to_automation

    try:
        await fan_out_to_automation(session, name, **payload)
    except Exception:  # noqa: BLE001
        log.exception("automation_listener.error event=%s", name)
    # CSAT survey emitter (Phase 6.5) — runs on ``CONVERSATION_RESOLVED``
    # only. Same failure-isolation contract as the automation listener.
    from app.domains.csat.listener import fan_out_to_csat

    try:
        await fan_out_to_csat(session, name, **payload)
    except Exception:  # noqa: BLE001
        log.exception("csat_listener.error event=%s", name)
    # Reporting event emitter (Phase 7.1) — writes a ReportingEvent row
    # on resolve / first reply / reply / open. Source for dashboards.
    from app.domains.reporting.listener import fan_out_to_reporting

    try:
        await fan_out_to_reporting(session, name, **payload)
    except Exception:  # noqa: BLE001
        log.exception("reporting_listener.error event=%s", name)
    # AgentBot relay (Phase 8.2) — POSTs the standard webhook envelope
    # to each bot attached to the inbox / assigned to the conversation.
    from app.domains.agent_bots.listener import fan_out_to_agent_bots

    try:
        await fan_out_to_agent_bots(session, name, **payload)
    except Exception:  # noqa: BLE001
        log.exception("agent_bot_listener.error event=%s", name)
    # In-app notifications inbox (v2.5) — inserts a Notification row
    # per recipient (inbox members on create, assignee on assign /
    # new incoming message) and broadcasts ``notification.created``
    # to the recipient's cable channel so the bell badge updates live.
    from app.domains.notifications.listener import fan_out_to_notifications

    try:
        await fan_out_to_notifications(session, name, **payload)
    except Exception:  # noqa: BLE001
        log.exception("notifications_listener.error event=%s", name)
    # Webhook delivery (Phase 8.3) — POSTs to every account-configured
    # Webhook subscribed to the event.
    from app.domains.webhooks.listener import fan_out_to_webhooks

    try:
        await fan_out_to_webhooks(session, name, **payload)
    except Exception:  # noqa: BLE001
        log.exception("webhook_listener.error event=%s", name)


__all__ = ["ActionCableListener", "broadcast_event"]
