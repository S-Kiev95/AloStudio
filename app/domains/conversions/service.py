"""Conversions API (F17): what the account reports to Meta, queuing the
events as they happen, and sending them (the 5-minute tick)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Conversation
from app.domains.conversions import client
from app.domains.conversions.models import (
    EVENTS,
    MAX_ATTEMPTS,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SENT,
    ConversionDataset,
    ConversionEvent,
    ConversionSettings,
)
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WHATSAPP,
    WHATSAPP_PROVIDER_CLOUD,
    Inbox,
    WhatsappChannel,
)

log = logging.getLogger(__name__)

CRM_TRIGGERS = ("opportunity_created", "opportunity_qualified", "opportunity_won")
DEFAULT_RULES: dict[str, Any] = {
    "opportunity_created": "LeadSubmitted",
    "opportunity_qualified": "QualifiedLead",
    "opportunity_won": "Purchase",
    "closing": {},
}
# The seeded CRM stage that means "qualified".
QUALIFIED_STAGE_CODE = "qualified"
CLOSING_MAX = 30
LOG_LIMIT = 50
SEND_BATCH = 50


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def rules_of(row: ConversionSettings | None) -> dict[str, Any]:
    raw = row.rules if row is not None and isinstance(row.rules, dict) else {}
    out: dict[str, Any] = {k: raw[k] if k in raw else DEFAULT_RULES[k] for k in CRM_TRIGGERS}
    closing = raw.get("closing")
    out["closing"] = dict(closing) if isinstance(closing, dict) else {}
    return out


def clean_rules(raw: Any) -> dict[str, Any]:
    """Raises ValueError (a short code) when the rules do not hold up."""
    if not isinstance(raw, dict):
        raise ValueError("rules")
    out: dict[str, Any] = {}
    for key in CRM_TRIGGERS:
        event = raw.get(key)
        if event is not None and event not in EVENTS:
            raise ValueError("event")
        out[key] = event
    closing_raw = raw.get("closing") or {}
    if not isinstance(closing_raw, dict) or len(closing_raw) > CLOSING_MAX:
        raise ValueError("closing")
    closing: dict[str, dict[str, Any]] = {}
    for reason, rule in closing_raw.items():
        if not isinstance(reason, str) or not reason.strip() or not isinstance(rule, dict):
            raise ValueError("closing")
        event = rule.get("event")
        if event is None:
            continue
        if event not in EVENTS:
            raise ValueError("event")
        value = rule.get("value")
        if value is not None:
            try:
                value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError("value") from exc
            if value < 0:
                raise ValueError("value")
        closing[" ".join(reason.split())] = {"event": event, "value": value}
    out["closing"] = closing
    return out


def clean_currency(raw: Any) -> str:
    code = str(raw or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError("currency")
    return code


async def _whatsapp_inboxes(
    session: AsyncSession, account_id: int
) -> list[tuple[Inbox, WhatsappChannel]]:
    inboxes = (
        await session.exec(
            select(Inbox)
            .where(Inbox.account_id == account_id, Inbox.channel_type == CHANNEL_TYPE_WHATSAPP)
            .order_by(Inbox.id)  # type: ignore[arg-type]
        )
    ).all()
    out = []
    for inbox in inboxes:
        channel = await session.get(WhatsappChannel, inbox.channel_id)
        if channel is not None and channel.provider == WHATSAPP_PROVIDER_CLOUD:
            out.append((inbox, channel))
    return out


async def present_settings(session: AsyncSession, account_id: int) -> dict[str, Any]:
    row = await session.get(ConversionSettings, account_id)
    inboxes = []
    for inbox, _ in await _whatsapp_inboxes(session, account_id):
        dataset = await session.get(ConversionDataset, inbox.id)
        inboxes.append(
            {
                "inbox_id": inbox.id,
                "name": inbox.name,
                "dataset_id": dataset.dataset_id if dataset else None,
            }
        )
    return {
        "enabled": bool(row and row.enabled),
        "currency": row.currency if row else "USD",
        "rules": rules_of(row),
        "inboxes": inboxes,
    }


async def save_settings(
    session: AsyncSession,
    *,
    account_id: int,
    enabled: bool,
    currency: Any,
    rules: Any | None,
) -> dict[str, Any]:
    row = await session.get(ConversionSettings, account_id)
    if row is None:
        row = ConversionSettings(account_id=account_id)
    row.enabled = enabled
    row.currency = clean_currency(currency)
    if rules is not None:
        row.rules = clean_rules(rules)
    session.add(row)
    await session.flush()
    return await present_settings(session, account_id)


async def connect(session: AsyncSession, inbox: Inbox) -> str:
    """Ask Meta for the number's dataset and keep it. Raises
    :class:`client.ConversionsError`."""
    channel = await session.get(WhatsappChannel, inbox.channel_id)
    if channel is None:
        raise client.ConversionsError("not_connected")
    dataset_id = await client.fetch_dataset(channel)
    row = await session.get(ConversionDataset, inbox.id)
    if row is None:
        row = ConversionDataset(
            inbox_id=inbox.id,
            account_id=inbox.account_id,
            dataset_id=dataset_id,
        )
    row.dataset_id = dataset_id
    session.add(row)
    await session.flush()
    return dataset_id


# ---------------------------------------------------------------------------
# Queuing events
# ---------------------------------------------------------------------------
async def _enabled(session: AsyncSession, account_id: int) -> ConversionSettings | None:
    row = await session.get(ConversionSettings, account_id)
    return row if row is not None and row.enabled else None


async def record(
    session: AsyncSession,
    *,
    conversation: Conversation,
    event_name: str,
    trigger: str,
    detail: str | None,
    value: Decimal | None = None,
    currency: str | None = None,
) -> ConversionEvent | None:
    """Queue ``event_name`` for a conversation that came from a WhatsApp ad.
    ``None`` when it does not apply (off, no ad click, not WhatsApp) or the
    conversation already has that event: Meta does not deduplicate."""
    settings = await _enabled(session, conversation.account_id)
    if settings is None or not conversation.ad_click_id or event_name not in EVENTS:
        return None
    inbox = await session.get(Inbox, conversation.inbox_id)
    if inbox is None or inbox.channel_type != CHANNEL_TYPE_WHATSAPP:
        return None
    if event_name == "Purchase" and value is None:
        value = Decimal("0")
    stmt = (
        pg_insert(ConversionEvent.__table__)  # type: ignore[attr-defined]
        .values(
            account_id=conversation.account_id,
            conversation_id=conversation.id,
            inbox_id=inbox.id,
            event_name=event_name,
            trigger=trigger,
            detail=(detail or None) and detail[:255],
            value=value,
            currency=(currency or settings.currency) if value is not None else None,
            status=STATUS_PENDING,
            attempts=0,
        )
        .on_conflict_do_nothing(constraint="uniq_conversion_event_per_conversation")
        .returning(ConversionEvent.__table__.c.id)  # type: ignore[attr-defined]
    )
    new_id = (await session.exec(stmt)).scalar_one_or_none()
    if new_id is None:
        return None
    log.info(
        "conversions.queued conversation_id=%s event=%s trigger=%s",
        conversation.id,
        event_name,
        trigger,
    )
    return await session.get(ConversionEvent, new_id)


async def on_closing(session: AsyncSession, *, conversation: Conversation, category: str) -> None:
    """A conversation closed with a reason the account maps to an event."""
    settings = await _enabled(session, conversation.account_id)
    if settings is None:
        return
    rule = rules_of(settings)["closing"].get(category)
    if not rule:
        return
    value = rule.get("value")
    await record(
        session,
        conversation=conversation,
        event_name=rule["event"],
        trigger="closing",
        detail=category,
        value=Decimal(str(value)) if value is not None else None,
        currency=settings.currency,
    )


async def _conversation_for(session: AsyncSession, opportunity: Any) -> Conversation | None:
    """The ad conversation an opportunity belongs to: its own, or the
    contact's latest one that came from an ad."""
    if opportunity.conversation_id:
        own = await session.get(Conversation, opportunity.conversation_id)
        if own is not None and own.ad_click_id:
            return own
    if not opportunity.contact_id:
        return None
    return (
        await session.exec(
            select(Conversation)
            .where(
                Conversation.account_id == opportunity.account_id,
                Conversation.contact_id == opportunity.contact_id,
                Conversation.ad_click_id.is_not(None),  # type: ignore[union-attr]
            )
            .order_by(Conversation.created_at.desc())  # type: ignore[attr-defined]
        )
    ).first()


async def on_opportunity(
    session: AsyncSession, *, opportunity: Any, created: bool, entered: Any | None
) -> None:
    """A CRM opportunity was opened, or moved into ``entered`` (a stage)."""
    from app.domains.crm.models import STAGE_WON

    settings = await _enabled(session, opportunity.account_id)
    if settings is None:
        return
    rules = rules_of(settings)
    fired: list[tuple[str, str]] = []
    if created and rules["opportunity_created"]:
        fired.append(("opportunity_created", rules["opportunity_created"]))
    if entered is not None and entered.code == QUALIFIED_STAGE_CODE and rules["opportunity_qualified"]:
        fired.append(("opportunity_qualified", rules["opportunity_qualified"]))
    if entered is not None and entered.kind == STAGE_WON and rules["opportunity_won"]:
        fired.append(("opportunity_won", rules["opportunity_won"]))
    if not fired:
        return
    conversation = await _conversation_for(session, opportunity)
    if conversation is None:
        return
    for trigger, event in fired:
        value = opportunity.value if event == "Purchase" else None
        await record(
            session,
            conversation=conversation,
            event_name=event,
            trigger=trigger,
            detail=opportunity.title,
            value=Decimal(str(value)) if value is not None else None,
            currency=opportunity.currency or settings.currency,
        )


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------
async def _dataset(session: AsyncSession, inbox: Inbox, channel: WhatsappChannel) -> str:
    row = await session.get(ConversionDataset, inbox.id)
    if row is not None:
        return row.dataset_id
    dataset_id = await client.fetch_dataset(channel)
    session.add(
        ConversionDataset(
            inbox_id=inbox.id,
            account_id=inbox.account_id,
            dataset_id=dataset_id,
        )
    )
    await session.flush()
    return dataset_id


def payload_for(event: ConversionEvent, *, waba_id: str, click_id: str) -> dict[str, Any]:
    """The event as Meta reads it."""
    body: dict[str, Any] = {
        "event_name": event.event_name,
        "event_time": int((event.created_at or _now()).timestamp()),
        "action_source": "business_messaging",
        "messaging_channel": "whatsapp",
        "user_data": {"whatsapp_business_account_id": waba_id, "ctwa_clid": click_id},
    }
    if event.value is not None:
        body["custom_data"] = {"currency": event.currency or "USD", "value": float(event.value)}
    return body


async def _send_one(session: AsyncSession, event: ConversionEvent) -> None:
    inbox = await session.get(Inbox, event.inbox_id)
    channel = await session.get(WhatsappChannel, inbox.channel_id) if inbox else None
    conversation = await session.get(Conversation, event.conversation_id)
    if inbox is None or channel is None or conversation is None or not conversation.ad_click_id:
        raise client.ConversionsError("not_connected")
    waba_id, _ = client.credentials(channel)
    dataset_id = await _dataset(session, inbox, channel)
    await client.send_events(
        channel,
        dataset_id,
        [payload_for(event, waba_id=waba_id, click_id=conversation.ad_click_id)],
    )


async def send_pending(session: AsyncSession, *, limit: int = SEND_BATCH) -> int:
    """Send what is queued, for accounts that still have it on. A refusal is
    retried on later ticks, up to :data:`MAX_ATTEMPTS`."""
    rows = (
        await session.exec(
            select(ConversionEvent)
            .where(ConversionEvent.status == STATUS_PENDING)
            .order_by(ConversionEvent.id)  # type: ignore[arg-type]
            .limit(limit)
        )
    ).all()
    enabled: dict[int, bool] = {}
    sent = 0
    for event in rows:
        if event.account_id not in enabled:
            enabled[event.account_id] = await _enabled(session, event.account_id) is not None
        if not enabled[event.account_id]:
            continue
        try:
            await _send_one(session, event)
        except client.ConversionsError as exc:
            event.attempts += 1
            event.error = (exc.detail or exc.code)[:1000]
            if event.attempts >= MAX_ATTEMPTS or exc.code == "not_connected":
                event.status = STATUS_FAILED
            log.warning(
                "conversions.send_failed event_id=%s code=%s attempts=%s",
                event.id,
                exc.code,
                event.attempts,
            )
        else:
            event.status = STATUS_SENT
            event.sent_at = _now()
            event.error = None
            sent += 1
        session.add(event)
        await session.flush()
    return sent


async def recent(session: AsyncSession, *, account_id: int) -> list[dict[str, Any]]:
    """The latest events, newest first, for the log in the panel."""
    rows = (
        await session.exec(
            select(ConversionEvent, Conversation.display_id)
            .join(Conversation, Conversation.id == ConversionEvent.conversation_id)  # type: ignore[arg-type]
            .where(ConversionEvent.account_id == account_id)
            .order_by(ConversionEvent.created_at.desc(), ConversionEvent.id.desc())  # type: ignore[attr-defined,union-attr]
            .limit(LOG_LIMIT)
        )
    ).all()
    return [
        {
            "id": event.id,
            "conversation_id": display_id,
            "event_name": event.event_name,
            "trigger": event.trigger,
            "detail": event.detail,
            "value": float(event.value) if event.value is not None else None,
            "currency": event.currency,
            "status": event.status,
            "error": event.error,
            "created_at": event.created_at,
            "sent_at": event.sent_at,
        }
        for event, display_id in rows
    ]


__all__ = [
    "clean_currency",
    "clean_rules",
    "connect",
    "on_closing",
    "on_opportunity",
    "payload_for",
    "present_settings",
    "recent",
    "record",
    "rules_of",
    "save_settings",
    "send_pending",
]
