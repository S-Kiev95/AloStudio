"""Handoff between Meta Business Agent and AloStudio on a WhatsApp number.

Meta Business Agent is Meta's own AI responder for a WhatsApp Business
number. When the business sets it as the number's responder and lets
AloStudio take over conversations ("Thread control" in Business Suite
conversation routing), a conversation is owned by one side at a time:

  * ``ai_agent`` — Meta Business Agent answers; the team reads along.
  * ``app``      — AloStudio owns it; agents answer from the inbox.

Control moves through four doors:

  * Meta pushes a ``messaging_handovers`` webhook when the agent hands a
    conversation off (or takes it back). :func:`process_handover_value`
    applies it.
  * An agent presses "take over" / "return to the AI", which calls the
    Thread Control (Cloud API) endpoint (:func:`take_over`,
    :func:`return_to_ai`).
  * An agent replies while the AI owns the chat: the reply takes it first
    (:func:`take_over_before_reply`), so both never answer at once.
  * Resolving a conversation the team owned hands it back to the agent,
    from a job queued by the whatsapp listener
    (:func:`release_resolved_conversation`).

The owner lives in ``conversation.additional_attributes["thread_control"]``
(no migration; the conversation presenter already ships the blob to the
dashboard). The channel opts in through ``provider_config``:

  * ``meta_business_agent`` — the number has Meta Business Agent as its
    responder. Set by hand or by the first parsed handover webhook.
  * ``meta_business_agent_return_on_resolve`` — hand the conversation
    back on resolve (default ``True``).

Meta documents the Thread Control request, but not yet the WhatsApp
shape of ``messaging_handovers``. The parser therefore reads the
Messenger handover keys plus the obvious WhatsApp variants, and logs the
key set of anything it cannot read so the shape can be pinned down from
the first real events.

Anchors:
  https://developers.facebook.com/documentation/meta-business-agent/reference/operate/thread-control-cloud-api
  https://developers.facebook.com/documentation/business-messaging/messenger-platform/webhooks/webhook-events/messaging_handovers
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import httpx
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.activities import create_activity_message
from app.domains.conversations.events import CONVERSATION_UPDATED, dispatcher
from app.domains.conversations.models import (
    CONVERSATION_STATUS_RESOLVED,
    Conversation,
)
from app.domains.conversations.service import toggle_status
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WHATSAPP,
    WHATSAPP_PROVIDER_CLOUD,
    Inbox,
    WhatsappChannel,
)

log = logging.getLogger(__name__)

OWNER_AI_AGENT = "ai_agent"
OWNER_APP = "app"

FLAG_ENABLED = "meta_business_agent"
FLAG_RETURN_ON_RESOLVE = "meta_business_agent_return_on_resolve"

_STATE_KEY = "thread_control"
_HANDOVER_KEYS = (
    "pass_thread_control",
    "take_thread_control",
    "release_thread_control",
)

# Thread Control lives on api.facebook.com, not graph.facebook.com, and
# is versioned by header. Overridable for tests and for a proxy.
_THREAD_CONTROL_API_VERSION = "1.0.0"


def _api_base() -> str:
    return os.environ.get(
        "META_BUSINESS_AGENT_API_BASE", "https://api.facebook.com"
    )


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
def business_agent_enabled(channel: WhatsappChannel) -> bool:
    cfg = channel.provider_config or {}
    return (
        channel.provider == WHATSAPP_PROVIDER_CLOUD
        and isinstance(cfg, dict)
        and bool(cfg.get(FLAG_ENABLED))
    )


def thread_owner(conversation: Conversation) -> str | None:
    state = (conversation.additional_attributes or {}).get(_STATE_KEY)
    if isinstance(state, dict):
        owner = state.get("owner")
        if owner in (OWNER_AI_AGENT, OWNER_APP):
            return str(owner)
    return None


def _write_owner(
    conversation: Conversation, owner: str, *, metadata: str | None
) -> None:
    state: dict[str, Any] = {"owner": owner, "updated_at": int(time.time())}
    if metadata:
        state["metadata"] = metadata
    # Reassign rather than mutate so the JSON column is marked dirty.
    conversation.additional_attributes = {
        **(conversation.additional_attributes or {}),
        _STATE_KEY: state,
    }


async def _set_owner(
    session: AsyncSession,
    *,
    conversation: Conversation,
    owner: str,
    activity: str | None,
    metadata: str | None = None,
) -> None:
    previous = thread_owner(conversation)
    _write_owner(conversation, owner, metadata=metadata)
    session.add(conversation)
    await session.flush()
    # The flush expires server-filled columns (updated_at); the listeners'
    # presenters read them outside a greenlet, so reload first.
    await session.refresh(conversation)
    if previous != owner:
        await dispatcher.dispatch(
            session,
            CONVERSATION_UPDATED,
            conversation=conversation,
            changed_attributes={_STATE_KEY: [previous, owner]},
        )
    if activity:
        await create_activity_message(
            session, conversation=conversation, content=activity
        )


def mark_ai_owner_if_unknown(
    conversation: Conversation, channel: WhatsappChannel
) -> bool:
    """A new conversation on a Business Agent number starts with the AI:
    Meta routes the first message to it. Silent (no activity row), since
    nothing changed hands. Returns ``True`` when it stamped the owner."""
    if not business_agent_enabled(channel) or thread_owner(conversation):
        return False
    _write_owner(conversation, OWNER_AI_AGENT, metadata=None)
    return True


# ---------------------------------------------------------------------------
# Thread Control (Cloud API)
# ---------------------------------------------------------------------------
async def request_thread_control(
    channel: WhatsappChannel,
    *,
    to_phone: str,
    action: str,
    metadata: str | None = None,
) -> str | None:
    """POST a ``take`` / ``release`` to Meta. Returns ``None`` on success,
    else a short error for the caller to show. Never raises."""
    cfg = channel.provider_config or {}
    api_key = cfg.get("api_key") if isinstance(cfg, dict) else None
    phone_number_id = (
        cfg.get("phone_number_id") if isinstance(cfg, dict) else None
    )
    if not api_key or not phone_number_id:
        return "the WhatsApp channel has no access token or phone number id"

    body: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "action": action,
        "to": to_phone.lstrip("+"),
    }
    if metadata:
        body["metadata"] = metadata
    url = (
        f"{_api_base()}/business/whatsapp/phone_numbers/"
        f"{phone_number_id}/thread_control"
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "X-API-Version": _THREAD_CONTROL_API_VERSION,
                },
                json=body,
            )
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        log.warning(
            "whatsapp.thread_control.transport_error channel_id=%s action=%s err=%s",
            channel.id,
            action,
            exc,
        )
        return "Meta could not be reached"

    if resp.status_code >= 400:
        log.warning(
            "whatsapp.thread_control.api_error channel_id=%s action=%s status=%s body=%s",
            channel.id,
            action,
            resp.status_code,
            resp.text[:500],
        )
        try:
            error = resp.json().get("error") or {}
            message = error.get("error_user_msg") or error.get("message")
        except (ValueError, AttributeError):
            message = None
        return str(message or f"Meta answered {resp.status_code}")
    return None


async def _channel_of(
    session: AsyncSession, conversation: Conversation
) -> WhatsappChannel | None:
    # Explicit gets rather than relationships: listeners and jobs run
    # outside the request's eager loads, where a lazy load fails.
    inbox = await session.get(Inbox, conversation.inbox_id)
    if inbox is None or inbox.channel_type != CHANNEL_TYPE_WHATSAPP:
        return None
    if not isinstance(inbox.channel_id, int):
        return None
    return await session.get(WhatsappChannel, inbox.channel_id)


async def _contact_of(
    session: AsyncSession, conversation: Conversation
) -> Contact | None:
    return await session.get(Contact, conversation.contact_id)


async def _channel_and_phone(
    session: AsyncSession, conversation: Conversation
) -> tuple[WhatsappChannel, str]:
    channel = await _channel_of(session, conversation)
    if channel is None or channel.provider != WHATSAPP_PROVIDER_CLOUD:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": "Handing off to the AI only works on WhatsApp Cloud inboxes"
            },
        )
    contact = await _contact_of(session, conversation)
    if contact is None or not contact.phone_number:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "The contact has no WhatsApp number"},
        )
    return channel, contact.phone_number


def _enable_on_channel(session: AsyncSession, channel: WhatsappChannel) -> None:
    if business_agent_enabled(channel):
        return
    channel.provider_config = {
        **(channel.provider_config or {}),
        FLAG_ENABLED: True,
    }
    session.add(channel)


async def take_over(
    session: AsyncSession,
    *,
    conversation: Conversation,
    user_name: str | None,
) -> Conversation:
    """An agent takes the conversation from Meta Business Agent."""
    channel, phone = await _channel_and_phone(session, conversation)
    error = await request_thread_control(channel, to_phone=phone, action="take")
    if error:
        raise ChatwootHTTPException(
            status_code=502,
            detail={"message": f"Meta did not hand over the conversation: {error}"},
        )
    _enable_on_channel(session, channel)
    await _set_owner(
        session,
        conversation=conversation,
        owner=OWNER_APP,
        activity=f"{user_name or 'An agent'} took over the conversation from Meta Business Agent",
    )
    return conversation


async def return_to_ai(
    session: AsyncSession,
    *,
    conversation: Conversation,
    user_name: str | None,
) -> Conversation:
    """An agent hands the conversation back to Meta Business Agent."""
    channel, phone = await _channel_and_phone(session, conversation)
    error = await request_thread_control(
        channel, to_phone=phone, action="release"
    )
    if error:
        raise ChatwootHTTPException(
            status_code=502,
            detail={"message": f"Meta did not take the conversation back: {error}"},
        )
    _enable_on_channel(session, channel)
    await _set_owner(
        session,
        conversation=conversation,
        owner=OWNER_AI_AGENT,
        activity=f"{user_name or 'An agent'} returned the conversation to Meta Business Agent",
    )
    return conversation


async def take_over_before_reply(
    session: AsyncSession,
    *,
    conversation: Conversation,
    channel: WhatsappChannel,
    to_phone: str,
    user_name: str | None,
) -> None:
    """Take the conversation before an agent's reply goes out while the AI
    still owns it, so the AI and the agent never answer at the same time.

    A refusal is recorded on the conversation and the reply still goes
    out: Meta decides whether to deliver it, and the agent sees why the
    AI may keep answering. Never raises.
    """
    if not business_agent_enabled(channel):
        return
    if thread_owner(conversation) != OWNER_AI_AGENT:
        return
    error = await request_thread_control(channel, to_phone=to_phone, action="take")
    if error:
        await create_activity_message(
            session,
            conversation=conversation,
            content=f"Could not take the conversation from Meta Business Agent: {error}",
        )
        return
    await _set_owner(
        session,
        conversation=conversation,
        owner=OWNER_APP,
        activity=f"{user_name or 'An agent'} took over the conversation from Meta Business Agent by replying",
    )


async def release_resolved_conversation(
    session: AsyncSession, *, conversation_id: int
) -> str:
    """Hand a resolved conversation the team owned back to the AI.

    Runs as a job after the resolve committed, so it re-reads everything:
    a conversation reopened in between, a muted (blocked) contact, or a
    channel with ``meta_business_agent_return_on_resolve`` off stays with
    the team. Returns the outcome for the job log. Never raises.
    """
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        return "conversation_gone"
    if conversation.status != CONVERSATION_STATUS_RESOLVED:
        return "not_resolved"
    if thread_owner(conversation) != OWNER_APP:
        return "not_owned"
    channel = await _channel_of(session, conversation)
    if channel is None or not business_agent_enabled(channel):
        return "not_business_agent"
    if not (channel.provider_config or {}).get(FLAG_RETURN_ON_RESOLVE, True):
        return "return_on_resolve_off"
    contact = await _contact_of(session, conversation)
    if contact is None or not contact.phone_number or contact.blocked:
        return "no_contact"
    error = await request_thread_control(
        channel, to_phone=contact.phone_number, action="release"
    )
    if error:
        await create_activity_message(
            session,
            conversation=conversation,
            content=f"Could not return the conversation to Meta Business Agent: {error}",
        )
        return "meta_refused"
    await _set_owner(
        session,
        conversation=conversation,
        owner=OWNER_AI_AGENT,
        activity="Conversation resolved and returned to Meta Business Agent",
    )
    return "released"


# ---------------------------------------------------------------------------
# messaging_handovers webhook
# ---------------------------------------------------------------------------
_LONG_NUMBER = re.compile(r"\d{7,}")


def _masked(value: Any) -> str:
    """The payload as JSON with long digit runs (phones, ids) masked."""
    try:
        text = json.dumps(value, ensure_ascii=False)[:2000]
    except (TypeError, ValueError):
        text = str(value)[:2000]
    return _LONG_NUMBER.sub(lambda m: f"{m.group(0)[:3]}***", text)


def _handover_items(value: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("messaging_handovers", "handovers", "thread_control"):
        items = value.get(key)
        if isinstance(items, list):
            return [i for i in items if isinstance(i, dict)]
        if isinstance(items, dict):
            return [items]
    return [value]


def _consumer_phone(
    item: dict[str, Any], value: dict[str, Any], *, own: set[str]
) -> str | None:
    """The customer's number. ``own`` holds the business's number and
    phone-number id, which some keys may carry instead."""

    def pick(raw: Any) -> str | None:
        text = str(raw).strip().lstrip("+") if raw is not None else ""
        return text if text and text not in own else None

    for key in ("from", "to", "wa_id", "recipient_id"):
        if isinstance(item.get(key), (str, int)):
            found = pick(item[key])
            if found:
                return found
    for key in ("sender", "recipient", "user"):
        node = item.get(key)
        if isinstance(node, dict):
            for inner in ("wa_id", "id", "phone_number"):
                found = pick(node.get(inner))
                if found:
                    return found
    contacts = value.get("contacts")
    if isinstance(contacts, list) and contacts and isinstance(contacts[0], dict):
        return pick(contacts[0].get("wa_id"))
    return None


def _new_owner(item: dict[str, Any]) -> tuple[str | None, str | None]:
    """``(owner, metadata)`` from one handover item."""
    control: dict[str, Any] | None = None
    action: str | None = None
    for key in _HANDOVER_KEYS:
        if isinstance(item.get(key), dict):
            control, action = item[key], key.split("_", 1)[0]
            break
    if control is None:
        control = item
        action = str(item.get("action") or item.get("type") or "") or None
    metadata = control.get("metadata") or item.get("metadata")
    metadata = str(metadata) if metadata else None

    control_pass = control.get("control_pass")
    target = control.get("target_role") or (
        control_pass.get("target_role") if isinstance(control_pass, dict) else None
    )
    if target == "ai_agent" or action == "release":
        return OWNER_AI_AGENT, metadata
    new_app = control.get("new_owner_app_id") or control.get("new_owner")
    our_app_id = str(get_settings().meta_app_id or "")
    if new_app is not None and str(new_app) and our_app_id:
        owner = OWNER_APP if str(new_app) == our_app_id else OWNER_AI_AGENT
        return owner, metadata
    if new_app is not None and str(new_app):
        log.warning(
            "whatsapp.handover.no_app_id META_APP_ID is unset, owner read from the action"
        )
    # A pass with no target reaches the configured escalation partner (us,
    # since we received it); a take is the other side taking it from us.
    if action == "pass":
        return OWNER_APP, metadata
    if action == "take":
        return OWNER_AI_AGENT, metadata
    return None, metadata


async def _conversation_for_phone(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    inbox: Inbox,
    phone: str,
    create: bool,
) -> Conversation | None:
    from app.domains.whatsapp.incoming_cloud import (
        _find_or_create_contact,
        _find_or_create_conversation,
    )

    normalized = f"+{phone.lstrip('+')}"
    contact_inbox = (
        await session.exec(
            select(ContactInbox).where(
                ContactInbox.inbox_id == inbox.id,
                ContactInbox.source_id == normalized,
            )
        )
    ).first()
    if contact_inbox is None:
        if not create:
            return None
        contact = await _find_or_create_contact(
            session,
            account_id=channel.account_id,
            phone_number=normalized,
            name=None,
        )
        contact_inbox = await ContactInboxBuilder(
            session=session,
            contact=contact,
            inbox=inbox,
            source_id=normalized,
        ).perform()
    elif not create:
        return (
            await session.exec(
                select(Conversation)
                .where(Conversation.contact_inbox_id == contact_inbox.id)
                .order_by(Conversation.id.desc())
                .limit(1)
            )
        ).first()
    return await _find_or_create_conversation(session, contact_inbox=contact_inbox)


async def process_handover_value(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    inbox: Inbox,
    value: dict[str, Any],
) -> list[Conversation]:
    """Apply a ``messaging_handovers`` change. Unknown shapes are logged
    and dropped, never raised: Meta must always get its 200."""
    # Masked, and at debug: the payload can carry profile names and the
    # AI's own summary of the chat.
    log.debug(
        "whatsapp.handover.received channel_id=%s value=%s",
        channel.id,
        _masked(value),
    )
    cfg = channel.provider_config or {}
    own = {
        str(x).lstrip("+")
        for x in (channel.phone_number, cfg.get("phone_number_id"))
        if x
    }
    changed: list[Conversation] = []
    for item in _handover_items(value):
        phone = _consumer_phone(item, value, own=own)
        owner, metadata = _new_owner(item)
        if not phone or owner is None:
            log.warning(
                "whatsapp.handover.unparsed channel_id=%s keys=%s",
                channel.id,
                sorted(item.keys()),
            )
            continue
        # A real handover proves the number runs Meta Business Agent.
        _enable_on_channel(session, channel)
        conversation = await _conversation_for_phone(
            session,
            channel=channel,
            inbox=inbox,
            phone=phone,
            # Only a handoff to the team needs a conversation to show; "back
            # to the AI" for a chat we never saw changes nothing here.
            create=owner == OWNER_APP,
        )
        # Same owner again: a redelivery, or the echo of our own take.
        if conversation is None or thread_owner(conversation) == owner:
            continue
        if owner == OWNER_APP:
            # A handoff is a request for a person: make sure it shows up
            # in the open queue even if the last chat was resolved.
            if conversation.status == CONVERSATION_STATUS_RESOLVED:
                await toggle_status(session, conversation=conversation, status="open")
            activity = "Meta Business Agent handed the conversation off to the team"
            if metadata:
                activity = f"{activity}: {metadata}"
        else:
            activity = "Meta Business Agent is answering the conversation again"
        await _set_owner(
            session,
            conversation=conversation,
            owner=owner,
            activity=activity,
            metadata=metadata,
        )
        changed.append(conversation)
    log.info(
        "whatsapp.handover.applied channel_id=%s conversations=%s",
        channel.id,
        [c.id for c in changed],
    )
    return changed


__all__ = [
    "FLAG_ENABLED",
    "FLAG_RETURN_ON_RESOLVE",
    "OWNER_AI_AGENT",
    "OWNER_APP",
    "business_agent_enabled",
    "mark_ai_owner_if_unknown",
    "process_handover_value",
    "release_resolved_conversation",
    "request_thread_control",
    "return_to_ai",
    "take_over",
    "take_over_before_reply",
    "thread_owner",
]
