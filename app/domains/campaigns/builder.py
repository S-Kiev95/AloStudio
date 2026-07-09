"""Campaign → conversation builder.

Ports ``reference/chatwoot/app/builders/campaigns/campaign_conversation_builder.rb``.

Shared by both campaign trigger paths:
  * ``one_off`` — the scheduler fires it per audience contact
    (:mod:`app.workers.scheduler`).
  * ``ongoing`` — the widget fires it on a ``campaign.triggered`` event
    (:mod:`app.domains.web_widget.router`).

Given a resolved ContactInbox + Campaign, create a conversation stamped
with ``campaign_id`` plus an outgoing message carrying the campaign body.
Idempotent: returns ``None`` when the ContactInbox already has a
conversation, so a re-trigger never double-sends (mirrors the builder's
``raise 'Conversation already present'`` guard).
"""

from __future__ import annotations

from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.campaigns.models import Campaign
from app.domains.contacts.models import ContactInbox
from app.domains.conversations.models import Conversation


async def build_campaign_conversation(
    session: AsyncSession,
    *,
    campaign: Campaign,
    contact_inbox: ContactInbox,
    additional_attributes: dict[str, Any] | None = None,
    custom_attributes: dict[str, Any] | None = None,
) -> Conversation | None:
    """Create the campaign conversation + outgoing message for
    ``contact_inbox``, or return ``None`` when one already exists."""
    from app.domains.conversations.service import (
        ConversationBuilderParams,
        MessageBuilderParams,
        create_conversation,
        create_message,
    )

    existing = (
        await session.exec(
            select(Conversation).where(
                Conversation.contact_inbox_id == contact_inbox.id
            )
        )
    ).first()
    if existing is not None:
        return None

    # create_conversation reads contact_inbox.inbox — load it in the async
    # context first to avoid a sync lazy-load (MissingGreenlet).
    await session.refresh(contact_inbox, ["inbox"])
    conv = await create_conversation(
        session,
        contact_inbox=contact_inbox,
        params=ConversationBuilderParams(
            additional_attributes=additional_attributes,
            custom_attributes=custom_attributes,
        ),
    )
    conv.campaign_id = campaign.id
    session.add(conv)
    await session.flush()
    await create_message(
        session,
        conversation=conv,
        params=MessageBuilderParams(
            content=campaign.message,
            message_type="outgoing",
            campaign_id=campaign.id,
            # WhatsApp campaigns carry a template — the outbound sender
            # (``_maybe_send_outbound_whatsapp``) turns these into a template
            # send instead of free-form text.
            template_params=campaign.template_params,
        ),
        user_id=campaign.sender_id,
    )
    return conv


__all__ = ["build_campaign_conversation"]
