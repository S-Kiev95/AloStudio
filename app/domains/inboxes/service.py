"""Inbox service layer.

Ports the flow of ``Api::V1::Accounts::InboxesController`` from
``reference/chatwoot/app/controllers/api/v1/accounts/inboxes_controller.rb``
— with the inline channel-creation logic promoted to a real builder
(``InboxBuilder.perform``).

Chatwoot's controller creates channel + inbox inside an
``ActiveRecord::Base.transaction`` block. We preserve the same
atomicity: if either side fails, nothing lands.

Channel scope (Phase 2): only ``Channel::Api``. Other channel types will
grow ``channel_factory`` into a registry of per-type builders. The shape
here accepts that growth naturally — ``_build_channel`` dispatches on
``channel.type`` already.

Agent membership helpers (:func:`add_members` / :func:`remove_members`)
mirror ``Inbox#add_members`` / ``Inbox#remove_members``. The Rails hooks
``InboxRoundRobinService#add_agent_to_queue`` / ``remove_agent_from_queue``
are Phase 5 work; we leave a TODO marker rather than wire a no-op.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.core.tokens import base58_token
from app.domains.accounts.models import Account
from app.domains.inboxes.models import (
    CHANNEL_TYPE_API,
    CHANNEL_TYPE_EMAIL,
    CHANNEL_TYPE_FACEBOOK,
    CHANNEL_TYPE_INSTAGRAM,
    CHANNEL_TYPE_SMS,
    CHANNEL_TYPE_TELEGRAM,
    CHANNEL_TYPE_TWILIO_SMS,
    CHANNEL_TYPE_WEB_WIDGET,
    CHANNEL_TYPE_WHATSAPP,
    TWILIO_MEDIUM_SMS,
    WEB_WIDGET_DEFAULT_COLOR,
    WEB_WIDGET_DEFAULT_PRE_CHAT_FORM_OPTIONS,
    WHATSAPP_PROVIDER_360DIALOG,
    WHATSAPP_PROVIDER_CLOUD,
    WHATSAPP_PROVIDERS,
    ApiChannel,
    EmailChannel,
    FacebookPage,
    Inbox,
    InboxMember,
    InstagramChannel,
    SmsChannel,
    TelegramChannel,
    TwilioSmsChannel,
    WebWidget,
    WhatsappChannel,
    sender_name_type_from_str,
    twilio_medium_from_str,
)

# ---------------------------------------------------------------------------
# Channel registry
# ---------------------------------------------------------------------------
# Chatwoot's ``channel_type_from_params`` maps the short string in the
# payload (``"api"``, ``"email"``, …) to the Ruby class. We keep the same
# short keys so API clients flow over unchanged, and carry the Rails class
# name so inbox.channel_type lands on ``'Channel::Api'`` (exact parity).
_CHANNEL_REGISTRY: dict[str, str] = {
    "api": CHANNEL_TYPE_API,
    "email": CHANNEL_TYPE_EMAIL,
    "facebook": CHANNEL_TYPE_FACEBOOK,
    "instagram": CHANNEL_TYPE_INSTAGRAM,
    "sms": CHANNEL_TYPE_SMS,
    "telegram": CHANNEL_TYPE_TELEGRAM,
    "twilio_sms": CHANNEL_TYPE_TWILIO_SMS,
    "web_widget": CHANNEL_TYPE_WEB_WIDGET,
    "whatsapp": CHANNEL_TYPE_WHATSAPP,
}


def _allowed_channel_types() -> set[str]:
    """Same short-strings Chatwoot allows in the create payload.

    Only ``api`` is live in Phase 2 — the full Chatwoot list is
    ``%w[web_widget api email line telegram whatsapp sms]``. Adding more
    here is the entry point for future phases; the service layer fans
    out to ``_build_channel``.
    """
    return set(_CHANNEL_REGISTRY)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class InboxBuilderParams:
    """Subset of Rails' ``permitted_params`` that our API exposes.

    Flat dict-style, matching Chatwoot's ``params.permit(*inbox_attributes,
    channel: [:type, *channel_attributes])`` — the channel sub-hash is
    expressed via ``channel_type`` + ``channel_params``.
    """

    account: Account
    name: str
    channel_type: str                          # e.g. "api"
    channel_params: dict[str, Any]              # webhook_url, hmac_mandatory, ...
    # Optional inbox attributes (subset of Rails ``inbox_attributes``)
    greeting_enabled: bool | None = None
    greeting_message: str | None = None
    enable_email_collect: bool | None = None
    csat_survey_enabled: bool | None = None
    enable_auto_assignment: bool | None = None
    working_hours_enabled: bool | None = None
    out_of_office_message: str | None = None
    timezone: str | None = None
    allow_messages_after_resolved: bool | None = None
    lock_to_single_conversation: bool | None = None
    portal_id: int | None = None
    sender_name_type: str | None = None         # "friendly" | "professional"
    business_name: str | None = None
    csat_config: dict[str, Any] | None = None


@dataclass(slots=True)
class InboxBuilderResult:
    inbox: Inbox
    channel: (
        ApiChannel
        | WebWidget
        | EmailChannel
        | WhatsappChannel
        | FacebookPage
        | InstagramChannel
        | TwilioSmsChannel
        | SmsChannel
        | TelegramChannel
    )


class InboxBuilder:
    """Two-step create: channel → inbox.

    Chatwoot inlines this in the controller::

        ActiveRecord::Base.transaction do
          channel = create_channel
          @inbox = Current.account.inboxes.build(name:, channel:, ...)
          @inbox.save!
        end

    We keep the same shape but hoist it to a builder so the router stays
    thin and so integration tests can drive the create path without
    going through HTTP.
    """

    def __init__(self, session: AsyncSession, params: InboxBuilderParams) -> None:
        self._session = session
        self._params = params

    async def perform(self) -> InboxBuilderResult:
        if self._params.channel_type not in _allowed_channel_types():
            # Chatwoot silently returns ``nil`` from ``create_channel`` for
            # unknown types, which then fails ``Inbox#save!`` with a
            # ``channel must exist`` validation error (422). We shortcut
            # to the same 422 shape via the standard error envelope.
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "Channel must exist",
                    "attributes": ["channel"],
                },
            )

        channel = await self._build_channel()
        inbox = self._build_inbox(channel)
        self._session.add(inbox)
        await self._session.flush()
        await self._session.refresh(inbox)
        # Mirror Rails' ``OutOfOffisable#after_create
        # :create_default_working_hours`` callback — seed seven rows
        # (Sun + Sat closed; Mon-Fri 09:00-17:00) so the working-hours
        # update endpoints have something to PATCH and Phase 7's
        # business-hours arithmetic has a schedule to consult.
        from app.domains.working_hours.service import (
            create_default_working_hours,
        )

        await create_default_working_hours(self._session, inbox=inbox)
        return InboxBuilderResult(inbox=inbox, channel=channel)

    # ---------------------------- internals ----------------------------
    async def _build_channel(
        self,
    ) -> (
        ApiChannel
        | WebWidget
        | EmailChannel
        | WhatsappChannel
        | FacebookPage
        | InstagramChannel
        | TwilioSmsChannel
        | SmsChannel
        | TelegramChannel
    ):
        assert self._params.account.id is not None
        if self._params.channel_type == "api":
            channel = ApiChannel(
                account_id=self._params.account.id,
                webhook_url=self._params.channel_params.get("webhook_url"),
                hmac_mandatory=bool(self._params.channel_params.get("hmac_mandatory", False)),
                additional_attributes=(
                    self._params.channel_params.get("additional_attributes") or {}
                ),
            )
            self._session.add(channel)
            await self._session.flush()  # populate channel.id for the inbox row
            await self._session.refresh(channel)
            return channel
        if self._params.channel_type == "web_widget":
            params = self._params.channel_params
            website_url = params.get("website_url")
            if not website_url:
                # Mirrors Rails ``validates :website_url, presence: true``.
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={
                        "message": "Validation failed",
                        "attributes": ["website_url"],
                    },
                )
            web_widget = WebWidget(
                account_id=self._params.account.id,
                website_url=website_url,
                widget_color=params.get(
                    "widget_color", WEB_WIDGET_DEFAULT_COLOR
                ),
                welcome_title=params.get("welcome_title"),
                welcome_tagline=params.get("welcome_tagline"),
                hmac_mandatory=bool(params.get("hmac_mandatory", False)),
                pre_chat_form_enabled=bool(
                    params.get("pre_chat_form_enabled", False)
                ),
                pre_chat_form_options=(
                    params.get("pre_chat_form_options")
                    or dict(WEB_WIDGET_DEFAULT_PRE_CHAT_FORM_OPTIONS)
                ),
                continuity_via_email=bool(
                    params.get("continuity_via_email", True)
                ),
                allowed_domains=params.get("allowed_domains") or "",
            )
            self._session.add(web_widget)
            await self._session.flush()
            await self._session.refresh(web_widget)
            return web_widget
        if self._params.channel_type == "email":
            channel = await self._build_email_channel()
            return channel
        if self._params.channel_type == "whatsapp":
            wa = await self._build_whatsapp_channel()
            return wa
        if self._params.channel_type == "facebook":
            fb = await self._build_facebook_channel()
            return fb
        if self._params.channel_type == "instagram":
            ig = await self._build_instagram_channel()
            return ig
        if self._params.channel_type == "twilio_sms":
            tw = await self._build_twilio_sms_channel()
            return tw
        if self._params.channel_type == "sms":
            sms = await self._build_sms_channel()
            return sms
        if self._params.channel_type == "telegram":
            tg = await self._build_telegram_channel()
            return tg
        # Unreachable because perform() gates on _allowed_channel_types().
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": f"Unsupported channel type: {self._params.channel_type!r}"},
        )

    async def _build_email_channel(self) -> EmailChannel:
        """Validate + persist a fresh ``Channel::Email`` row.

        Validates ``email`` is present (Rails: ``validates :email,
        presence: true``). When IMAP or SMTP is enabled, requires the
        host triplet (address + port + login) so we can't ship a
        broken inbox. ``forward_to_email`` falls back to a generated
        ``<random>@inbound.local`` token because Phase 5b doesn't
        wire SES/SendGrid inbound webhooks yet — the column has a
        UNIQUE constraint and Rails generates the same kind of
        placeholder.
        """
        params = self._params.channel_params
        assert self._params.account.id is not None
        email = params.get("email")
        if not email:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed",
                    "attributes": ["email"],
                },
            )

        imap_enabled = bool(params.get("imap_enabled", False))
        smtp_enabled = bool(params.get("smtp_enabled", False))
        if imap_enabled:
            for required in ("imap_address", "imap_port", "imap_login"):
                if not params.get(required):
                    raise ChatwootHTTPException(
                        status_code=422,
                        detail={
                            "message": "Validation failed",
                            "attributes": [required],
                        },
                    )
        if smtp_enabled:
            for required in ("smtp_address", "smtp_port", "smtp_login"):
                if not params.get(required):
                    raise ChatwootHTTPException(
                        status_code=422,
                        detail={
                            "message": "Validation failed",
                            "attributes": [required],
                        },
                    )

        forward_to = params.get("forward_to_email") or (
            f"{base58_token(16)}@inbound.local"
        )

        ch = EmailChannel(
            account_id=self._params.account.id,
            email=str(email).lower(),
            forward_to_email=forward_to,
            imap_enabled=imap_enabled,
            imap_address=str(params.get("imap_address") or ""),
            imap_port=int(params.get("imap_port") or 0),
            imap_login=str(params.get("imap_login") or ""),
            imap_password=str(params.get("imap_password") or ""),
            imap_enable_ssl=bool(params.get("imap_enable_ssl", True)),
            smtp_enabled=smtp_enabled,
            smtp_address=str(params.get("smtp_address") or ""),
            smtp_port=int(params.get("smtp_port") or 0),
            smtp_login=str(params.get("smtp_login") or ""),
            smtp_password=str(params.get("smtp_password") or ""),
            smtp_domain=str(params.get("smtp_domain") or ""),
            smtp_authentication=str(
                params.get("smtp_authentication") or "login"
            ),
            smtp_enable_ssl_tls=bool(params.get("smtp_enable_ssl_tls", False)),
            smtp_enable_starttls_auto=bool(
                params.get("smtp_enable_starttls_auto", True)
            ),
            smtp_openssl_verify_mode=str(
                params.get("smtp_openssl_verify_mode") or "none"
            ),
            verified_for_sending=False,
        )
        self._session.add(ch)
        try:
            await self._session.flush()
        except Exception as exc:
            # Surface UNIQUE-violation on email / forward_to_email as a
            # clean 422; everything else re-raises.
            from sqlalchemy.exc import IntegrityError

            if isinstance(exc, IntegrityError):
                await self._session.rollback()
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={
                        "message": "Email is already taken",
                        "attributes": ["email"],
                    },
                ) from exc
            raise
        await self._session.refresh(ch)
        return ch

    async def _build_whatsapp_channel(self) -> WhatsappChannel:
        """Validate + persist a fresh ``Channel::Whatsapp`` row.

        Per-provider validation matches Rails' ``validate_provider_config``
        side of the model:

          * ``whatsapp_cloud`` -> requires ``api_key`` +
            ``phone_number_id`` + ``business_account_id`` in
            ``provider_config`` (Meta uses these to address the
            Graph API).
          * ``default`` (360dialog) -> requires ``api_key`` + ``url``.

        Both providers get an auto-generated ``webhook_verify_token``
        injected into ``provider_config`` so Meta's GET-handshake
        check (5c.2) has something to compare against. Agents can
        leave it blank in the create payload — the InboxBuilder mints
        it once and that value is what they paste into the WhatsApp
        Business Account webhook config.
        """
        params = self._params.channel_params
        assert self._params.account.id is not None

        phone_number = params.get("phone_number")
        if not phone_number:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed",
                    "attributes": ["phone_number"],
                },
            )

        provider = str(params.get("provider") or WHATSAPP_PROVIDER_360DIALOG)
        if provider not in WHATSAPP_PROVIDERS:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Validation failed: provider must be one of "
                        f"{list(WHATSAPP_PROVIDERS)!r}"
                    ),
                    "attributes": ["provider"],
                },
            )

        provider_config: dict[str, Any] = dict(
            params.get("provider_config") or {}
        )
        if provider == WHATSAPP_PROVIDER_CLOUD:
            for required in ("api_key", "phone_number_id", "business_account_id"):
                if not provider_config.get(required):
                    raise ChatwootHTTPException(
                        status_code=422,
                        detail={
                            "message": "Validation failed",
                            "attributes": [f"provider_config.{required}"],
                        },
                    )
        elif provider == WHATSAPP_PROVIDER_360DIALOG:
            for required in ("api_key", "url"):
                if not provider_config.get(required):
                    raise ChatwootHTTPException(
                        status_code=422,
                        detail={
                            "message": "Validation failed",
                            "attributes": [f"provider_config.{required}"],
                        },
                    )

        # Auto-generate the webhook verify token if the caller didn't
        # supply one — Meta will compare this against what we echo on
        # the GET handshake (5c.2).
        provider_config.setdefault(
            "webhook_verify_token", base58_token(24)
        )

        ch = WhatsappChannel(
            account_id=self._params.account.id,
            phone_number=str(phone_number),
            provider=provider,
            provider_config=provider_config,
            message_templates=[],
        )
        self._session.add(ch)
        try:
            await self._session.flush()
        except Exception as exc:
            from sqlalchemy.exc import IntegrityError

            if isinstance(exc, IntegrityError):
                await self._session.rollback()
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={
                        "message": "Phone number is already taken",
                        "attributes": ["phone_number"],
                    },
                ) from exc
            raise
        await self._session.refresh(ch)
        return ch

    async def _build_facebook_channel(self) -> FacebookPage:
        """Validate + persist a fresh ``Channel::FacebookPage`` row.

        Required params:
          * ``page_id`` — Meta's numeric page id (string).
          * ``page_access_token`` — long-lived token Meta returns
            after the OAuth handshake. We don't run the OAuth flow
            ourselves (Phase 9); the agent supplies the token via
            the create-inbox payload until then.

        Optional:
          * ``user_access_token`` — admin's user token, used to
            refresh ``page_access_token`` when it expires.
            Defaults to the page token when omitted (the most common
            case in test fixtures + simple deployments where the
            admin grants both at the same moment).
          * ``instagram_id`` — set when the FB page is connected to
            an IG Business account, so the IG channel (Phase 5e)
            can resolve back to this page row.

        Uniqueness on ``(page_id, account_id)`` surfaces as a 422
        with the canonical "already taken" envelope.
        """
        params = self._params.channel_params
        assert self._params.account.id is not None

        page_id = params.get("page_id")
        page_token = params.get("page_access_token")
        if not page_id:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed",
                    "attributes": ["page_id"],
                },
            )
        if not page_token:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed",
                    "attributes": ["page_access_token"],
                },
            )
        user_token = params.get("user_access_token") or page_token

        ch = FacebookPage(
            account_id=self._params.account.id,
            page_id=str(page_id),
            page_access_token=str(page_token),
            user_access_token=str(user_token),
            instagram_id=(
                str(params["instagram_id"])
                if params.get("instagram_id")
                else None
            ),
        )
        self._session.add(ch)
        try:
            await self._session.flush()
        except Exception as exc:
            from sqlalchemy.exc import IntegrityError

            if isinstance(exc, IntegrityError):
                await self._session.rollback()
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={
                        "message": "Page id is already taken",
                        "attributes": ["page_id"],
                    },
                ) from exc
            raise
        await self._session.refresh(ch)
        return ch

    async def _build_instagram_channel(self) -> InstagramChannel:
        """Validate + persist a fresh ``Channel::Instagram`` row.

        Required params:
          * ``instagram_id`` — IG Business account id (string).
          * ``access_token`` — long-lived OAuth token Meta returns
            from the IG Business app handshake.

        Optional:
          * ``expires_at`` — ISO-8601 timestamp where the token
            rotates. Defaults to 60 days from now (Meta's standard
            long-lived-token TTL) when the caller omits it. Phase 9
            reauthorization handles refresh — for 5e the column is
            set but never consumed.

        Uniqueness on ``instagram_id`` (account-agnostic — Meta
        only lets one app subscribe per IG id) surfaces as a 422
        with the canonical "already taken" envelope.
        """
        from datetime import UTC, datetime, timedelta

        params = self._params.channel_params
        assert self._params.account.id is not None

        ig_id = params.get("instagram_id")
        access_token = params.get("access_token")
        if not ig_id:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed",
                    "attributes": ["instagram_id"],
                },
            )
        if not access_token:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed",
                    "attributes": ["access_token"],
                },
            )

        # Default expires_at to 60 days out — Meta's long-lived
        # IG-business-account token TTL.
        expires_raw = params.get("expires_at")
        if expires_raw is None:
            expires_at = datetime.now(UTC) + timedelta(days=60)
        elif isinstance(expires_raw, datetime):
            expires_at = expires_raw
        else:
            try:
                expires_at = datetime.fromisoformat(str(expires_raw))
            except ValueError as exc:
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={
                        "message": "Validation failed",
                        "attributes": ["expires_at"],
                    },
                ) from exc

        ch = InstagramChannel(
            account_id=self._params.account.id,
            instagram_id=str(ig_id),
            access_token=str(access_token),
            expires_at=expires_at,
        )
        self._session.add(ch)
        try:
            await self._session.flush()
        except Exception as exc:
            from sqlalchemy.exc import IntegrityError

            if isinstance(exc, IntegrityError):
                await self._session.rollback()
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={
                        "message": "Instagram id is already taken",
                        "attributes": ["instagram_id"],
                    },
                ) from exc
            raise
        await self._session.refresh(ch)
        return ch

    async def _build_twilio_sms_channel(self) -> TwilioSmsChannel:
        """Validate + persist a fresh ``Channel::TwilioSms`` row.

        Required:
          * ``account_sid`` — Twilio Account SID (``ACxxxx...``).
          * ``auth_token`` — paired auth token.
          * EITHER ``phone_number`` (E.164) OR
            ``messaging_service_sid`` — Twilio routes via the latter
            when set, falls back to the from-number otherwise.

        Optional:
          * ``api_key_sid`` — alternative auth path
            (``Twilio::REST::Client.new(api_key_sid, auth_token,
            account_sid)``).
          * ``medium`` — ``'sms'`` (default) or ``'whatsapp'``. The
            WhatsApp medium ships with sub-phase 5f.6 — we accept
            it here so the column is set correctly when 5f.6 wires
            the send path.

        Uniqueness on ``phone_number`` and
        ``messaging_service_sid`` (account-agnostic — Twilio only
        lets one Account own each) surfaces as a 422.
        """
        from app.core.tokens import base58_token  # noqa: F401  (kept for parity)

        params = self._params.channel_params
        assert self._params.account.id is not None

        account_sid = params.get("account_sid")
        auth_token = params.get("auth_token")
        phone_number = params.get("phone_number")
        messaging_service_sid = params.get("messaging_service_sid")

        if not account_sid:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed",
                    "attributes": ["account_sid"],
                },
            )
        if not auth_token:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed",
                    "attributes": ["auth_token"],
                },
            )
        if not phone_number and not messaging_service_sid:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Validation failed: either phone_number or "
                        "messaging_service_sid is required"
                    ),
                    "attributes": ["phone_number"],
                },
            )

        medium_str = params.get("medium")
        if medium_str is None:
            medium = TWILIO_MEDIUM_SMS
        else:
            try:
                medium = twilio_medium_from_str(str(medium_str))
            except ValueError as exc:
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={
                        "message": "Validation failed",
                        "attributes": ["medium"],
                    },
                ) from exc

        ch = TwilioSmsChannel(
            account_id=self._params.account.id,
            account_sid=str(account_sid),
            auth_token=str(auth_token),
            api_key_sid=(
                str(params["api_key_sid"])
                if params.get("api_key_sid")
                else None
            ),
            phone_number=str(phone_number) if phone_number else None,
            messaging_service_sid=(
                str(messaging_service_sid)
                if messaging_service_sid
                else None
            ),
            medium=medium,
            content_templates=[],
        )
        self._session.add(ch)
        try:
            await self._session.flush()
        except Exception as exc:
            from sqlalchemy.exc import IntegrityError

            if isinstance(exc, IntegrityError):
                await self._session.rollback()
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={
                        "message": (
                            "Phone number or messaging service SID is "
                            "already taken"
                        ),
                        "attributes": ["phone_number"],
                    },
                ) from exc
            raise
        await self._session.refresh(ch)
        return ch

    async def _build_sms_channel(self) -> SmsChannel:
        """Validate + persist a fresh ``Channel::Sms`` row (Bandwidth).

        Required:
          * ``phone_number`` (E.164).
          * ``provider_config`` carrying Bandwidth's ``account_id``
            + ``api_token`` + ``api_secret`` + ``application_id``.

        ``phone_number`` is account-agnostic UNIQUE.
        """
        params = self._params.channel_params
        assert self._params.account.id is not None

        phone_number = params.get("phone_number")
        if not phone_number:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed",
                    "attributes": ["phone_number"],
                },
            )

        provider_config = dict(params.get("provider_config") or {})
        for required in (
            "account_id",
            "api_token",
            "api_secret",
            "application_id",
        ):
            if not provider_config.get(required):
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={
                        "message": "Validation failed",
                        "attributes": [f"provider_config.{required}"],
                    },
                )

        ch = SmsChannel(
            account_id=self._params.account.id,
            phone_number=str(phone_number),
            provider=str(params.get("provider") or "default"),
            provider_config=provider_config,
        )
        self._session.add(ch)
        try:
            await self._session.flush()
        except Exception as exc:
            from sqlalchemy.exc import IntegrityError

            if isinstance(exc, IntegrityError):
                await self._session.rollback()
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={
                        "message": "Phone number is already taken",
                        "attributes": ["phone_number"],
                    },
                ) from exc
            raise
        await self._session.refresh(ch)
        return ch

    async def _build_telegram_channel(self) -> TelegramChannel:
        """Validate + persist a fresh ``Channel::Telegram`` row.

        Required:
          * ``bot_token`` — the secret BotFather hands the agent.
            Lives in the webhook URL (Telegram requires it that way
            so the bot can verify the request came from Telegram —
            knowing the URL == knowing the token), so we treat
            it as auth.

        Optional:
          * ``bot_name`` — the bot's @username. Rails fetches it via
            ``getMe`` on create; we accept a caller-supplied value
            and default to ``"telegram-bot"`` when omitted (Phase 9
            deployment hardening adds the live ``getMe`` validation).

        Uniqueness on ``bot_token`` (account-agnostic — the same
        bot token can't auth two different inboxes; Telegram itself
        enforces single-binding) surfaces as a 422.
        """
        params = self._params.channel_params
        assert self._params.account.id is not None

        bot_token = params.get("bot_token")
        if not bot_token:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed",
                    "attributes": ["bot_token"],
                },
            )
        bot_name = params.get("bot_name") or "telegram-bot"

        ch = TelegramChannel(
            account_id=self._params.account.id,
            bot_token=str(bot_token),
            bot_name=str(bot_name),
        )
        self._session.add(ch)
        try:
            await self._session.flush()
        except Exception as exc:
            from sqlalchemy.exc import IntegrityError

            if isinstance(exc, IntegrityError):
                await self._session.rollback()
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={
                        "message": "Bot token is already taken",
                        "attributes": ["bot_token"],
                    },
                ) from exc
            raise
        await self._session.refresh(ch)
        return ch

    def _build_inbox(
        self,
        channel: (
            ApiChannel
            | WebWidget
            | EmailChannel
            | WhatsappChannel
            | FacebookPage
            | InstagramChannel
            | TwilioSmsChannel
            | SmsChannel
            | TelegramChannel
        ),
    ) -> Inbox:
        p = self._params
        assert p.account.id is not None and channel.id is not None
        data: dict[str, Any] = {
            "account_id": p.account.id,
            "channel_id": channel.id,
            "channel_type": _CHANNEL_REGISTRY[p.channel_type],
            "name": p.name,
        }
        # Only assign optional columns when the caller sent a value —
        # matches Rails' ``assign_attributes`` skipping nil keys that
        # came through strong-params.
        if p.greeting_enabled is not None:
            data["greeting_enabled"] = p.greeting_enabled
        if p.greeting_message is not None:
            data["greeting_message"] = p.greeting_message
        if p.enable_email_collect is not None:
            data["enable_email_collect"] = p.enable_email_collect
        if p.csat_survey_enabled is not None:
            data["csat_survey_enabled"] = p.csat_survey_enabled
        if p.enable_auto_assignment is not None:
            data["enable_auto_assignment"] = p.enable_auto_assignment
        if p.working_hours_enabled is not None:
            data["working_hours_enabled"] = p.working_hours_enabled
        if p.out_of_office_message is not None:
            data["out_of_office_message"] = p.out_of_office_message
        if p.timezone is not None:
            data["timezone"] = p.timezone
        if p.allow_messages_after_resolved is not None:
            data["allow_messages_after_resolved"] = p.allow_messages_after_resolved
        if p.lock_to_single_conversation is not None:
            data["lock_to_single_conversation"] = p.lock_to_single_conversation
        if p.portal_id is not None:
            data["portal_id"] = p.portal_id
        if p.sender_name_type is not None:
            data["sender_name_type"] = sender_name_type_from_str(p.sender_name_type)
        if p.business_name is not None:
            data["business_name"] = p.business_name
        if p.csat_config is not None:
            data["csat_config"] = p.csat_config
        return Inbox(**data)


# ---------------------------------------------------------------------------
# Update helpers — mirror ``InboxesController#update`` and the inline
# ``update_channel`` branch for Channel::Api.
# ---------------------------------------------------------------------------
# Editable inbox attributes — a subset of Rails ``inbox_attributes``
# suitable for PATCH. ``csat_config`` is handled via a dedicated formatter
# (Chatwoot normalises the keys); we accept arbitrary dicts for now and
# deep-merge at update time.
_INBOX_EDITABLE_FIELDS = (
    "name",
    "greeting_enabled",
    "greeting_message",
    "enable_email_collect",
    "csat_survey_enabled",
    "enable_auto_assignment",
    "working_hours_enabled",
    "out_of_office_message",
    "timezone",
    "allow_messages_after_resolved",
    "lock_to_single_conversation",
    "portal_id",
    "business_name",
)

# ``Channel::Api::EDITABLE_ATTRS`` — the Ruby constant.
API_CHANNEL_EDITABLE_FIELDS = ("webhook_url", "hmac_mandatory", "additional_attributes")

# Never presented, and blank means "leave it alone" rather than "clear it".
_WRITE_ONLY_CHANNEL_FIELDS = frozenset({"imap_password", "smtp_password"})

# What a PATCH may change, per channel type. Explicit rather than "any
# field on the row": the same payload reaches SMTP passwords and IMAP
# hosts, and a typo in the UI must not be able to redirect a mailbox.
_CHANNEL_EDITABLE_FIELDS: dict[str, tuple[str, ...]] = {
    CHANNEL_TYPE_API: API_CHANNEL_EDITABLE_FIELDS,
    CHANNEL_TYPE_EMAIL: (
        "signature",
        "logo_url",
        # IMAP/SMTP, because a mailbox created from the UI arrives with
        # both sides off and no way to switch them on — it neither sends
        # nor receives until these are set. Admin-only by the route's
        # dependency; the passwords are write-only, never presented back.
        "imap_enabled",
        "imap_address",
        "imap_port",
        "imap_login",
        "imap_password",
        "imap_enable_ssl",
        "smtp_enabled",
        "smtp_address",
        "smtp_port",
        "smtp_login",
        "smtp_password",
        "smtp_enable_ssl_tls",
        "smtp_enable_starttls_auto",
    ),
}


async def update_inbox(
    session: AsyncSession,
    *,
    inbox: Inbox,
    channel: ApiChannel | None,
    inbox_updates: dict[str, Any],
    channel_updates: dict[str, Any],
    sender_name_type: str | None = None,
    csat_config: dict[str, Any] | None = None,
) -> Inbox:
    """Apply PATCH-style updates to inbox + channel atomically.

    The channel dict is scoped to ``Channel::Api::EDITABLE_ATTRS`` — any
    extra keys are silently dropped (Rails strong-params do the same).
    ``sender_name_type`` is the string form (``"friendly"``); it's
    translated to the integer backing enum here.
    """
    for field in _INBOX_EDITABLE_FIELDS:
        if field in inbox_updates and inbox_updates[field] is not None:
            setattr(inbox, field, inbox_updates[field])
    if sender_name_type is not None:
        inbox.sender_name_type = sender_name_type_from_str(sender_name_type)
    if csat_config is not None:
        inbox.csat_config = csat_config

    if channel is not None and channel_updates:
        editable = _CHANNEL_EDITABLE_FIELDS.get(inbox.channel_type or "", ())
        for field in editable:
            if field not in channel_updates or channel_updates[field] is None:
                continue
            # A stored password is never sent back to the browser, so the
            # form has nothing to re-submit and posts "". Writing that
            # would erase the credential every time anyone saved the
            # screen for an unrelated reason.
            if field in _WRITE_ONLY_CHANNEL_FIELDS and channel_updates[field] == "":
                continue
            setattr(channel, field, channel_updates[field])
        session.add(channel)

    session.add(inbox)
    await session.flush()
    await session.refresh(inbox)
    return inbox


async def reset_api_channel_secret(session: AsyncSession, channel: ApiChannel) -> ApiChannel:
    """``Channel::Api#reset_secret!`` — rotate the HMAC-ish ``secret`` token.

    Chatwoot uses ``has_secure_token`` + ``regenerate_secret`` which emits
    a fresh base58(24) value. We mirror with
    :func:`app.core.tokens.base58_token`.
    """
    channel.secret = base58_token(24)
    session.add(channel)
    await session.flush()
    await session.refresh(channel)
    return channel


# ---------------------------------------------------------------------------
# Agent membership helpers — ``Inbox#add_members`` / ``Inbox#remove_members``
# ---------------------------------------------------------------------------
async def list_member_ids(session: AsyncSession, inbox_id: int) -> list[int]:
    stmt = select(InboxMember.user_id).where(InboxMember.inbox_id == inbox_id)
    return list((await session.exec(stmt)).all())


async def add_members(
    session: AsyncSession, *, inbox: Inbox, user_ids: list[int]
) -> list[InboxMember]:
    """Create :class:`InboxMember` rows for each ``user_id`` not yet assigned.

    Idempotent at the service layer — duplicates would raise
    UniqueViolation on the ``(inbox_id, user_id)`` index; we filter them
    out pre-insert so PATCH flows (mixed add+remove) stay atomic.

    TODO(phase5): kick ``InboxRoundRobinService#add_agent_to_queue`` per
    new member — currently a no-op because auto-assignment isn't wired.
    """
    assert inbox.id is not None
    if not user_ids:
        return []
    existing = set(await list_member_ids(session, inbox.id))
    new_ids = [uid for uid in user_ids if uid not in existing]
    members = [InboxMember(inbox_id=inbox.id, user_id=uid) for uid in new_ids]
    for m in members:
        session.add(m)
    await session.flush()
    return members


async def remove_members(
    session: AsyncSession, *, inbox: Inbox, user_ids: list[int]
) -> None:
    """Destroy :class:`InboxMember` rows matching ``(inbox_id, user_id IN …)``.

    TODO(phase5): mirror call to
    ``InboxRoundRobinService#remove_agent_from_queue``.
    """
    assert inbox.id is not None
    if not user_ids:
        return
    stmt = select(InboxMember).where(
        InboxMember.inbox_id == inbox.id,
        InboxMember.user_id.in_(user_ids),  # type: ignore[attr-defined]
    )
    rows = (await session.exec(stmt)).all()
    for r in rows:
        await session.delete(r)
    await session.flush()
