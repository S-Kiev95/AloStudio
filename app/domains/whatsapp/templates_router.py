"""WhatsApp template listing + sync for the campaign composer.

A WhatsApp campaign sends an **approved template** (not free text), so the
composer needs the channel's templates. ``whatsapp.templates.sync_templates``
fetches them from Meta into ``WhatsappChannel.message_templates``; this exposes
them, scoped to a WhatsApp inbox:

  * ``GET  /api/v1/accounts/{id}/inboxes/{inbox_id}/whatsapp/templates``
    — the cached approved templates, each with its body text and the distinct
    ``{{n}}`` positions the composer must collect values for.
  * ``POST /api/v1/accounts/{id}/inboxes/{inbox_id}/whatsapp/templates/sync``
    — refresh from Meta, then return them (the sync isn't wired anywhere else).
"""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WHATSAPP,
    Inbox,
    WhatsappChannel,
)
from app.domains.whatsapp.templates import sync_templates

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/inboxes/{inbox_id}/whatsapp/templates",
    tags=["whatsapp-templates"],
)

_VAR_RE = re.compile(r"\{\{\s*(\d+)\s*\}\}")


def _body_text(tpl: dict[str, Any]) -> str | None:
    for comp in tpl.get("components") or []:
        if (
            isinstance(comp, dict)
            and str(comp.get("type", "")).upper() == "BODY"
        ):
            text = comp.get("text")
            return str(text) if text else None
    return None


def _present(tpl: dict[str, Any]) -> dict[str, Any]:
    """The subset the composer needs. ``variables`` is the sorted, distinct
    ``{{n}}`` positions in the body — one input each."""
    body = _body_text(tpl)
    variables = sorted({int(m) for m in _VAR_RE.findall(body or "")})
    return {
        "name": tpl.get("name"),
        "language": tpl.get("language"),
        "status": tpl.get("status"),
        "category": tpl.get("category"),
        "body_text": body,
        "variables": variables,
    }


def _approved(channel: WhatsappChannel) -> list[dict[str, Any]]:
    return [
        _present(t)
        for t in channel.message_templates or []
        if isinstance(t, dict)
        and str(t.get("status", "")).upper() == "APPROVED"
    ]


async def _whatsapp_channel(
    session: AsyncSession, *, account_id: int, inbox_id: int
) -> WhatsappChannel:
    inbox = await session.get(Inbox, inbox_id)
    if inbox is None or inbox.account_id != account_id:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    if inbox.channel_type != CHANNEL_TYPE_WHATSAPP:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "inbox is not a WhatsApp channel"},
        )
    channel = await session.get(WhatsappChannel, inbox.channel_id)
    if channel is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "whatsapp channel row not found"},
        )
    return channel


@router.get("")
async def list_templates(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Approved templates cached on the channel."""
    assert ctx.account.id is not None
    channel = await _whatsapp_channel(
        session, account_id=ctx.account.id, inbox_id=inbox_id
    )
    return {
        "templates": _approved(channel),
        "last_updated": (
            int(channel.message_templates_last_updated.timestamp())
            if channel.message_templates_last_updated
            else None
        ),
    }


@router.post("/sync")
async def sync_templates_endpoint(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Refresh the cached templates from Meta, then return the approved set."""
    assert ctx.account.id is not None
    channel = await _whatsapp_channel(
        session, account_id=ctx.account.id, inbox_id=inbox_id
    )
    await sync_templates(session, channel=channel)
    return {"templates": _approved(channel)}


__all__ = ["router"]
