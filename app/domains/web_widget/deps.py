"""FastAPI dependencies for the ``/api/v1/widget/*`` surface.

Resolves the request-scoped ``(WebWidget, Inbox, Contact, ContactInbox)``
tuple that every widget endpoint needs, mirroring Rails'
``Api::V1::Widget::BaseController#set_web_widget`` + ``set_contact``
before-actions.

Auth model:
  * ``website_token`` query string identifies the WebWidget channel.
  * ``X-Auth-Token`` header is a JWT signed by
    :mod:`app.core.widget_token` — payload ``{source_id, inbox_id}``
    points at the visitor's ContactInbox.
  * Missing / invalid token is allowed for the bootstrap endpoint
    (``POST /widget/config`` mints a fresh contact + token); other
    endpoints raise 404 when the resolved tuple is incomplete, matching
    Rails' ``ActiveRecord::RecordNotFound`` behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.core.widget_token import decode_widget_token
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WEB_WIDGET,
    Inbox,
    WebWidget,
)


@dataclass(slots=True)
class WidgetContext:
    """Request-scoped widget resolution.

    ``contact`` / ``contact_inbox`` are ``None`` when the request hits
    the bootstrap endpoint without a valid token — the caller decides
    whether to mint fresh ones (``POST /widget/config``) or 404
    (``GET /widget/contact``, etc).
    """

    web_widget: WebWidget
    inbox: Inbox
    contact: Contact | None
    contact_inbox: ContactInbox | None


async def _resolve_web_widget(
    session: AsyncSession, *, website_token: str
) -> tuple[WebWidget, Inbox]:
    if not website_token:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "web widget does not exist"},
        )
    web_widget = (
        await session.exec(
            select(WebWidget).where(WebWidget.website_token == website_token)
        )
    ).first()
    if web_widget is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "web widget does not exist"},
        )
    inbox = (
        await session.exec(
            select(Inbox).where(
                Inbox.channel_type == CHANNEL_TYPE_WEB_WIDGET,
                Inbox.channel_id == web_widget.id,
            )
        )
    ).first()
    if inbox is None:
        # Defensive — Rails relies on the inverse association, which
        # would surface as ``NoMethodError on nil`` if missing. We
        # collapse to the same 404 shape.
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "web widget does not exist"},
        )
    return web_widget, inbox


async def _resolve_contact(
    session: AsyncSession, *, inbox_id: int, x_auth_token: str | None
) -> tuple[Contact | None, ContactInbox | None]:
    """Decode ``X-Auth-Token`` to ``{source_id, inbox_id}`` and look up
    the ContactInbox + Contact.

    Mirrors ``set_contact`` in WebsiteTokenHelper. A token whose
    ``inbox_id`` doesn't match the resolved widget yields ``(None,
    None)`` — Rails uses the inbox-scoped ``find_by`` so the lookup
    silently fails the same way.
    """
    payload = decode_widget_token(x_auth_token)
    source_id = payload.get("source_id")
    token_inbox_id = payload.get("inbox_id")
    if not source_id or token_inbox_id != inbox_id:
        return None, None
    contact_inbox = (
        await session.exec(
            select(ContactInbox).where(
                ContactInbox.inbox_id == inbox_id,
                ContactInbox.source_id == source_id,
            )
        )
    ).first()
    if contact_inbox is None:
        return None, None
    contact = await session.get(Contact, contact_inbox.contact_id)
    return contact, contact_inbox


async def widget_context(
    website_token: Annotated[str, Query(...)],
    x_auth_token: Annotated[str | None, Header(alias="X-Auth-Token")] = None,
    session: AsyncSession = Depends(get_session),
) -> WidgetContext:
    """Build the widget context. Allows missing token (bootstrap path).

    Raises 404 only for an unknown ``website_token``. The caller is
    responsible for treating ``contact is None`` as either a bootstrap
    cue (``/widget/config``) or a 404 (every other endpoint).
    """
    web_widget, inbox = await _resolve_web_widget(
        session, website_token=website_token
    )
    contact, contact_inbox = await _resolve_contact(
        session, inbox_id=inbox.id, x_auth_token=x_auth_token  # type: ignore[arg-type]
    )
    return WidgetContext(
        web_widget=web_widget,
        inbox=inbox,
        contact=contact,
        contact_inbox=contact_inbox,
    )


async def widget_context_required(
    ctx: Annotated[WidgetContext, Depends(widget_context)],
) -> WidgetContext:
    """Same as :func:`widget_context` but raises 404 if the contact
    couldn't be resolved.

    Used by every widget endpoint EXCEPT the bootstrap (config /
    set_user) — those mint a contact when the token is missing.
    """
    if ctx.contact is None or ctx.contact_inbox is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return ctx


__all__ = [
    "WidgetContext",
    "widget_context",
    "widget_context_required",
]
