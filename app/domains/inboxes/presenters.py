"""Inbox response shaping — ports ``_inbox.json.jbuilder``.

Chatwoot emits a union-of-all-channels shape per row, with channel-specific
keys gated by ``resource.api?`` / ``resource.email?`` / … — and admin-only
keys (``hmac_token``, ``secret``) gated by
``Current.account_user&.administrator?``.

Phase 2 surfaces only the ``Channel::Api`` subset. Other channels will
grow conditionals in :func:`present_inbox`. Parity with Chatwoot is
maintained by always emitting the same *base* keys — including common
fields with ``None`` values — because the Rails jbuilder writes
``json.key nil`` as ``"key": null`` on the wire, not omission.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.domains.inboxes.models import (
    CHANNEL_TYPE_API,
    CHANNEL_TYPE_EMAIL,
    CHANNEL_TYPE_SMS,
    CHANNEL_TYPE_TELEGRAM,
    CHANNEL_TYPE_TWILIO_SMS,
    CHANNEL_TYPE_WHATSAPP,
    ApiChannel,
    Inbox,
    sender_name_type_to_str,
)


def _avatar_url(_inbox: Inbox) -> str:
    """Same policy as the User presenter — Phase 2 has no real avatar
    pipeline yet; we emit the empty string so the key is present but
    opaque, matching ``try(:avatar_url)`` on an inbox with no attachment.
    """
    return ""


def _callback_webhook_url(inbox: Inbox, channel: Any) -> str | None:
    """The public URL the provider posts inbound events to — what the user
    pastes into Meta / Bandwidth / Twilio when wiring the channel up.

    Mirrors Chatwoot's ``Inbox#callback_webhook_url`` (Twilio / SMS / WhatsApp);
    we also surface Telegram, whose webhook carries the bot token in the path.
    Built off ``settings.app_base_url`` (Chatwoot's ``FRONTEND_URL``).
    """
    if channel is None:
        return None
    base = get_settings().app_base_url.rstrip("/")
    ct = inbox.channel_type
    if ct == CHANNEL_TYPE_TWILIO_SMS:
        return f"{base}/twilio/callback"
    if ct == CHANNEL_TYPE_SMS:
        phone = (getattr(channel, "phone_number", "") or "").lstrip("+")
        return f"{base}/webhooks/sms/{phone}"
    if ct == CHANNEL_TYPE_WHATSAPP:
        return f"{base}/webhooks/whatsapp/{getattr(channel, 'phone_number', '') or ''}"
    if ct == CHANNEL_TYPE_TELEGRAM:
        return f"{base}/webhooks/telegram/{getattr(channel, 'bot_token', '') or ''}"
    return None


def present_inbox(
    inbox: Inbox,
    *,
    channel: Any | None,
    is_administrator: bool,
) -> dict[str, Any]:
    """Emit the inbox row in Chatwoot wire shape.

    ``channel`` is the resolved concrete channel (Channel::Api for Phase 2)
    or ``None`` if the lookup hasn't happened — the caller typically
    resolves it once per request. Keeping it as an argument (instead of
    re-fetching here) avoids N+1 on the index endpoint.

    ``is_administrator`` gates admin-only keys
    (``hmac_token`` / ``secret`` for Channel::Api, ``hmac_token`` for
    web-widget, SMTP/IMAP for email, etc.). Wire parity with Chatwoot's
    ``Current.account_user&.administrator?`` check.
    """
    body: dict[str, Any] = {
        "id": inbox.id,
        "avatar_url": _avatar_url(inbox),
        "channel_id": inbox.channel_id,
        "name": inbox.name,
        "channel_type": inbox.channel_type,
        "greeting_enabled": inbox.greeting_enabled,
        "greeting_message": inbox.greeting_message,
        "working_hours_enabled": inbox.working_hours_enabled,
        "enable_email_collect": inbox.enable_email_collect,
        "csat_survey_enabled": inbox.csat_survey_enabled,
        "csat_config": inbox.csat_config or {},
        "enable_auto_assignment": inbox.enable_auto_assignment,
        "auto_assignment_config": inbox.auto_assignment_config or {},
        "out_of_office_message": inbox.out_of_office_message,
        # ``working_hours`` is Rails' ``resource.weekly_schedule`` — empty
        # list until the working_hours table lands (Phase 6+).
        "working_hours": [],
        "timezone": inbox.timezone,
        "callback_webhook_url": _callback_webhook_url(inbox, channel),
        "allow_messages_after_resolved": inbox.allow_messages_after_resolved,
        "lock_to_single_conversation": inbox.lock_to_single_conversation,
        # ``sender_name_type`` wire shape is the *string*, not the int enum
        # value — jbuilder serialises Rails enums by string key.
        "sender_name_type": sender_name_type_to_str(inbox.sender_name_type),
        "business_name": inbox.business_name,
    }

    # Common "might-apply" keys the jbuilder emits unconditionally via
    # ``resource.channel.try(...)``. For Channel::Api these are all nil,
    # but Chatwoot still writes the keys, so we do too.
    body.update(
        {
            "tweets_enabled": None,
            "allowed_domains": None,
            "widget_color": None,
            "website_url": None,
            "hmac_mandatory": getattr(channel, "hmac_mandatory", None),
            "welcome_title": None,
            "welcome_tagline": None,
            "web_widget_script": None,
            "website_token": None,
            "selected_feature_flags": None,
            "reply_time": None,
            "messaging_service_sid": None,
            "phone_number": getattr(channel, "phone_number", None),
            "provider": getattr(channel, "provider", None),
        }
    )

    # Channel::Api-specific block
    if inbox.channel_type == CHANNEL_TYPE_API and channel is not None:
        body["webhook_url"] = channel.webhook_url
        body["inbox_identifier"] = channel.identifier
        body["additional_attributes"] = channel.additional_attributes or {}
        if is_administrator:
            body["hmac_token"] = channel.hmac_token
            body["secret"] = channel.secret

    # Channel::Email branding, so the settings screen can render what the
    # mailbox currently signs with. Not admin-gated: it is what customers
    # already receive at the bottom of every reply, unlike the SMTP
    # credentials on the same row, which are never presented.
    if inbox.channel_type == CHANNEL_TYPE_EMAIL and channel is not None:
        body["email"] = getattr(channel, "email", None)
        body["signature"] = getattr(channel, "signature", "") or ""
        body["logo_url"] = getattr(channel, "logo_url", "") or ""
        if is_administrator:
            # Everything the transport form needs to render, except the
            # passwords: those go out to a mail server, never back to a
            # browser. The two booleans say whether one is stored, which
            # is what lets the form show "already set" instead of an empty
            # box that looks unconfigured.
            body.update(
                {
                    "imap_enabled": bool(getattr(channel, "imap_enabled", False)),
                    "imap_address": getattr(channel, "imap_address", "") or "",
                    "imap_port": getattr(channel, "imap_port", 0) or 0,
                    "imap_login": getattr(channel, "imap_login", "") or "",
                    "imap_enable_ssl": bool(
                        getattr(channel, "imap_enable_ssl", True)
                    ),
                    "imap_password_set": bool(
                        getattr(channel, "imap_password", "")
                    ),
                    "smtp_enabled": bool(getattr(channel, "smtp_enabled", False)),
                    "smtp_address": getattr(channel, "smtp_address", "") or "",
                    "smtp_port": getattr(channel, "smtp_port", 0) or 0,
                    "smtp_login": getattr(channel, "smtp_login", "") or "",
                    "smtp_enable_ssl_tls": bool(
                        getattr(channel, "smtp_enable_ssl_tls", False)
                    ),
                    "smtp_enable_starttls_auto": bool(
                        getattr(channel, "smtp_enable_starttls_auto", True)
                    ),
                    "smtp_password_set": bool(
                        getattr(channel, "smtp_password", "")
                    ),
                }
            )

    # WhatsApp's verify token — the value the user enters in Meta's webhook
    # config. Admin-only, like the Api hmac_token / secret.
    if is_administrator:
        verify_token = getattr(channel, "webhook_verify_token", None)
        if verify_token:
            body["webhook_verify_token"] = verify_token

    return body


def present_inboxes_index(
    rows: list[tuple[Inbox, ApiChannel | None]],
    *,
    is_administrator: bool,
) -> dict[str, Any]:
    """Chatwoot's ``inboxes/index.json.jbuilder`` wraps the array in
    ``{"payload": [...]}`` — we match that envelope.

    ``rows`` is a pre-joined list of ``(inbox, channel-or-None)`` tuples
    so the caller can batch the channel fetches.
    """
    return {
        "payload": [
            present_inbox(inbox, channel=channel, is_administrator=is_administrator)
            for (inbox, channel) in rows
        ]
    }


# ---------------------------------------------------------------------------
# Agent (reused for inbox_members payload) — a minimal copy of Chatwoot's
# ``_agent.json.jbuilder``. Lives here (not in users.presenters) to avoid
# pulling the inbox module into unrelated users flows.
# ---------------------------------------------------------------------------
def present_agent(
    *,
    account_id: int,
    account_user_availability: int | None,
    account_user_auto_offline: bool | None,
    user: Any,  # app.domains.users.models.User — Any to sidestep import cycle
) -> dict[str, Any]:
    """Shape of one element in ``inbox_members`` / ``team_members`` payloads.

    Mirrors ``_agent.json.jbuilder`` exactly except for the Enterprise-only
    ``custom_role_id`` (deferred to Phase 9).
    """
    from app.domains.users.models import _AVAIL_INT_TO_STR  # local to avoid cycle

    body: dict[str, Any] = {
        "id": user.id,
        "account_id": account_id,
        "availability_status": _AVAIL_INT_TO_STR.get(
            account_user_availability or 1, "offline"
        ),
        "auto_offline": account_user_auto_offline if account_user_auto_offline is not None else True,
        "confirmed": user.confirmed_at is not None,
        "email": user.email,
        "provider": user.provider,
        "available_name": user.display_name or user.name,
        "name": user.name,
        "role": _account_user_role_for(user, account_id),
        "thumbnail": getattr(user, "avatar_url", None) or "",
    }
    if user.custom_attributes:
        body["custom_attributes"] = user.custom_attributes
    return body


def _account_user_role_for(user: Any, account_id: int) -> int:
    """Locate the caller's role in ``account_id`` from the prefetched
    ``user.account_users`` relationship.

    We default to the Rails ``agent`` integer (0) on miss — should never
    happen because the outer query scopes to account members, but the
    defensive fallback keeps the presenter total.
    """
    for au in getattr(user, "account_users", []) or []:
        if au.account_id == account_id:
            return au.role
    return 0
