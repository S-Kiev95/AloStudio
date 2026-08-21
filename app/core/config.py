from collections.abc import Mapping
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # ``.env.local`` is layered AFTER ``.env`` so machine-local
        # secrets (Meta app credentials, etc.) override the committed
        # defaults without ever being checked in. pydantic-settings
        # applies later files with higher precedence.
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- core
    app_env: Literal["local", "test", "staging", "prod"] = "local"
    app_name: str = "alostudio"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    secret_key: str = Field(min_length=16)

    # --- db
    database_url: str
    database_url_sync: str

    # --- redis
    redis_url: str
    arq_redis_url: str

    # --- auth
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_seconds: int = 3600
    jwt_refresh_ttl_seconds: int = 60 * 60 * 24 * 30

    # --- mail
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: bool = False
    mail_from: str = "noreply@alostudio.local"

    # Public origin of the dashboard — used to build links inside
    # transactional emails (password reset, agent invitations). Override
    # in production via env (``APP_BASE_URL=https://app.midominio.com``).
    app_base_url: str = "http://localhost:3000"

    # --- integrations OAuth (Connect flow)
    # OAuth-based integration apps (Slack, Linear) are only "connectable"
    # when their client id is configured; the dashboard hides the Connect
    # link otherwise. Secrets + the callback token-exchange land with each
    # vendor's follow-up.
    slack_client_id: str | None = None
    linear_client_id: str | None = None

    # --- OpenAI (Help Center embedding search — Captain-style)
    # When ``openai_api_key`` is set, Help-Center article search switches
    # from ILIKE to semantic vector search: on save an article is expanded
    # into search terms by the chat model, each term is embedded, and the
    # public search embeds the query and does cosine nearest-neighbour.
    # Empty key → the feature is off and search falls back to ILIKE.
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com"
    # 1536-dim; must match the ``vector(1536)`` column. Mirrors Chatwoot's
    # ``LlmConstants::DEFAULT_EMBEDDING_MODEL``.
    openai_embedding_model: str = "text-embedding-3-small"
    # Chat model used to expand an article into diverse search terms.
    openai_chat_model: str = "gpt-4o"

    # --- web push (VAPID)
    # Generate a keypair once with ``app.core.webpush.generate_vapid_keys()``
    # and set these via env. Empty ``vapid_private_key`` disables web-push
    # delivery (the send task no-ops and the frontend hides the toggle).
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:ops@alostudio.local"

    # --- storage
    storage_backend: Literal["s3", "local"] = "s3"
    s3_endpoint_url: str = "http://localhost:9100"
    s3_region: str = "us-east-1"
    s3_bucket: str = "alostudio"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"

    # --- parity reference
    chatwoot_ref_base_url: str = "http://localhost:3001"
    chatwoot_ref_api_access_token: str = ""
    chatwoot_ref_admin_email: str = "admin@alostudio.local"
    chatwoot_ref_admin_password: str = "Password123!"

    # --- channels: Facebook Messenger (Phase 5d)
    # Mirrors Rails' ``FB_VERIFY_TOKEN`` env var. Set this to the same
    # value Meta has in the page's webhook subscription so the GET
    # handshake matches. Empty = no Facebook channel will accept the
    # verification (intentional — fail closed).
    fb_verify_token: str = ""
    # Graph API version Meta accepts for ``/me/messages`` calls. Bump
    # in lock-step with what the Chatwoot reference uses so a real
    # Meta-side validation passes against the same schema.
    facebook_api_version: str = "v17.0"

    # --- channels: Instagram DM (Phase 5e)
    # Mirrors Rails' ``IG_VERIFY_TOKEN`` / ``INSTAGRAM_VERIFY_TOKEN``
    # env vars (Chatwoot reads either; we ship one canonical name).
    # Same fail-closed behaviour as ``fb_verify_token``.
    ig_verify_token: str = ""

    # --- Instagram Graph publishing (feat/instagram-graph)
    # App-level credentials from the Meta Developer Dashboard. The
    # per-account Page access token + IG Business Account id live on
    # the ``channel_instagram`` row (Phase 5e), NOT here — these are
    # only the app identity used for the OAuth code exchange (I.10) +
    # the X-Hub-Signature-256 webhook verification (I.8).
    #
    # Loaded from ``.env.local`` (gitignored). Empty defaults keep the
    # app bootable without them; the publishing endpoints fail closed
    # with a clear error when unset.
    meta_app_id: str = ""
    meta_app_secret: str = ""
    # The user keeps a separate secret for the FB-Login app variant
    # ("login" app) distinct from the main app secret. Optional.
    meta_app_secret_login: str = ""
    # Graph API version pinned for all Instagram publishing calls.
    # Verified current-stable in the feat/instagram-graph research
    # (see PLAN.instagram-graph.md). Bump deliberately.
    meta_graph_api_version: str = "v23.0"
    # HMAC verification of inbound IG webhooks (I.8).
    # SECURITY: leave this ON in production. With it OFF, anyone who
    # learns the webhook URL can POST forged Instagram events that the
    # receiver will process. ``.env.example`` ships it as ``true`` so
    # fresh deployments are secure by default; the *code* default is
    # ``False`` only for backward-compat with the original unsigned
    # Phase 5e DM mirror (whose tests POST unsigned payloads). When ON,
    # the ``X-Hub-Signature-256`` header must validate against
    # ``meta_app_secret`` or the POST 401s (fails closed if unset).
    meta_verify_webhook_signature: bool = False
    # HMAC verification of inbound Twilio webhooks (CH-1).
    # SECURITY: leave this ON in production. With it OFF, anyone who
    # learns the /twilio/callback URL can POST forged SMS events.
    # When ON, the ``X-Twilio-Signature`` header must validate against
    # the resolved channel's ``auth_token`` or the POST 403s (fails
    # closed when the channel/secret can't be resolved). ``.env.example``
    # ships it ON; code default OFF for backward-compat with the
    # original unsigned receiver.
    twilio_verify_signature: bool = False
    # Opt-in pre-publish quota check (I.9). When ON, the publisher
    # queries ``content_publishing_limit`` before creating a container
    # and fails the post ``quota_exceeded`` if the 24h cap is reached
    # (saves a doomed container create). Default OFF so the publish
    # path stays a single round-trip unless an operator enables it.
    meta_check_publishing_quota: bool = False
    # OAuth redirect URI (I.10) — the callback registered in the Meta
    # app. Must match byte-for-byte between the login dialog and the
    # code exchange. Same URI serves both Facebook + Instagram Login.
    meta_oauth_redirect_uri: str = ""
    # Instagram Login flow (I.10c) — the *Instagram* app id + secret
    # (under the app's "Instagram > API setup with Instagram login"),
    # distinct from the Facebook app id/secret. Lets clients without a
    # Facebook Page connect (host ``graph.instagram.com``).
    meta_instagram_app_id: str = ""
    meta_instagram_app_secret: str = ""


# Values from ``installation_configs`` that override the environment.
# Populated by ``app.domains.installation.service`` — kept here, and
# deliberately dependency-free, because ``Settings`` must not import a
# domain (and because a deployment with no database rows has to work).
_overlay: dict[str, Any] = {}


def set_settings_overlay(values: Mapping[str, Any]) -> None:
    """Replace the DB-sourced overrides and invalidate the cache.

    Whole-replace rather than merge: a config deleted from the dashboard
    has to fall back to the environment, and a merge would keep serving
    the value that is no longer there.
    """
    global _overlay
    _overlay = dict(values)
    get_settings.cache_clear()


def clear_settings_overlay() -> None:
    global _overlay
    _overlay = {}
    get_settings.cache_clear()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    for field, value in _overlay.items():
        # The registry only ever names real fields, but a rename would
        # otherwise plant an attribute nothing reads and hide the drift.
        if hasattr(settings, field):
            setattr(settings, field, value)
    return settings
