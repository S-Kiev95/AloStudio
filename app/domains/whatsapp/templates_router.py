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

Management (F5, admin only): ``GET ?status=all`` lists every template with
its state and rejection reason; ``POST ""`` submits a new one to Meta;
``POST /{template_id}`` edits one; ``DELETE /{template_id}?name=`` deletes it.
"""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context, require_admin
from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WHATSAPP,
    Inbox,
    WhatsappChannel,
)
from app.domains.whatsapp.templates import (
    create_template,
    delete_template,
    edit_template,
    sync_templates,
)

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


def _present_full(tpl: dict[str, Any]) -> dict[str, Any]:
    """Everything the management screen shows: state, why Meta rejected it,
    and the components to edit and preview."""
    return {
        **_present(tpl),
        "id": tpl.get("id"),
        "rejected_reason": tpl.get("rejected_reason"),
        "quality_score": tpl.get("quality_score"),
        "components": tpl.get("components") or [],
    }


class TemplateBody(BaseModel):
    """A template as Meta takes it: ``components`` is Meta's own list
    (HEADER, BODY, FOOTER, BUTTONS), with ``example`` values for variables."""

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    category: str | None = None
    language: str | None = None
    components: list[dict[str, Any]] | None = None


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
    status: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """Approved templates cached on the channel; ``status=all`` returns every
    one with its state, rejection reason and components."""
    assert ctx.account.id is not None
    channel = await _whatsapp_channel(
        session, account_id=ctx.account.id, inbox_id=inbox_id
    )
    templates = (
        [_present_full(t) for t in channel.message_templates or [] if isinstance(t, dict)]
        if status == "all"
        else _approved(channel)
    )
    return {
        "templates": templates,
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


@router.post("")
async def create_template_endpoint(
    inbox_id: Annotated[int, Path()],
    body: TemplateBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Submit a template to Meta for review (it starts as PENDING)."""
    assert ctx.account.id is not None
    channel = await _whatsapp_channel(session, account_id=ctx.account.id, inbox_id=inbox_id)
    result = await create_template(
        session, channel=channel, payload=body.model_dump(exclude_none=True)
    )
    return {"result": result, "templates": _all(channel)}


@router.post("/{template_id}")
async def edit_template_endpoint(
    inbox_id: Annotated[int, Path()],
    template_id: Annotated[str, Path()],
    body: TemplateBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Edit a template's components (and category); Meta reviews it again."""
    assert ctx.account.id is not None
    channel = await _whatsapp_channel(session, account_id=ctx.account.id, inbox_id=inbox_id)
    _require_known(channel, template_id)
    result = await edit_template(
        session,
        channel=channel,
        template_id=template_id,
        payload=body.model_dump(exclude_none=True),
    )
    return {"result": result, "templates": _all(channel)}


@router.delete("/{template_id}")
async def delete_template_endpoint(
    inbox_id: Annotated[int, Path()],
    template_id: Annotated[str, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Delete one template (that language) on Meta."""
    assert ctx.account.id is not None
    channel = await _whatsapp_channel(session, account_id=ctx.account.id, inbox_id=inbox_id)
    name = _require_known(channel, template_id)
    await delete_template(session, channel=channel, name=name, template_id=template_id)
    return {"templates": _all(channel)}


def _all(channel: WhatsappChannel) -> list[dict[str, Any]]:
    return [_present_full(t) for t in channel.message_templates or [] if isinstance(t, dict)]


def _require_known(channel: WhatsappChannel, template_id: str) -> str:
    """The template's name if it belongs to this channel's cache; 404
    otherwise, so an id from another account's WABA can't be targeted."""
    for tpl in channel.message_templates or []:
        if isinstance(tpl, dict) and str(tpl.get("id")) == template_id and tpl.get("name"):
            return str(tpl["name"])
    raise ChatwootHTTPException(
        status_code=404, detail={"error": "Resource could not be found"}
    )


__all__ = ["router"]
