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

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.errors import ChatwootHTTPException
from app.core.widget_token import encode_widget_token
from app.domains.campaigns.builder import build_campaign_conversation
from app.domains.campaigns.models import CAMPAIGN_TYPE_ONGOING, Campaign
from app.domains.contacts.models import Contact
from app.domains.contacts.service import ContactIdentifyAction
from app.domains.conversations.events import (
    CONVERSATION_TYPING_OFF,
    CONVERSATION_TYPING_ON,
    dispatcher,
)
from app.domains.conversations.models import (
    CONVERSATION_STATUS_RESOLVED,
    Conversation,
    Message,
)
from app.domains.conversations.presenters import (
    present_conversation,
    present_message,
    present_messages_index,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    _AttachmentSpec,
    create_conversation,
    create_message,
)
from app.domains.uploads.service import presign_upload
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


# ===========================================================================
# Conversations + messages (5a.3)
# ===========================================================================
async def _last_conversation_for(
    session: AsyncSession, ctx: WidgetContext
) -> Conversation | None:
    """Mirror ``Api::V1::Widget::BaseController#conversation``.

    Picks the most recent conversation linked to either the
    contact_inbox (when not HMAC-verified) or any verified
    contact_inbox of the same contact (when HMAC-verified). The
    HMAC-verified branch matters for cross-device session resume.
    """
    assert ctx.contact_inbox is not None
    assert ctx.inbox.id is not None
    if ctx.contact_inbox.hmac_verified:
        # All verified contact_inboxes for this contact + inbox.
        from app.domains.contacts.models import ContactInbox as _CI

        verified_ids_stmt = select(_CI.id).where(
            _CI.contact_id == ctx.contact_inbox.contact_id,
            _CI.inbox_id == ctx.inbox.id,
            _CI.hmac_verified.is_(True),  # type: ignore[union-attr]
        )
        stmt = (
            select(Conversation)
            .where(Conversation.contact_inbox_id.in_(verified_ids_stmt))  # type: ignore[attr-defined]
            .order_by(Conversation.id.desc())  # type: ignore[attr-defined]
            .limit(1)
        )
    else:
        stmt = (
            select(Conversation)
            .where(
                Conversation.contact_inbox_id == ctx.contact_inbox.id,
                Conversation.inbox_id == ctx.inbox.id,
            )
            .order_by(Conversation.id.desc())  # type: ignore[attr-defined]
            .limit(1)
        )
    return (await session.exec(stmt)).first()


@router.get("/conversations")
async def widget_conversation_index(
    ctx: Annotated[WidgetContext, Depends(widget_context_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any] | None:
    """Mirror ``Api::V1::Widget::ConversationsController#index``.

    Returns the most recent conversation in the verified set (or null
    when the visitor has none). The Rails action sets ``@conversation``
    + renders the partial, which produces ``null`` when nil.
    """
    conv = await _last_conversation_for(session, ctx)
    if conv is None:
        return None
    return present_conversation(conv)


@router.get("/messages")
async def widget_messages_index(
    ctx: Annotated[WidgetContext, Depends(widget_context_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
    before: int | None = Query(None, description="Message id cursor"),
) -> dict[str, Any]:
    """Mirror ``Api::V1::Widget::MessagesController#index``.

    Filters internal (private) messages — the widget never shows them.
    Returns ``[]`` when the visitor has no conversation yet (Rails
    short-circuits with ``conversation.nil? ? [] : ...``).
    """
    conv = await _last_conversation_for(session, ctx)
    if conv is None:
        return {"meta": {}, "payload": []}

    stmt = select(Message).where(
        Message.conversation_id == conv.id,
        Message.private.is_(False),  # type: ignore[union-attr]
    )
    if before is not None:
        stmt = stmt.where(Message.id < before)  # type: ignore[operator]
    stmt = stmt.order_by(Message.id.desc()).limit(20)  # type: ignore[attr-defined]
    rows = list((await session.exec(stmt)).all())
    rows.reverse()  # oldest first, matches MessageFinder
    return present_messages_index(rows, conversation=conv)


@router.post("/messages")
async def widget_messages_create(
    payload: dict[str, Any],
    ctx: Annotated[WidgetContext, Depends(widget_context_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Mirror ``Api::V1::Widget::MessagesController#create``.

    Auto-creates a Conversation (via ConversationBuilder) when the
    visitor has none yet, then writes the incoming message. The reply
    is the message push-event shape used elsewhere.

    Permitted payload (Rails):
      ``{message: {content, referer_url, timestamp, echo_id, reply_to},
         contact: {name, email}, custom_attributes: {}, labels: []}``
    """
    assert ctx.contact is not None and ctx.contact_inbox is not None

    msg_in = payload.get("message") or {}
    if not isinstance(msg_in, dict):
        raise ChatwootHTTPException(
            status_code=422, detail={"message": "message: invalid payload"}
        )

    content = msg_in.get("content")
    echo_id = msg_in.get("echo_id")
    referer = msg_in.get("referer_url")
    reply_to = msg_in.get("reply_to")

    conv = await _last_conversation_for(session, ctx)
    if conv is None:
        # Mirror ``set_conversation`` -> ``create_conversation`` —
        # wraps additional_attributes + custom_attributes + initial labels.
        additional: dict[str, Any] = {}
        if referer:
            additional["referer"] = referer
        custom = (
            payload.get("custom_attributes")
            if isinstance(payload.get("custom_attributes"), dict)
            else {}
        )
        conv = await create_conversation(
            session,
            contact_inbox=ctx.contact_inbox,
            params=ConversationBuilderParams(
                additional_attributes=additional or None,
                custom_attributes=custom or None,
            ),
        )

    content_attrs: dict[str, Any] = {}
    if reply_to is not None:
        content_attrs["in_reply_to"] = reply_to

    # URL-metadata attachments the visitor uploaded via ``/widget/uploads``.
    raw_atts = msg_in.get("attachments")
    specs: list[_AttachmentSpec] | None = None
    if isinstance(raw_atts, list):
        built = [
            _AttachmentSpec(
                file_type=a.get("file_type", "file") or "file",
                external_url=a.get("external_url"),
            )
            for a in raw_atts
            if isinstance(a, dict) and a.get("external_url")
        ]
        specs = built or None

    # ``create_message`` expects ``user_id`` for outgoing — for the
    # widget the sender is the contact, so we pass ``user_id=None`` and
    # message_type=incoming. ``_resolve_sender`` handles the contact
    # branch automatically.
    msg = await create_message(
        session,
        conversation=conv,
        params=MessageBuilderParams(
            content=content,
            message_type="incoming",
            content_attributes=content_attrs or None,
            echo_id=echo_id,
            attachments=specs,
        ),
        user_id=None,
    )
    return present_message(msg, echo_id=echo_id)


@router.post("/uploads")
async def widget_upload(
    payload: dict[str, Any],
    ctx: Annotated[WidgetContext, Depends(widget_context_required)],
) -> dict[str, Any]:
    """Pre-signed direct-upload URL for a widget visitor's attachment.

    Gated on the widget's ``attachments`` feature flag (Rails:
    ``head :forbidden unless @web_widget.attachments?``). The key is
    namespaced under the widget's account, identical to the dashboard
    surface — the agent then sees the file via the signed-read presenter.
    """
    if not ctx.web_widget.attachments:
        raise ChatwootHTTPException(
            status_code=403,
            detail={"error": "Attachments are not enabled for this widget"},
        )
    assert ctx.inbox.account_id is not None
    filename = payload.get("filename") if isinstance(payload, dict) else None
    return presign_upload(ctx.inbox.account_id, filename)


@router.post("/conversations/update_last_seen")
async def widget_update_last_seen(
    ctx: Annotated[WidgetContext, Depends(widget_context_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Mirror ``Api::V1::Widget::ConversationsController#update_last_seen``."""
    conv = await _last_conversation_for(session, ctx)
    if conv is None:
        return {"status": "ok"}
    conv.contact_last_seen_at = datetime.now(UTC)
    session.add(conv)
    await session.flush()
    return {"status": "ok"}


@router.post("/conversations/toggle_typing")
async def widget_toggle_typing(
    payload: dict[str, Any],
    ctx: Annotated[WidgetContext, Depends(widget_context_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Mirror ``Api::V1::Widget::ConversationsController#toggle_typing``."""
    conv = await _last_conversation_for(session, ctx)
    if conv is None:
        return {"status": "ok"}

    typing_status = payload.get("typing_status")
    if typing_status == "on":
        await dispatcher.dispatch(
            session,
            CONVERSATION_TYPING_ON,
            conversation=conv,
            user=ctx.contact,
        )
    elif typing_status == "off":
        await dispatcher.dispatch(
            session,
            CONVERSATION_TYPING_OFF,
            conversation=conv,
            user=ctx.contact,
        )
    return {"status": "ok"}


@router.post("/conversations/toggle_status")
async def widget_toggle_status(
    ctx: Annotated[WidgetContext, Depends(widget_context_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Mirror ``Api::V1::Widget::ConversationsController#toggle_status``.

    403 when the widget has ``end_conversation`` disabled (Rails:
    ``return head :forbidden unless @web_widget.end_conversation?``).
    Resolves the conversation otherwise.
    """
    if not ctx.web_widget.end_conversation:
        raise ChatwootHTTPException(
            status_code=403,
            detail={"error": "End conversation is not enabled for this widget"},
        )
    conv = await _last_conversation_for(session, ctx)
    if conv is None:
        return {"status": "ok"}
    if conv.status != CONVERSATION_STATUS_RESOLVED:
        conv.status = CONVERSATION_STATUS_RESOLVED
        session.add(conv)
        await session.flush()
    return {"status": "ok"}


# ===========================================================================
# Campaigns (ongoing) — list + trigger
# ===========================================================================
def _present_widget_campaign(campaign: Campaign) -> dict[str, Any]:
    """Mirror ``api/v1/widget/campaigns/index.json.jbuilder``."""
    return {
        "id": campaign.display_id,
        "trigger_rules": campaign.trigger_rules or {},
        "trigger_only_during_business_hours": (
            campaign.trigger_only_during_business_hours
        ),
        "message": campaign.message,
        # sender.push_event_data — deferred; the SDK tolerates a null sender.
        "sender": None,
    }


@router.get("/campaigns")
async def widget_campaigns_index(
    ctx: Annotated[WidgetContext, Depends(widget_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    """Mirror ``Api::V1::Widget::CampaignsController#index`` — the enabled
    ongoing campaigns on this widget's inbox. The SDK evaluates each
    campaign's ``trigger_rules`` client-side and posts a
    ``campaign.triggered`` event back when one matches."""
    rows = list(
        (
            await session.exec(
                select(Campaign).where(
                    Campaign.inbox_id == ctx.inbox.id,
                    Campaign.campaign_type == CAMPAIGN_TYPE_ONGOING,
                    Campaign.enabled.is_(True),  # type: ignore[union-attr]
                )
            )
        ).all()
    )
    return [_present_widget_campaign(c) for c in rows]


@router.post("/events")
async def widget_events(
    payload: dict[str, Any],
    ctx: Annotated[WidgetContext, Depends(widget_context_required)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Mirror ``Api::V1::Widget::EventsController#create`` — the widget's
    generic event bus. Today only ``campaign.triggered`` is handled: it
    runs the campaign conversation builder for the visitor's ContactInbox
    (ports ``CampaignListener#campaign_triggered``)."""
    if payload.get("name") == "campaign.triggered":
        await _on_campaign_triggered(
            session, ctx, payload.get("event_info") or {}
        )
    return {"status": "ok"}


async def _on_campaign_triggered(
    session: AsyncSession, ctx: WidgetContext, event_info: dict[str, Any]
) -> None:
    """Port of ``CampaignListener#campaign_triggered`` — resolve the
    ongoing campaign by display id (scoped to the widget's inbox) and run
    the builder for the visitor's ContactInbox."""
    if ctx.contact_inbox is None:
        return
    raw_id = event_info.get("campaign_id")
    try:
        display_id = int(raw_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return
    campaign = (
        await session.exec(
            select(Campaign).where(
                Campaign.inbox_id == ctx.inbox.id,
                Campaign.display_id == display_id,
                Campaign.campaign_type == CAMPAIGN_TYPE_ONGOING,
                Campaign.enabled.is_(True),  # type: ignore[union-attr]
            )
        )
    ).first()
    if campaign is None:
        return
    additional = {
        k: v
        for k, v in event_info.items()
        if k not in ("campaign_id", "custom_attributes")
    }
    custom = event_info.get("custom_attributes")
    await build_campaign_conversation(
        session,
        campaign=campaign,
        contact_inbox=ctx.contact_inbox,
        additional_attributes=additional or None,
        custom_attributes=custom if isinstance(custom, dict) else None,
    )


__all__ = ["router"]
