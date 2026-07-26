"""Campaign CRUD service.

Ported from:
  reference/chatwoot/app/controllers/api/v1/accounts/campaigns_controller.rb
  reference/chatwoot/app/models/campaign.rb
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func as sa_func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.campaigns.models import (
    CAMPAIGN_TYPE_ONE_OFF,
    Campaign,
    campaign_type_from_str,
)
from app.domains.conversations.models import (
    Conversation,
    Message,
    message_status_to_str,
)
from app.domains.inboxes.models import Inbox


async def _next_display_id(
    session: AsyncSession, *, account_id: int
) -> int:
    """Per-account sequential display_id — 1, 2, 3 .. matches the
    Postgres BEFORE INSERT trigger Chatwoot ships for the column.

    Computed here as ``MAX(display_id) + 1`` filtered by account. Two
    races within the same account would result in a UNIQUE violation
    if a constraint existed; v4.13.0 has none, so we mirror.
    """
    stmt = select(sa_func.coalesce(sa_func.max(Campaign.display_id), 0)).where(
        Campaign.account_id == account_id
    )
    current = int((await session.exec(stmt)).one() or 0)
    return current + 1


async def _validate_inbox(
    session: AsyncSession, *, account_id: int, inbox_id: Any
) -> Inbox:
    if not isinstance(inbox_id, int):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "inbox_id is required"},
        )
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.id == inbox_id, Inbox.account_id == account_id
            )
        )
    ).first()
    if inbox is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Inbox does not belong to the account"},
        )
    return inbox


async def list_campaigns(
    session: AsyncSession, *, account_id: int
) -> list[Campaign]:
    return list(
        (
            await session.exec(
                select(Campaign)
                .where(Campaign.account_id == account_id)
                .order_by(Campaign.id.asc())
            )
        ).all()
    )


async def fetch_campaign_by_display_id(
    session: AsyncSession, *, account_id: int, display_id: int
) -> Campaign | None:
    return (
        await session.exec(
            select(Campaign).where(
                Campaign.account_id == account_id,
                Campaign.display_id == display_id,
            )
        )
    ).first()


async def create_campaign(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
) -> Campaign:
    title = (payload.get("title") or "").strip()
    if not title:
        raise ChatwootHTTPException(
            status_code=422, detail={"message": "Title can't be blank"}
        )
    message = (payload.get("message") or "").strip()
    if not message:
        raise ChatwootHTTPException(
            status_code=422, detail={"message": "Message can't be blank"}
        )
    await _validate_inbox(
        session, account_id=account_id, inbox_id=payload.get("inbox_id")
    )

    raw_type = payload.get("campaign_type")
    if raw_type is None:
        ctype = 0
    elif isinstance(raw_type, str):
        ctype = campaign_type_from_str(raw_type)
    elif isinstance(raw_type, int):
        ctype = raw_type
    else:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "campaign_type is invalid"},
        )

    scheduled_at = payload.get("scheduled_at")
    if scheduled_at is not None and not isinstance(scheduled_at, datetime):
        try:
            scheduled_at = datetime.fromisoformat(
                str(scheduled_at).replace("Z", "+00:00")
            )
        except (TypeError, ValueError) as exc:
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "scheduled_at is invalid"},
            ) from exc

    audience = payload.get("audience") or []
    if not isinstance(audience, list):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "audience must be an array"},
        )

    trigger_rules = payload.get("trigger_rules") or {}
    if not isinstance(trigger_rules, dict):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "trigger_rules must be an object"},
        )

    display_id = await _next_display_id(
        session, account_id=account_id
    )
    campaign = Campaign(
        display_id=display_id,
        account_id=account_id,
        inbox_id=payload["inbox_id"],
        title=title,
        description=payload.get("description"),
        message=message,
        sender_id=payload.get("sender_id"),
        enabled=(
            bool(payload.get("enabled"))
            if "enabled" in payload
            else True
        ),
        trigger_rules=trigger_rules,
        campaign_type=ctype,
        campaign_status=0,
        audience=audience,
        scheduled_at=scheduled_at,
        trigger_only_during_business_hours=bool(
            payload.get("trigger_only_during_business_hours", False)
        ),
        template_params=payload.get("template_params"),
    )
    session.add(campaign)
    await session.flush()
    await session.refresh(campaign)
    return campaign


async def update_campaign(
    session: AsyncSession,
    *,
    campaign: Campaign,
    payload: dict[str, Any],
) -> Campaign:
    """Mirror Rails ``prevent_completed_campaign_from_update``:
    completed campaigns are immutable except via destroy."""
    from app.domains.campaigns.models import CAMPAIGN_STATUS_COMPLETED

    if campaign.campaign_status == CAMPAIGN_STATUS_COMPLETED:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Completed campaign cannot be updated"},
        )

    if "title" in payload:
        new_title = (payload.get("title") or "").strip()
        if not new_title:
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "Title can't be blank"},
            )
        campaign.title = new_title
    if "message" in payload:
        new_message = (payload.get("message") or "").strip()
        if not new_message:
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "Message can't be blank"},
            )
        campaign.message = new_message
    if "description" in payload:
        campaign.description = payload.get("description")
    if "enabled" in payload:
        campaign.enabled = bool(payload.get("enabled"))
    if "trigger_only_during_business_hours" in payload:
        campaign.trigger_only_during_business_hours = bool(
            payload.get("trigger_only_during_business_hours")
        )
    if "audience" in payload:
        raw = payload.get("audience") or []
        if not isinstance(raw, list):
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "audience must be an array"},
            )
        campaign.audience = raw
    if "trigger_rules" in payload:
        raw = payload.get("trigger_rules") or {}
        if not isinstance(raw, dict):
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "trigger_rules must be an object"},
            )
        campaign.trigger_rules = raw
    if "template_params" in payload:
        campaign.template_params = payload.get("template_params")
    if "scheduled_at" in payload:
        raw = payload.get("scheduled_at")
        if raw is None:
            campaign.scheduled_at = None
        elif isinstance(raw, datetime):
            campaign.scheduled_at = raw
        else:
            try:
                campaign.scheduled_at = datetime.fromisoformat(
                    str(raw).replace("Z", "+00:00")
                )
            except (TypeError, ValueError) as exc:
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={"message": "scheduled_at is invalid"},
                ) from exc
    session.add(campaign)
    await session.flush()
    await session.refresh(campaign)
    return campaign


async def destroy_campaign(
    session: AsyncSession, *, campaign: Campaign
) -> None:
    await session.delete(campaign)
    await session.flush()


async def campaign_analytics(
    session: AsyncSession, *, campaign: Campaign
) -> dict[str, Any]:
    """Delivery metrics for one campaign.

    Not a Chatwoot port (v4.13 ships no campaign-reports API) — a
    value-add surface over two things the campaign builder writes: the
    ``conversations.campaign_id`` column (one row per recipient reached)
    and the ``messages.additional_attributes['campaign_id']`` stamp on
    each outgoing campaign message (whose ``status`` carries the
    sent/delivered/read/failed delivery state).
    """
    conversations_count = (
        await session.exec(
            select(sa_func.count())
            .select_from(Conversation)
            .where(
                Conversation.account_id == campaign.account_id,
                Conversation.campaign_id == campaign.id,
            )
        )
    ).one()
    rows = (
        await session.exec(
            select(Message.status, sa_func.count())
            .where(
                Message.account_id == campaign.account_id,
                Message.additional_attributes["campaign_id"].astext
                == str(campaign.id),
            )
            .group_by(Message.status)  # type: ignore[arg-type]
        )
    ).all()
    delivery = {"sent": 0, "delivered": 0, "read": 0, "failed": 0}
    for status_int, count in rows:
        delivery[message_status_to_str(status_int)] = count
    return {
        "campaign_id": campaign.display_id,
        "audience_count": len(campaign.audience or []),
        "conversations_count": conversations_count,
        "messages_count": sum(delivery.values()),
        "delivery": delivery,
    }


__all__ = [
    "CAMPAIGN_TYPE_ONE_OFF",
    "campaign_analytics",
    "create_campaign",
    "destroy_campaign",
    "fetch_campaign_by_display_id",
    "list_campaigns",
    "update_campaign",
]
