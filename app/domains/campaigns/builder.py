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

One-off campaigns (``reuse_existing``) are mass sends to contacts that
usually already talked to the business: the message goes into the
contact's latest conversation, and the guard is "this campaign already
messaged this contact" instead. ``{nombre}`` / ``{primer_nombre}`` in the
message and the template variables become the contact's name.
"""

from __future__ import annotations

import copy
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.campaigns.models import Campaign
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.conversations.models import Conversation, Message


async def build_campaign_conversation(
    session: AsyncSession,
    *,
    campaign: Campaign,
    contact_inbox: ContactInbox,
    additional_attributes: dict[str, Any] | None = None,
    custom_attributes: dict[str, Any] | None = None,
    reuse_existing: bool = False,
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
            select(Conversation)
            .where(Conversation.contact_inbox_id == contact_inbox.id)
            .order_by(Conversation.id.desc())  # type: ignore[union-attr]
        )
    ).first()
    if existing is not None and not reuse_existing:
        return None
    if existing is not None and await _already_sent(session, campaign, contact_inbox):
        return None

    if existing is not None:
        conv = existing
    else:
        # create_conversation reads contact_inbox.inbox — load it in the
        # async context first to avoid a sync lazy-load (MissingGreenlet).
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
    contact = await session.get(Contact, contact_inbox.contact_id)
    names = _names(contact)
    await create_message(
        session,
        conversation=conv,
        params=MessageBuilderParams(
            content=_fill(campaign.message, names),
            message_type="outgoing",
            campaign_id=campaign.id,
            # WhatsApp campaigns carry a template — the outbound sender
            # (``_maybe_send_outbound_whatsapp``) turns these into a template
            # send instead of free-form text.
            template_params=_fill_params(campaign.template_params, names),
        ),
        user_id=campaign.sender_id,
    )
    return conv


async def _already_sent(
    session: AsyncSession, campaign: Campaign, contact_inbox: ContactInbox
) -> bool:
    row = (
        await session.exec(
            select(Message.id)
            .join(Conversation, Conversation.id == Message.conversation_id)  # type: ignore[arg-type]
            .where(
                Conversation.contact_inbox_id == contact_inbox.id,
                Message.additional_attributes["campaign_id"].astext  # type: ignore[index]
                == str(campaign.id),
            )
            .limit(1)
        )
    ).first()
    return row is not None


def _names(contact: Contact | None) -> dict[str, str]:
    full = (contact.name or "").strip() if contact is not None else ""
    return {"{nombre}": full, "{primer_nombre}": full.split(" ")[0] if full else ""}


def _fill(text: str | None, names: dict[str, str]) -> str | None:
    if not text:
        return text
    for token, value in names.items():
        text = text.replace(token, value)
    return text


def _fill_params(
    params: dict[str, Any] | None, names: dict[str, str]
) -> dict[str, Any] | None:
    """Personalize the template variables (``processed_params``) per contact."""
    if not params:
        return params
    out = copy.deepcopy(params)
    processed = out.get("processed_params")
    if isinstance(processed, dict):
        for section in processed.values():
            if isinstance(section, dict):
                for key, value in section.items():
                    if isinstance(value, str):
                        section[key] = _fill(value, names)
    return out


__all__ = ["build_campaign_conversation"]
