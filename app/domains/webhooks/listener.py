"""WebhookListener — delivers dispatcher events to account-configured
HTTP receivers.

Ported from:
  reference/chatwoot/app/listeners/webhook_listener.rb
  reference/chatwoot/app/jobs/webhook_job.rb (delivery contract)

For each dispatcher event we know how to map (see :data:`_EVENT_MAP`),
the listener:
  1. Resolves the subject (conversation / message / contact) from the
     payload + maps to the canonical webhook event name.
  2. Looks up every account-type Webhook whose ``subscriptions``
     includes that event name.
  3. POSTs the standard envelope to each Webhook with the
     ``X-Chatwoot-Signature`` HMAC header.

Failure isolation: per-webhook try/except so a single bad receiver
doesn't fail siblings or the request cycle.

Phase 8.3 scope:
  * conversation_created / conversation_updated / conversation_status_changed
  * message_created
  * Activity messages are skipped (mirrors ``webhook_sendable?``).
  * contact_created / contact_updated (``Contact#webhook_data``). Unlike
    Rails, whose ``changed_attributes`` always carries ``updated_at``, an
    update that changes nothing the webhook exposes is not sent.

AloStudio extensions (not in Chatwoot), same envelope; their dates are
ISO 8601 strings:
  * appointment_created / appointment_updated
  * publication_completed — once every channel of a publication is
    settled, with the per-channel result.

Every event is delivered after the commit, like Rails' ``after_*_commit``
callbacks; ``changed_attributes`` uses Rails' ``extract_changed_attributes``
shape for every event.

Deferred:
  * inbox_created / inbox_updated — not yet dispatched as ``INBOX_*``.
  * conversation_typing_on / off — needs the typing payload. Not
    parity-critical for v4.13.0 webhook receivers.
  * webwidget_triggered / message_updated.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.accounts.models import Account
from app.domains.agent_bots.listener import (
    _build_conversation_webhook_body,
    _build_message_webhook_body,
    _is_webhook_sendable,
    _jsonable,
    extract_changed_attributes,
)
from app.domains.appointments.models import Appointment
from app.domains.contacts.models import Contact
from app.domains.conversations import events as ev
from app.domains.conversations.models import Conversation, Message
from app.domains.publishing.models import Publication
from app.domains.webhooks.models import RECEIVER_KIND_WEBHOOK
from app.domains.webhooks.service import webhooks_subscribed_to
from app.workers.deliver_webhook import enqueue_delivery

log = logging.getLogger(__name__)

# Dispatcher event name → ``Webhook.subscriptions`` event name.
_EVENT_MAP: dict[str, str] = {
    ev.CONVERSATION_CREATED: "conversation_created",
    ev.CONVERSATION_UPDATED: "conversation_updated",
    ev.CONVERSATION_STATUS_CHANGED: "conversation_status_changed",
    ev.MESSAGE_CREATED: "message_created",
    ev.CONTACT_CREATED: "contact_created",
    ev.CONTACT_UPDATED: "contact_updated",
    ev.APPOINTMENT_CREATED: "appointment_created",
    ev.APPOINTMENT_UPDATED: "appointment_updated",
    ev.PUBLICATION_COMPLETED: "publication_completed",
}

# Events whose subject is a record rather than a conversation/message.
_RECORD_EVENTS = frozenset(
    {
        "contact_created",
        "contact_updated",
        "appointment_created",
        "appointment_updated",
        "publication_completed",
    }
)


async def fan_out_to_webhooks(
    session: AsyncSession, event_name: str, **payload: Any
) -> None:
    subscribed_name = _EVENT_MAP.get(event_name)
    if subscribed_name is None:
        return

    if subscribed_name in _RECORD_EVENTS:
        account_id, builder = await _resolve_record_subject(
            session, subscribed_name, payload
        )
    else:
        account_id, builder = _resolve_subject(subscribed_name, payload)
    if account_id is None or builder is None:
        return

    webhooks = await webhooks_subscribed_to(
        session, account_id=account_id, event_name=subscribed_name
    )
    if not webhooks:
        return
    for hook in webhooks:
        # Per-delivery event_id (v2.7) so the same logical event sent
        # to multiple subscribers carries distinct dedupe keys.
        body = builder(event_id=str(uuid.uuid4()))
        delivery = {
            "account_id": account_id,
            "receiver_kind": RECEIVER_KIND_WEBHOOK,
            "receiver_id": hook.id,
            "url": hook.url,
            "event_name": subscribed_name,
            "body": body,
            "secret": hook.secret,
        }
        # Rails dispatches from ``after_*_commit``: never announce what a
        # rollback is about to erase. Once committed it is enqueued (v2.9);
        # the ARQ task handles retries + dead-letter, and the inline
        # fallback (no ARQ pool) delivers once and records the dead letter.
        _deliver_after_commit(session, delivery)


# ---------------------------------------------------------------------------
# Delivery after commit
# ---------------------------------------------------------------------------
# Every webhook waits for the outermost commit and is dropped when the
# transaction — or the savepoint it was raised in — rolls back.
_PENDING_KEY = "webhooks_after_commit"
_in_flight: set[asyncio.Task[None]] = set()


def _deliver_after_commit(session: AsyncSession, delivery: dict[str, Any]) -> None:
    sync = session.sync_session
    transaction = sync.get_nested_transaction() or sync.get_transaction()
    sync.info.setdefault(_PENDING_KEY, []).append((transaction, delivery))


def _within(transaction: Any, closed: Any) -> bool:
    while transaction is not None:
        if transaction is closed:
            return True
        transaction = transaction.parent
    return False


@event.listens_for(Session, "after_soft_rollback")
def _drop_rolled_back(session: Session, previous_transaction: Any) -> None:
    pending = session.info.get(_PENDING_KEY)
    if pending:
        session.info[_PENDING_KEY] = [
            (tx, delivery)
            for tx, delivery in pending
            if not _within(tx, previous_transaction)
        ]


@event.listens_for(Session, "after_commit")
def _send_committed(session: Session) -> None:
    pending = session.info.pop(_PENDING_KEY, None)
    if not pending:
        return
    task = asyncio.get_running_loop().create_task(
        _enqueue_all([delivery for _, delivery in pending])
    )
    _in_flight.add(task)
    task.add_done_callback(_in_flight.discard)


async def _enqueue_all(deliveries: list[dict[str, Any]]) -> None:
    """Enqueue on a session of its own: the committing one is done, and
    the inline fallback may need to write a dead-letter row."""
    from app.core.db import get_session_factory

    try:
        async with get_session_factory()() as session:
            for delivery in deliveries:
                await enqueue_delivery(session=session, **delivery)
            await session.commit()
    except Exception:
        log.exception("webhook_listener.after_commit_failed")


async def wait_for_pending_deliveries() -> None:
    """Await the post-commit enqueues still running (tests, shutdown)."""
    if _in_flight:
        await asyncio.gather(*list(_in_flight), return_exceptions=True)


# A builder closure here keeps the per-hook ``event_id`` injection clean
# without re-walking the payload for each receiver.
def _resolve_subject(
    subscribed_name: str, payload: dict[str, Any]
) -> tuple[int | None, Any]:
    """Build (account_id, body_builder(event_id) → dict) for the event.

    Returns ``(None, None)`` when the payload doesn't carry the
    expected subject (defensive — listeners must never raise)."""
    if subscribed_name == "message_created":
        message = payload.get("message")
        if not isinstance(message, Message):
            return None, None
        if not _is_webhook_sendable(message):
            return None, None
        conversation = message.conversation
        if not isinstance(conversation, Conversation):
            return None, None

        def _build(*, event_id: str) -> dict[str, Any]:
            return _build_message_webhook_body(
                conversation=conversation,
                message=message,
                event_name=subscribed_name,
                event_id=event_id,
            )

        return conversation.account_id, _build

    # Conversation-level events.
    conversation = payload.get("conversation")
    if not isinstance(conversation, Conversation):
        return None, None
    changed_attributes = payload.get("changed_attributes")

    def _build_conv(*, event_id: str) -> dict[str, Any]:
        return _build_conversation_webhook_body(
            conversation=conversation,
            event_name=subscribed_name,
            changed_attributes=changed_attributes,
            event_id=event_id,
        )

    return conversation.account_id, _build_conv


def _contact_webhook_data(contact: Contact) -> dict[str, Any]:
    """Mirror ``Contact#webhook_data``. Avatars aren't stored yet (same
    empty value the contact presenter emits)."""
    return {
        "account": {"id": contact.account_id},
        "additional_attributes": contact.additional_attributes or {},
        "avatar": "",
        "custom_attributes": contact.custom_attributes or {},
        "email": contact.email,
        "id": contact.id,
        "identifier": contact.identifier,
        "name": contact.name,
        "phone_number": contact.phone_number,
        "thumbnail": "",
        "blocked": bool(contact.blocked),
    }


def _appointment_webhook_data(appointment: Appointment) -> dict[str, Any]:
    return {
        "account": {"id": appointment.account_id},
        "id": appointment.id,
        "contact_id": appointment.contact_id,
        "product_id": appointment.product_id,
        "title": appointment.title,
        "description": appointment.description,
        "starts_at": _jsonable(appointment.starts_at),
        "ends_at": _jsonable(appointment.ends_at),
        "status": appointment.status,
        "notes": appointment.notes,
        "created_by_id": appointment.created_by_id,
    }


async def _publication_webhook_data(
    session: AsyncSession, publication: Publication
) -> dict[str, Any]:
    from app.domains.publishing.service import channels_by_id, targets_by_publication

    targets = (
        await targets_by_publication(
            session, publication_ids=[publication.id]  # type: ignore[list-item]
        )
    ).get(publication.id, [])  # type: ignore[call-overload]
    channels = await channels_by_id(
        session, channel_ids=[t.channel_id for t in targets]
    )
    return {
        "account": {"id": publication.account_id},
        "id": publication.id,
        "state": publication.state,
        "content": publication.content,
        "media": publication.media or [],
        "scheduled_for": _jsonable(publication.scheduled_for),
        "published_at": _jsonable(publication.published_at),
        "targets": [
            {
                "channel_id": t.channel_id,
                # Set for channels that publish through an inbox.
                "inbox_id": channels[t.channel_id].inbox_id
                if t.channel_id in channels
                else None,
                "network": t.network,
                "state": t.state,
                "external_id": t.external_id,
                "permalink": t.permalink,
                "error_code": t.error_code,
                "error_message": t.error_message,
                "published_at": _jsonable(t.published_at),
            }
            for t in targets
        ],
    }


async def _resolve_record_subject(
    session: AsyncSession, subscribed_name: str, payload: dict[str, Any]
) -> tuple[int | None, Any]:
    """(account_id, body_builder) for contact / appointment / publication
    events. ``(None, None)`` when the payload lacks its subject, or for an
    update with no change the webhook exposes."""
    changed = extract_changed_attributes(payload.get("changed_attributes"))
    if subscribed_name.endswith("_updated") and changed is None:
        return None, None

    data: dict[str, Any]
    if subscribed_name.startswith("contact_"):
        contact = payload.get("contact")
        if not isinstance(contact, Contact):
            return None, None
        data = _contact_webhook_data(contact)
    elif subscribed_name.startswith("appointment_"):
        appointment = payload.get("appointment")
        if not isinstance(appointment, Appointment):
            return None, None
        data = _appointment_webhook_data(appointment)
    else:
        publication = payload.get("publication")
        if not isinstance(publication, Publication):
            return None, None
        data = await _publication_webhook_data(session, publication)

    # ``Account#webhook_data`` is ``{id, name}``.
    account = await session.get(Account, data["account"]["id"])
    if account is not None:
        data["account"] = {"id": account.id, "name": account.name}

    def _build(*, event_id: str) -> dict[str, Any]:
        body: dict[str, Any] = {"event": subscribed_name, **data}
        if changed is not None:
            body["changed_attributes"] = changed
        body["event_id"] = event_id
        return body

    return data["account"]["id"], _build


__all__ = ["fan_out_to_webhooks", "wait_for_pending_deliveries"]
