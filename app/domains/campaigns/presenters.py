"""Wire-shape presenter for Campaign."""

from __future__ import annotations

from typing import Any

from app.domains.campaigns.models import (
    Campaign,
    campaign_status_to_str,
    campaign_type_to_str,
)


def present_campaign(campaign: Campaign) -> dict[str, Any]:
    return {
        "id": campaign.display_id,
        "display_id": campaign.display_id,
        "title": campaign.title,
        "description": campaign.description,
        "message": campaign.message,
        "sender_id": campaign.sender_id,
        "enabled": campaign.enabled,
        "account_id": campaign.account_id,
        "inbox_id": campaign.inbox_id,
        "trigger_rules": campaign.trigger_rules or {},
        "campaign_type": campaign_type_to_str(campaign.campaign_type),
        "campaign_status": campaign_status_to_str(campaign.campaign_status),
        "audience": list(campaign.audience or []),
        "scheduled_at": (
            campaign.scheduled_at.isoformat()
            if campaign.scheduled_at
            else None
        ),
        "trigger_only_during_business_hours": campaign.trigger_only_during_business_hours,
        "template_params": campaign.template_params,
        "created_at": (
            int(campaign.created_at.timestamp())
            if campaign.created_at
            else None
        ),
    }


__all__ = ["present_campaign"]
