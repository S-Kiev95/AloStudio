"""``/api/v1/widget`` HTTP surface — config + contact endpoints.

Ports the read-only / contact-management half of Chatwoot's widget
controller stack (4b.2 milestone). The conversation + message half
arrives in 5a.3.

Endpoints:
  * ``POST /api/v1/widget/config`` — bootstrap a fresh ContactInbox +
    JWT token for an anonymous visitor. If the request already carries
    an ``X-Auth-Token`` whose source_id resolves, returns the existing
    contact.
  * ``GET  /api/v1/widget/contact`` — return the resolved contact.
  * ``PATCH /api/v1/widget/contact`` — merge-or-update via
    ContactIdentifyAction.
  * ``POST /api/v1/widget/contact/set_user`` — HMAC-validated contact
    identify (the SDK's ``setUser`` flow).

Anchors:
  reference/chatwoot/app/controllers/api/v1/widget/configs_controller.rb
  reference/chatwoot/app/controllers/api/v1/widget/contacts_controller.rb
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Header
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.core.widget_token import encode_widget_token
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactIdentifyAction
from app.domains.web_widget.deps import (
    WidgetContext,
    widget_context,
    widget_context_required,
)
from app.domains.web_widget.service import (
    build_contact_inbox_with_token,
    valid_hmac,
)

router = APIRouter(
    prefix="/api/v1/widget",
    tags=["widget"],
)


# ---------------------------------------------------------------------------
# Presenters — kept inline since the surface is small + widget-specific
# ---------------------------------------------------------------------------
def _present_widget_config(ctx: WidgetContext, *, token: str) -> dict[str, Any]:
    """Mirror ``configs_controller`` jbuilder.

    Chatwoot's view exposes the channel config + the contact + the
    auth token. We ship the subset the widget JS reads on bootstrap.
    """
    ww = ctx.web_widget
    inbox = ctx.inbox
    contact = ctx.contact
    return {
        "auth_token": token,
        "inbox": {
            "id": inbox.id,
            "name": inbox.name,
            "channel_type": inbox.channel_type,
            "website_token": ww.website_token,
            "widget_color": ww.widget_color,
            "welcome_title": ww.welcome_title,
            "welcome_tagline": ww.welcome_tagline,
            "pre_chat_form_enabled": ww.pre_chat_form_enabled,
            "pre_chat_form_options": ww.pre_chat_form_options,
            "feature_flags": {
                "attachments": ww.attachments,
                "emoji_picker": ww.emoji_picker,
                "end_conversation": ww.end_conversation,
                "use_inbox_avatar_for_bot": ww.use_inbox_avatar_for_bot,
                "allow_mobile_webview": ww.allow_mobile_webview,
            },
            "reply_time": ww.reply_time,
        },
        "contact": _present_widget_contact(contact) if contact is not None else None,
    }


def _present_widget_contact(contact: Contact) -> dict[str, Any]:
    """Subset of the Rails ``_contact`` partial the widget reads."""
    return {
        "id": contact.id,
        "name": contact.name,
        "email": contact.email,
        "phone_number": contact.phone_number,
        "identifier": contact.identifier,
        "additional_attributes": contact.additional_attributes or {},
        "custom_attributes": contact.custom_attributes or {},
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/config")
async def widget_config(
    ctx: Annotated[WidgetContext, Depends(widget_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Bootstrap the widget — mint a contact + token if the request
    didn't carry a valid one.

    Mirrors ``Api::V1::Widget::ConfigsController#create``.
    """
    if ctx.contact is not None and ctx.contact_inbox is not None:
        # Re-mint a token so the response always carries a fresh
        # ``auth_token`` field (Chatwoot does the same — the JS SDK
        # rotates the localStorage token on every config call).
        assert ctx.inbox.id is not None
        token = encode_widget_token(
            source_id=ctx.contact_inbox.source_id,
            inbox_id=ctx.inbox.id,
        )
        return _present_widget_config(ctx, token=token)

    sess = await build_contact_inbox_with_token(
        session, web_widget=ctx.web_widget, inbox=ctx.inbox
    )
    new_ctx = WidgetContext(
        web_widget=ctx.web_widget,
        inbox=ctx.inbox,
        contact=sess.contact,
        contact_inbox=sess.contact_inbox,
    )
    return _present_widget_config(new_ctx, token=sess.token)


@router.get("/contact")
async def widget_contact_show(
    ctx: Annotated[WidgetContext, Depends(widget_context_required)],
) -> dict[str, Any]:
    """Mirror ``Api::V1::Widget::ContactsController#show``."""
    assert ctx.contact is not None
    return _present_widget_contact(ctx.contact)


@router.patch("/contact")
async def widget_contact_update(
    payload: dict[str, Any],
    ctx: Annotated[WidgetContext, Depends(widget_context_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Mirror ``Api::V1::Widget::ContactsController#update``.

    Permitted params: ``email``, ``name``, ``avatar_url``,
    ``phone_number``, ``custom_attributes``, ``additional_attributes``.
    No ``identifier`` here — that flows through ``set_user`` so the
    HMAC gate fires.
    """
    assert ctx.contact is not None
    permitted = _permit_contact_update(payload)
    contact = await ContactIdentifyAction(
        session=session,
        contact=ctx.contact,
        params=permitted,
        retain_original_contact_name=True,
    ).perform()
    return _present_widget_contact(contact)


@router.post("/contact/set_user")
async def widget_contact_set_user(
    payload: dict[str, Any],
    ctx: Annotated[WidgetContext, Depends(widget_context_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Mirror ``Api::V1::Widget::ContactsController#set_user``.

    HMAC validation gate (when ``hmac_mandatory`` is on or
    ``identifier_hash`` is supplied), then identify-by-identifier.

    The ``a_different_contact?`` branch (where the new identifier
    points at a different existing contact and we have to spin a fresh
    ContactInbox + token) is implemented inline here — it's the only
    other place in Chatwoot's widget that mints a new token outside
    ``/config``.
    """
    assert ctx.contact is not None and ctx.contact_inbox is not None
    identifier = payload.get("identifier")
    identifier_hash = payload.get("identifier_hash")

    if _should_verify_hmac(ctx, payload):
        if not isinstance(identifier, str) or not isinstance(identifier_hash, str):
            raise ChatwootHTTPException(
                status_code=401,
                detail={"error": "HMAC failed: Invalid Identifier Hash Provided"},
            )
        if not valid_hmac(
            hmac_token=ctx.web_widget.hmac_token,
            identifier=identifier,
            identifier_hash=identifier_hash,
        ):
            raise ChatwootHTTPException(
                status_code=401,
                detail={"error": "HMAC failed: Invalid Identifier Hash Provided"},
            )

    target_contact = ctx.contact
    target_contact_inbox = ctx.contact_inbox

    # Mirror ``a_different_contact?``: existing identifier on the
    # current contact mismatches the incoming one -> fresh ContactInbox.
    if (
        ctx.contact.identifier
        and isinstance(identifier, str)
        and ctx.contact.identifier != identifier
    ):
        sess_pair = await build_contact_inbox_with_token(
            session, web_widget=ctx.web_widget, inbox=ctx.inbox
        )
        target_contact = sess_pair.contact
        target_contact_inbox = sess_pair.contact_inbox

    # ``@contact_inbox.update(hmac_verified: true) if should_verify_hmac?``
    if _should_verify_hmac(ctx, payload):
        target_contact_inbox.hmac_verified = True
        session.add(target_contact_inbox)
        await session.flush()

    permitted = _permit_contact_update(payload)
    if isinstance(identifier, str):
        permitted["identifier"] = identifier
    contact = await ContactIdentifyAction(
        session=session,
        contact=target_contact,
        params=permitted,
    ).perform()
    return _present_widget_contact(contact)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _permit_contact_update(payload: dict[str, Any]) -> dict[str, Any]:
    """Mirror Rails ``params.permit(:email, :name, :avatar_url,
    :phone_number, custom_attributes: {}, additional_attributes: {})``."""
    permitted: dict[str, Any] = {}
    for key in ("email", "name", "avatar_url", "phone_number"):
        if key in payload and payload[key] is not None:
            permitted[key] = payload[key]
    for key in ("custom_attributes", "additional_attributes"):
        val = payload.get(key)
        if isinstance(val, dict) and val:
            permitted[key] = val
    return permitted


def _should_verify_hmac(ctx: WidgetContext, payload: dict[str, Any]) -> bool:
    """Mirror ``ContactsController#should_verify_hmac?``.

    Verify when:
      * ``identifier_hash`` is present in the payload, OR
      * the widget has ``hmac_mandatory`` enabled.

    Skip when ``custom_attributes`` are sent without an identifier
    (Rails' anti-leakage guard).
    """
    if (
        "identifier_hash" not in payload
        and not ctx.web_widget.hmac_mandatory
    ):
        return False
    if (
        payload.get("custom_attributes")
        and not payload.get("identifier")
    ):
        return False
    return True


__all__ = ["router"]
