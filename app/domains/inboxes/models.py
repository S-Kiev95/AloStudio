"""Inbox + ApiChannel + InboxMember.

Ported from:
  reference/chatwoot/app/models/inbox.rb
  reference/chatwoot/app/models/channel/api.rb
  reference/chatwoot/app/models/inbox_member.rb
  reference/chatwoot/db/schema.rb (v4.13.0)

Phase 2 scope: only the ``Channel::Api`` concrete channel is wired up. Other
channel classes (``Channel::Email``, ``Channel::FacebookPage``, etc.) will
live in sibling modules under ``app/domains/inboxes/channels/`` when their
phase arrives. The ``Inbox.channel_type`` / ``Inbox.channel_id`` columns are
*polymorphic without a foreign key* — exactly how Chatwoot stores it — so
adding more channel models later is additive.

Notable omissions (deferred):
  * ``portal_id`` column is kept (schema parity with v4.13.0) but the FK
    to ``portals`` is not declared because Portal is Phase 6+.
  * Round-robin hooks on ``InboxMember`` — Chatwoot kicks
    ``AutoAssignment::InboxRoundRobinService`` from ``after_create`` /
    ``after_destroy`` callbacks. We don't run auto-assignment yet, so the
    hooks are service-layer no-ops until Phase 5 (conversations + routing).
  * ``working_hours`` has its own table (``working_hours``) joined by
    inbox_id — that table lives in its own phase; the inbox response
    presenter surfaces an empty schedule for now.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship

from app.core.base_model import TimestampMixin
from app.core.tokens import base58_token

if TYPE_CHECKING:
    from app.domains.accounts.models import Account
    from app.domains.users.models import User


# ------------------------------------------------------------------ constants
# ``sender_name_type`` enum from Chatwoot (``enum sender_name_type: {...}``).
# Stored as integer in the DB; we expose the string at the wire boundary.
INBOX_SENDER_NAME_FRIENDLY = 0
INBOX_SENDER_NAME_PROFESSIONAL = 1
_SENDER_NAME_INT_TO_STR: dict[int, str] = {
    INBOX_SENDER_NAME_FRIENDLY: "friendly",
    INBOX_SENDER_NAME_PROFESSIONAL: "professional",
}
_SENDER_NAME_STR_TO_INT: dict[str, int] = {v: k for k, v in _SENDER_NAME_INT_TO_STR.items()}


# ``channel_type`` stores the Ruby class name verbatim (``'Channel::Api'``,
# ``'Channel::Email'``, …). We keep the Ruby spelling so a side-by-side DB
# dump against Chatwoot lines up identically.
CHANNEL_TYPE_API = "Channel::Api"
CHANNEL_TYPE_EMAIL = "Channel::Email"
CHANNEL_TYPE_FACEBOOK = "Channel::FacebookPage"
CHANNEL_TYPE_INSTAGRAM = "Channel::Instagram"
CHANNEL_TYPE_SMS = "Channel::Sms"
CHANNEL_TYPE_TWILIO_SMS = "Channel::TwilioSms"
CHANNEL_TYPE_WEB_WIDGET = "Channel::WebWidget"
CHANNEL_TYPE_WHATSAPP = "Channel::Whatsapp"

# Rails ``Channel::TwilioSms#medium`` enum: 0=sms, 1=whatsapp.
TWILIO_MEDIUM_SMS = 0
TWILIO_MEDIUM_WHATSAPP = 1
_TWILIO_MEDIUM_INT_TO_STR: dict[int, str] = {
    TWILIO_MEDIUM_SMS: "sms",
    TWILIO_MEDIUM_WHATSAPP: "whatsapp",
}


def twilio_medium_to_str(value: int) -> str:
    return _TWILIO_MEDIUM_INT_TO_STR.get(value, "sms")


def twilio_medium_from_str(value: str) -> int:
    if value == "sms":
        return TWILIO_MEDIUM_SMS
    if value == "whatsapp":
        return TWILIO_MEDIUM_WHATSAPP
    raise ValueError(f"unknown twilio medium: {value!r}")

# Provider strings mirror Chatwoot exactly. ``default`` is 360dialog
# (legacy naming kept for parity); ``whatsapp_cloud`` is Meta's
# official Graph API.
WHATSAPP_PROVIDER_360DIALOG = "default"
WHATSAPP_PROVIDER_CLOUD = "whatsapp_cloud"
WHATSAPP_PROVIDERS = (WHATSAPP_PROVIDER_360DIALOG, WHATSAPP_PROVIDER_CLOUD)


# Default ``pre_chat_form_options`` JSON Chatwoot writes when a fresh
# ``Channel::WebWidget`` row is created without explicit options. Kept
# here (not on :class:`WebWidget` directly) so the InboxBuilder can
# inject it without instantiating the SQLModel.
WEB_WIDGET_DEFAULT_PRE_CHAT_FORM_OPTIONS: dict[str, Any] = {
    "pre_chat_message": "Share your queries or comments here.",
    "pre_chat_fields": [
        {
            "field_type": "standard",
            "label": "Email Id",
            "name": "emailAddress",
            "type": "email",
            "required": True,
            "enabled": False,
        },
        {
            "field_type": "standard",
            "label": "Full name",
            "name": "fullName",
            "type": "text",
            "required": False,
            "enabled": False,
        },
        {
            "field_type": "standard",
            "label": "Phone number",
            "name": "phoneNumber",
            "type": "text",
            "required": False,
            "enabled": False,
        },
    ],
}

# ``feature_flags`` default — Chatwoot's FlagShihTzu maps
# attachments=1, emoji_picker=2, end_conversation=3 -> default 7
# (1+2+4 = first three flags on).
WEB_WIDGET_DEFAULT_FEATURE_FLAGS = 7

# ``widget_color`` default Chatwoot ships.
WEB_WIDGET_DEFAULT_COLOR = "#1f93ff"


def sender_name_type_to_str(value: int) -> str:
    return _SENDER_NAME_INT_TO_STR.get(value, "friendly")


def sender_name_type_from_str(value: str) -> int:
    try:
        return _SENDER_NAME_STR_TO_INT[value]
    except KeyError as e:
        raise ValueError(f"unknown sender_name_type: {value!r}") from e


# =========================================================================
# ApiChannel (Channel::Api)
# =========================================================================
class ApiChannel(TimestampMixin, table=True):
    """Concrete channel for ``Channel::Api`` — the generic HTTP API channel.

    Chatwoot stores channel rows in per-type tables (``channel_api``,
    ``channel_email``, …) — no shared channels table. The Inbox joins via
    polymorphic ``(channel_type, channel_id)`` columns without a real FK,
    so each channel table is a standalone island.

    ``identifier``, ``hmac_token``, and ``secret`` come from Rails'
    ``has_secure_token`` + ``WebhookSecretable`` concerns — 24-char Base58
    tokens generated at create time. ``identifier`` and ``hmac_token`` carry
    UNIQUE indexes so a collision would surface as an IntegrityError rather
    than silent overwrites.
    """

    __tablename__ = "channel_api"

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    webhook_url: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    # has_secure_token :identifier / :hmac_token + WebhookSecretable :secret
    identifier: str | None = Field(
        default_factory=lambda: base58_token(24),
        sa_column=Column(String, nullable=True, unique=True),
    )
    hmac_token: str | None = Field(
        default_factory=lambda: base58_token(24),
        sa_column=Column(String, nullable=True, unique=True),
    )
    secret: str | None = Field(
        default_factory=lambda: base58_token(24),
        sa_column=Column(String, nullable=True),
    )

    hmac_mandatory: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false"),
    )
    additional_attributes: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True, server_default="{}"),
    )


# =========================================================================
# WebWidget (Channel::WebWidget)
# =========================================================================
class WebWidget(TimestampMixin, table=True):
    """Concrete channel for ``Channel::WebWidget`` — the embedded
    JS chat widget.

    Schema mirrors ``channel_web_widgets`` from Chatwoot v4.13.0:
    ``website_token`` is a per-inbox public id surfaced to the JS SDK,
    ``hmac_token`` is the symmetric secret used by ``Contacts#set_user``
    HMAC validation, and ``feature_flags`` is a bitmask (FlagShihTzu)
    encoding attachments / emoji_picker / end_conversation /
    use_inbox_avatar_for_bot / allow_mobile_webview.

    The Rails model exposes booleans via FlagShihTzu's ``has_flags``;
    we expose them as Python properties + helpers (see
    :meth:`feature_flag` / :meth:`set_feature_flag`).
    """

    __tablename__ = "channel_web_widgets"
    __table_args__ = (
        Index(
            "index_channel_web_widgets_on_website_token",
            "website_token",
            unique=True,
        ),
        Index(
            "index_channel_web_widgets_on_hmac_token",
            "hmac_token",
            unique=True,
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    website_url: str = Field(sa_column=Column(String, nullable=False))
    widget_color: str = Field(
        default=WEB_WIDGET_DEFAULT_COLOR,
        sa_column=Column(
            String, nullable=False, server_default=WEB_WIDGET_DEFAULT_COLOR
        ),
    )
    welcome_title: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    welcome_tagline: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )

    # Rails ``has_secure_token :website_token`` / ``:hmac_token`` —
    # auto-generated on insert. We mint Base58 strings here for parity
    # with the rest of our token surface; Chatwoot uses URL-safe Base64
    # via ``has_secure_token``, but the column is opaque.
    website_token: str = Field(
        default_factory=lambda: base58_token(24),
        sa_column=Column(String, nullable=False),
    )
    hmac_token: str = Field(
        default_factory=lambda: base58_token(24),
        sa_column=Column(String, nullable=False),
    )

    hmac_mandatory: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false"),
    )
    pre_chat_form_enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false"),
    )
    pre_chat_form_options: dict[str, Any] = Field(
        default_factory=lambda: dict(WEB_WIDGET_DEFAULT_PRE_CHAT_FORM_OPTIONS),
        sa_column=Column(JSONB, nullable=True),
    )
    continuity_via_email: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    feature_flags: int = Field(
        default=WEB_WIDGET_DEFAULT_FEATURE_FLAGS,
        sa_column=Column(
            Integer,
            nullable=False,
            server_default=str(WEB_WIDGET_DEFAULT_FEATURE_FLAGS),
        ),
    )
    reply_time: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=True, server_default="0"),
    )
    allowed_domains: str | None = Field(
        default="",
        sa_column=Column(Text, nullable=True, server_default=""),
    )

    # FlagShihTzu bit positions (1-indexed, matching the Ruby ``has_flags``).
    _FLAG_ATTACHMENTS = 1
    _FLAG_EMOJI_PICKER = 2
    _FLAG_END_CONVERSATION = 3
    _FLAG_USE_INBOX_AVATAR_FOR_BOT = 4
    _FLAG_ALLOW_MOBILE_WEBVIEW = 5

    def feature_flag(self, position: int) -> bool:
        """Read flag at 1-indexed bit position (mirrors FlagShihTzu)."""
        return bool(self.feature_flags & (1 << (position - 1)))

    @property
    def attachments(self) -> bool:
        return self.feature_flag(self._FLAG_ATTACHMENTS)

    @property
    def emoji_picker(self) -> bool:
        return self.feature_flag(self._FLAG_EMOJI_PICKER)

    @property
    def end_conversation(self) -> bool:
        return self.feature_flag(self._FLAG_END_CONVERSATION)

    @property
    def use_inbox_avatar_for_bot(self) -> bool:
        return self.feature_flag(self._FLAG_USE_INBOX_AVATAR_FOR_BOT)

    @property
    def allow_mobile_webview(self) -> bool:
        return self.feature_flag(self._FLAG_ALLOW_MOBILE_WEBVIEW)


# =========================================================================
# EmailChannel (Channel::Email)
# =========================================================================
class EmailChannel(TimestampMixin, table=True):
    """Concrete channel for ``Channel::Email``.

    Schema mirrors ``channel_email`` from Chatwoot v4.13.0 — IMAP
    inbound + SMTP outbound, both gated by per-side ``*_enabled``
    flags so an inbox can be in send-only or receive-only mode.

    The ``provider`` + ``provider_config`` fields ship empty in 5b
    — they're the OAuth2 surface (Gmail / Microsoft Entra) which
    lands with Phase 9 alongside the other OAuth integrations. The
    columns are present so the schema is forward-compatible: enabling
    OAuth then is a service-layer change, not a migration.

    Password fields:
      Rails encrypts ``imap_password`` + ``smtp_password`` via the
      ``encrypts`` macro when ``Chatwoot.encryption_configured?``.
      Our port leaves them as plain ``String`` for 5b — Phase 10
      hardening adds at-rest encryption (libsodium / fernet keyed
      off ``settings.secret_key``) once a deployment matters.
    """

    __tablename__ = "channel_email"
    __table_args__ = (
        Index("index_channel_email_on_email", "email", unique=True),
        Index(
            "index_channel_email_on_forward_to_email",
            "forward_to_email",
            unique=True,
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # Public address customers send mail TO.
    email: str = Field(sa_column=Column(String, nullable=False))
    # Internal address generated for catch-all / fallback ingest. We
    # set this at create-time to ``<random>@<account_domain>`` until
    # the inbound webhook story (Phase 8b) gives it a real meaning.
    forward_to_email: str = Field(sa_column=Column(String, nullable=False))

    # IMAP inbound -----------------------------------------------------
    imap_enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false"),
    )
    imap_address: str = Field(
        default="", sa_column=Column(String, nullable=True, server_default="")
    )
    imap_port: int = Field(
        default=0, sa_column=Column(Integer, nullable=True, server_default="0")
    )
    imap_login: str = Field(
        default="", sa_column=Column(String, nullable=True, server_default="")
    )
    imap_password: str = Field(
        default="", sa_column=Column(String, nullable=True, server_default="")
    )
    imap_enable_ssl: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=True, server_default="true"),
    )

    # SMTP outbound ----------------------------------------------------
    smtp_enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false"),
    )
    smtp_address: str = Field(
        default="", sa_column=Column(String, nullable=True, server_default="")
    )
    smtp_port: int = Field(
        default=0, sa_column=Column(Integer, nullable=True, server_default="0")
    )
    smtp_login: str = Field(
        default="", sa_column=Column(String, nullable=True, server_default="")
    )
    smtp_password: str = Field(
        default="", sa_column=Column(String, nullable=True, server_default="")
    )
    smtp_domain: str = Field(
        default="", sa_column=Column(String, nullable=True, server_default="")
    )
    smtp_authentication: str = Field(
        default="login",
        sa_column=Column(String, nullable=True, server_default="login"),
    )
    smtp_enable_ssl_tls: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false"),
    )
    smtp_enable_starttls_auto: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=True, server_default="true"),
    )
    smtp_openssl_verify_mode: str = Field(
        default="none",
        sa_column=Column(String, nullable=True, server_default="none"),
    )

    verified_for_sending: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )

    # OAuth surface (Phase 9 — empty in 5b) ---------------------------
    provider: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    provider_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True),
    )


# =========================================================================
# WhatsappChannel (Channel::Whatsapp)
# =========================================================================
class WhatsappChannel(TimestampMixin, table=True):
    """Concrete channel for ``Channel::Whatsapp``.

    Schema mirrors ``channel_whatsapp`` from Chatwoot v4.13.0.
    ``provider`` is ``'default'`` for 360dialog (legacy naming) or
    ``'whatsapp_cloud'`` for Meta's official Graph API. Each provider
    stores different keys under ``provider_config``:

      * ``whatsapp_cloud`` -> ``{api_key, phone_number_id,
        business_account_id, webhook_verify_token, ...}``
      * ``default`` (360dialog) -> ``{api_key, url,
        webhook_verify_token, ...}``

    ``message_templates`` is the cached list of approved templates
    fetched from Meta's Graph API. Empty in 5c.1; populated by the
    template sync service in 5c.6.

    The webhook verify token is auto-generated at create time so the
    InboxBuilder doesn't have to ask the agent for one — Meta's
    subscription-setup handshake compares it to whatever they entered
    in their app config.
    """

    __tablename__ = "channel_whatsapp"
    __table_args__ = (
        Index(
            "index_channel_whatsapp_on_phone_number",
            "phone_number",
            unique=True,
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    phone_number: str = Field(sa_column=Column(String, nullable=False))
    provider: str = Field(
        default=WHATSAPP_PROVIDER_360DIALOG,
        sa_column=Column(String, nullable=True, server_default=WHATSAPP_PROVIDER_360DIALOG),
    )
    provider_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True),
    )
    message_templates: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=True),
    )
    message_templates_last_updated: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    @property
    def webhook_verify_token(self) -> str | None:
        """Convenience accessor — the token lives in ``provider_config``
        but every webhook code path reads it as a top-level field.
        """
        cfg = self.provider_config or {}
        if isinstance(cfg, dict):
            tok = cfg.get("webhook_verify_token")
            return str(tok) if tok else None
        return None


# =========================================================================
# FacebookPage (Channel::FacebookPage)
# =========================================================================
class FacebookPage(TimestampMixin, table=True):
    """Concrete channel for ``Channel::FacebookPage``.

    Schema mirrors ``channel_facebook_pages`` from Chatwoot v4.13.0.
    ``page_id`` identifies the Facebook page on Meta's side (numeric
    string), ``page_access_token`` is the long-lived token Meta returns
    after the OAuth handshake, and ``user_access_token`` is the token
    the page admin granted us — kept around so we can refresh
    ``page_access_token`` when it expires (60 days for long-lived
    tokens). ``instagram_id`` lights up when the page is connected to
    an Instagram Business account, but the IG channel itself ships in
    Phase 5e so we just store the value here.

    Verify-token shape diverges from WhatsApp: Facebook uses an
    installation-wide ``FB_VERIFY_TOKEN`` (env var) that's the same
    for every page. We hold the value in :class:`Settings.fb_verify
    _token`; the channel itself doesn't carry one.

    Encryption: Rails' :class:`Channel::FacebookPage` encrypts both
    access tokens at rest when ``Chatwoot.encryption_configured?``.
    Phase 5d ports the columns as plain ``String``; Phase 10 hardening
    adds at-rest encryption (libsodium / fernet keyed off
    ``settings.secret_key``).
    """

    __tablename__ = "channel_facebook_pages"
    __table_args__ = (
        Index(
            "index_channel_facebook_pages_on_page_id",
            "page_id",
        ),
        Index(
            "index_channel_facebook_pages_on_page_id_and_account_id",
            "page_id",
            "account_id",
            unique=True,
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    page_id: str = Field(sa_column=Column(String, nullable=False))
    page_access_token: str = Field(sa_column=Column(String, nullable=False))
    user_access_token: str = Field(sa_column=Column(String, nullable=False))
    instagram_id: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )


# =========================================================================
# InstagramChannel (Channel::Instagram)
# =========================================================================
class InstagramChannel(TimestampMixin, table=True):
    """Concrete channel for ``Channel::Instagram`` — the modern
    "Direct Instagram Login" path.

    Schema mirrors ``channel_instagram`` from Chatwoot v4.13.0.
    ``instagram_id`` is the IG Business account id; ``access_token``
    is the long-lived OAuth token Meta returns from the Instagram
    Business app handshake. ``expires_at`` is the absolute timestamp
    where the token rotates (Phase 9 reauthorization handles the
    refresh — for 5e the column is set but not consumed).

    Distinct from the legacy "Instagram via Facebook Page" path
    (which lives on :class:`FacebookPage.instagram_id` — same Meta
    surface, different routing). Phase 5e ports the standalone IG
    channel only; the FB-page-IG branch lands in a later sub-phase
    once we wire the dispatch-by-instagram-id router.
    """

    __tablename__ = "channel_instagram"
    __table_args__ = (
        Index(
            "index_channel_instagram_on_instagram_id",
            "instagram_id",
            unique=True,
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    instagram_id: str = Field(sa_column=Column(String, nullable=False))
    access_token: str = Field(sa_column=Column(String, nullable=False))
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


# =========================================================================
# TwilioSmsChannel (Channel::TwilioSms)
# =========================================================================
class TwilioSmsChannel(TimestampMixin, table=True):
    """Concrete channel for ``Channel::TwilioSms`` — Twilio's SMS
    REST API. Also covers Twilio's WhatsApp (``medium=whatsapp``)
    via the same row + REST endpoint; the WhatsApp medium ships in
    sub-phase 5f.6.

    Schema mirrors ``channel_twilio_sms`` from Chatwoot v4.13.0:
    ``account_sid`` + ``auth_token`` are the Twilio account
    credentials, ``phone_number`` is the agent-facing E.164 number
    (e.g. ``+15551234567``), and ``messaging_service_sid`` is the
    optional Messaging Service that lets Twilio pick a sender from
    a pool.

    Three unique indexes mirror Rails:
      * ``phone_number`` (account-agnostic — Twilio only lets one
        Account own a number).
      * ``messaging_service_sid`` (account-agnostic — same reason).
      * ``(account_sid, phone_number)`` (defensive).
    """

    __tablename__ = "channel_twilio_sms"
    __table_args__ = (
        Index(
            "index_channel_twilio_sms_on_phone_number",
            "phone_number",
            unique=True,
        ),
        Index(
            "index_channel_twilio_sms_on_messaging_service_sid",
            "messaging_service_sid",
            unique=True,
        ),
        Index(
            "index_channel_twilio_sms_on_account_sid_and_phone_number",
            "account_sid",
            "phone_number",
            unique=True,
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    account_sid: str = Field(sa_column=Column(String, nullable=False))
    auth_token: str = Field(sa_column=Column(String, nullable=False))
    api_key_sid: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    phone_number: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    messaging_service_sid: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    medium: int = Field(
        default=TWILIO_MEDIUM_SMS,
        sa_column=Column(
            Integer,
            nullable=True,
            server_default=str(TWILIO_MEDIUM_SMS),
        ),
    )
    content_templates: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=True),
    )
    content_templates_last_updated: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    @property
    def medium_str(self) -> str:
        return twilio_medium_to_str(self.medium)


# =========================================================================
# SmsChannel (Channel::Sms — Bandwidth provider)
# =========================================================================
class SmsChannel(TimestampMixin, table=True):
    """Concrete channel for ``Channel::Sms`` — Bandwidth's messaging
    API (Chatwoot's ``provider='default'`` is Bandwidth; the
    ``provider`` column exists for forward-compat with other
    SMS-aggregator providers but only Bandwidth ships in 5f).

    Schema mirrors ``channel_sms`` from Chatwoot v4.13.0:
    ``phone_number`` UNIQUE, ``provider_config`` JSONB carrying
    Bandwidth's ``account_id`` + ``api_token`` + ``api_secret`` +
    ``application_id`` (the four values that authorise outbound +
    correlate inbound).
    """

    __tablename__ = "channel_sms"
    __table_args__ = (
        Index(
            "index_channel_sms_on_phone_number",
            "phone_number",
            unique=True,
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    phone_number: str = Field(sa_column=Column(String, nullable=False))
    provider: str = Field(
        default="default",
        sa_column=Column(String, nullable=True, server_default="default"),
    )
    provider_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True),
    )


# =========================================================================
# Inbox
# =========================================================================
class Inbox(TimestampMixin, table=True):
    """Generic channel wrapper — one row per agent-facing inbox.

    The ``channel_type`` / ``channel_id`` pair is a Rails polymorphic
    association with *no FK* — Postgres doesn't know about the link, so
    deletes cascade via the Ruby ``dependent: :destroy_async`` hook, which
    we replicate in the service layer (see :mod:`app.domains.inboxes.service`).
    """

    __tablename__ = "inboxes"
    __table_args__ = (
        Index("index_inboxes_on_account_id", "account_id"),
        Index(
            "index_inboxes_on_channel_id_and_channel_type",
            "channel_id",
            "channel_type",
        ),
        Index("index_inboxes_on_portal_id", "portal_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    channel_id: int = Field(sa_column=Column(Integer, nullable=False))
    channel_type: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    name: str = Field(sa_column=Column(String, nullable=False))
    business_name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    email_address: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    # Feature toggles — all default TRUE/FALSE per Chatwoot schema
    enable_auto_assignment: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=True, server_default="true"),
    )
    enable_email_collect: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=True, server_default="true"),
    )
    greeting_enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false"),
    )
    greeting_message: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    working_hours_enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false"),
    )
    out_of_office_message: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    timezone: str = Field(
        default="UTC",
        sa_column=Column(String, nullable=True, server_default="UTC"),
    )
    csat_survey_enabled: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false"),
    )
    allow_messages_after_resolved: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=True, server_default="true"),
    )
    lock_to_single_conversation: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )

    # ``sender_name_type`` — 0=friendly, 1=professional (integer enum in Rails)
    sender_name_type: int = Field(
        default=INBOX_SENDER_NAME_FRIENDLY,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )

    # JSONB blobs — shape owned by the service layer, schema stays permissive
    auto_assignment_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True, server_default="{}"),
    )
    csat_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )

    # Portal FK is deferred until Phase 6 (HelpCenter) — keep column for
    # schema parity, no SA-level ForeignKey declared yet.
    portal_id: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))

    # Relationships
    account: "Account" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})
    inbox_members: list["InboxMember"] = Relationship(
        back_populates="inbox",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
        },
    )

    # ---- helpers (not persisted) -------------------------------------
    @property
    def sender_name_type_str(self) -> str:
        return sender_name_type_to_str(self.sender_name_type)

    def is_api(self) -> bool:
        return self.channel_type == CHANNEL_TYPE_API


# =========================================================================
# InboxMember
# =========================================================================
class InboxMember(TimestampMixin, table=True):
    """Agent ↔ Inbox join row.

    Chatwoot attaches two callbacks here:
      * ``after_create`` → ``InboxRoundRobinService#add_agent_to_queue``
      * ``after_destroy`` → ``InboxRoundRobinService#remove_agent_from_queue``

    Auto-assignment isn't wired yet (Phase 5), so we don't replicate those
    callbacks at the ORM level. The service-layer helpers in
    :mod:`app.domains.inboxes.service` will be the future injection point
    when round-robin arrives.
    """

    __tablename__ = "inbox_members"
    __table_args__ = (
        UniqueConstraint(
            "inbox_id", "user_id", name="index_inbox_members_on_inbox_id_and_user_id"
        ),
        Index("index_inbox_members_on_inbox_id", "inbox_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    user_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    inbox_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # Chatwoot uses ``precision: nil`` on these two columns (timestamp
    # without fractional seconds). We inherit the base ``TimestampMixin``
    # columns instead of overriding — ``DateTime(timezone=True)`` with
    # default precision is a harmless precision-widening, not a schema
    # break. Flagged here so nobody writes a parity assertion against
    # microsecond-level equality.

    # Relationships
    inbox: "Inbox" = Relationship(
        back_populates="inbox_members",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    user: "User" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})


__all__ = [
    "CHANNEL_TYPE_API",
    "CHANNEL_TYPE_EMAIL",
    "CHANNEL_TYPE_FACEBOOK",
    "CHANNEL_TYPE_INSTAGRAM",
    "CHANNEL_TYPE_SMS",
    "CHANNEL_TYPE_TWILIO_SMS",
    "CHANNEL_TYPE_WEB_WIDGET",
    "CHANNEL_TYPE_WHATSAPP",
    "INBOX_SENDER_NAME_FRIENDLY",
    "INBOX_SENDER_NAME_PROFESSIONAL",
    "TWILIO_MEDIUM_SMS",
    "TWILIO_MEDIUM_WHATSAPP",
    "WEB_WIDGET_DEFAULT_COLOR",
    "WEB_WIDGET_DEFAULT_FEATURE_FLAGS",
    "WEB_WIDGET_DEFAULT_PRE_CHAT_FORM_OPTIONS",
    "WHATSAPP_PROVIDER_360DIALOG",
    "WHATSAPP_PROVIDER_CLOUD",
    "WHATSAPP_PROVIDERS",
    "ApiChannel",
    "EmailChannel",
    "FacebookPage",
    "Inbox",
    "InboxMember",
    "InstagramChannel",
    "SmsChannel",
    "TwilioSmsChannel",
    "WebWidget",
    "WhatsappChannel",
    "sender_name_type_from_str",
    "sender_name_type_to_str",
    "twilio_medium_from_str",
    "twilio_medium_to_str",
]
