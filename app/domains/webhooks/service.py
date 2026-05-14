"""Webhook CRUD service.

Ported from:
  reference/chatwoot/app/controllers/api/v1/accounts/webhooks_controller.rb
  reference/chatwoot/app/models/webhook.rb (validate_webhook_subscriptions)
"""

from __future__ import annotations

import re
import secrets
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.webhooks.models import (
    ALLOWED_WEBHOOK_EVENTS,
    WEBHOOK_TYPE_ACCOUNT,
    WEBHOOK_TYPE_INBOX,
    Webhook,
)

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _new_secret() -> str:
    return secrets.token_hex(12)


def _validate_url(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Url can't be blank"},
        )
    url = raw.strip()
    if not _URL_RE.match(url):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Url is invalid"},
        )
    return url


def _validate_subscriptions(raw: Any) -> list[str]:
    """Mirror ``validate_webhook_subscriptions`` — non-empty array, no
    unknown event names, deduped."""
    if not isinstance(raw, list) or not raw:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Subscriptions are invalid"},
        )
    allowed = set(ALLOWED_WEBHOOK_EVENTS)
    seen: set[str] = set()
    cleaned: list[str] = []
    for entry in raw:
        if not isinstance(entry, str) or entry in seen:
            continue
        seen.add(entry)
        cleaned.append(entry)
    if not cleaned:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Subscriptions are invalid"},
        )
    if set(cleaned) - allowed:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Subscriptions are invalid"},
        )
    return cleaned


async def list_webhooks(
    session: AsyncSession, *, account_id: int
) -> list[Webhook]:
    return list(
        (
            await session.exec(
                select(Webhook)
                .where(Webhook.account_id == account_id)
                .order_by(Webhook.id.asc())  # type: ignore[attr-defined]
            )
        ).all()
    )


async def fetch_webhook(
    session: AsyncSession, *, account_id: int, webhook_id: int
) -> Webhook | None:
    return (
        await session.exec(
            select(Webhook).where(
                Webhook.id == webhook_id,
                Webhook.account_id == account_id,
            )
        )
    ).first()


async def create_webhook(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
) -> Webhook:
    url = _validate_url(payload.get("url"))
    subscriptions = _validate_subscriptions(payload.get("subscriptions"))
    inbox_id = payload.get("inbox_id")
    webhook_type = (
        WEBHOOK_TYPE_INBOX if inbox_id is not None else WEBHOOK_TYPE_ACCOUNT
    )
    webhook = Webhook(
        account_id=account_id,
        inbox_id=inbox_id,
        url=url,
        name=payload.get("name"),
        subscriptions=subscriptions,
        webhook_type=webhook_type,
        secret=_new_secret(),
    )
    session.add(webhook)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Url has already been taken"},
        ) from exc
    await session.refresh(webhook)
    return webhook


async def update_webhook(
    session: AsyncSession,
    *,
    webhook: Webhook,
    payload: dict[str, Any],
) -> Webhook:
    if "url" in payload:
        webhook.url = _validate_url(payload.get("url"))
    if "name" in payload:
        webhook.name = payload.get("name")
    if "subscriptions" in payload:
        webhook.subscriptions = _validate_subscriptions(
            payload.get("subscriptions")
        )
    if "inbox_id" in payload:
        inbox_id = payload.get("inbox_id")
        webhook.inbox_id = inbox_id
        webhook.webhook_type = (
            WEBHOOK_TYPE_INBOX if inbox_id is not None else WEBHOOK_TYPE_ACCOUNT
        )
    session.add(webhook)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Url has already been taken"},
        ) from exc
    await session.refresh(webhook)
    return webhook


async def destroy_webhook(session: AsyncSession, *, webhook: Webhook) -> None:
    await session.delete(webhook)
    await session.flush()


async def webhooks_subscribed_to(
    session: AsyncSession, *, account_id: int, event_name: str
) -> list[Webhook]:
    """Return every account-type webhook on the account whose
    ``subscriptions`` includes the given event name. Inbox-scoped
    webhooks join later when their feature lands."""
    stmt = select(Webhook).where(
        Webhook.account_id == account_id,
        Webhook.webhook_type == WEBHOOK_TYPE_ACCOUNT,
        # Postgres JSONB ? operator — element existence check.
        Webhook.subscriptions.op("?")(event_name),  # type: ignore[union-attr]
    )
    return list((await session.exec(stmt)).all())


__all__ = [
    "create_webhook",
    "destroy_webhook",
    "fetch_webhook",
    "list_webhooks",
    "update_webhook",
    "webhooks_subscribed_to",
]
