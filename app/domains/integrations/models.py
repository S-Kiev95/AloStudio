"""IntegrationsHook + the static App catalogue.

Ported from:
  reference/chatwoot/app/models/integrations/hook.rb
  reference/chatwoot/app/models/integrations/app.rb
  reference/chatwoot/db/schema.rb (``integrations_hooks`` table)

Phase 8.4 scope: the generic registry that the dashboard's
"Integrations" tab consumes. Each row binds an account (and
optionally an inbox) to one app — Slack / Dialogflow / Linear /
Shopify / Notion / Dyte / OpenAI. The per-vendor adapters defer
because each needs its own OAuth + SDK + per-vendor settings schema.

The ``encrypts :access_token`` ActiveRecord directive in Chatwoot
defers to Phase 10 (cryptography setup is part of hardening). For
now we store ``access_token`` in plaintext like every other API
secret in our DB — same posture as ``webhooks.secret`` and
``agent_bots.secret``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.base_model import TimestampMixin

# enum hook_type: {account: 0, inbox: 1}
HOOK_TYPE_ACCOUNT = 0
HOOK_TYPE_INBOX = 1

# enum status: {disabled: 0, enabled: 1}
HOOK_STATUS_DISABLED = 0
HOOK_STATUS_ENABLED = 1


def hook_type_from_str(s: str | None) -> int:
    if s == "inbox":
        return HOOK_TYPE_INBOX
    return HOOK_TYPE_ACCOUNT


def hook_type_to_str(v: int | None) -> str:
    return "inbox" if v == HOOK_TYPE_INBOX else "account"


class IntegrationsHook(TimestampMixin, table=True):
    __tablename__ = "integrations_hooks"

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
    inbox_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("inboxes.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    app_id: str = Field(sa_column=Column(String, nullable=False))
    hook_type: int = Field(
        default=HOOK_TYPE_ACCOUNT,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    status: int = Field(
        default=HOOK_STATUS_ENABLED,
        sa_column=Column(Integer, nullable=False, server_default="1"),
    )
    reference_id: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    access_token: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    settings: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )


# ---------------------------------------------------------------------------
# Static app catalogue (mirrors ``Integrations::App.all``)
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class IntegrationApp:
    """One entry in the integrations directory — what the dashboard's
    "Integrations" tab renders.

    Phase 8.4 ships the metadata for every app Chatwoot v4.13.0
    advertises. The per-app OAuth flow + processing pipeline defer to
    follow-up phases on a vendor-by-vendor basis."""

    id: str
    name: str
    description: str
    short_description: str
    enabled: bool = True
    allow_multiple_hooks: bool = False
    # ``action`` mirrors ``config/integration/apps.yml``: a relative path
    # (``/openai``) means an inline settings form; an absolute URL means an
    # external OAuth authorize endpoint; ``None`` means "no Connect action".
    # ``hook_type`` scopes a connection to the whole account or one inbox.
    action: str | None = None
    hook_type: str = "account"


# Order mirrors ``config/integrations.yml`` in Chatwoot — keeps the
# dashboard's tab order consistent.
# OAuth apps: ``action`` is an external authorize URL the presenter
# augments with the configured client id + redirect uri.
OAUTH_APPS: frozenset[str] = frozenset({"slack", "linear"})

# Order mirrors ``config/integration/apps.yml`` in Chatwoot.
INTEGRATION_APPS: tuple[IntegrationApp, ...] = (
    IntegrationApp(
        id="slack",
        name="Slack",
        description="Chat with users directly from Slack channels.",
        short_description="Slack thread relay",
        action=(
            "https://slack.com/oauth/v2/authorize?scope=commands,chat:write,"
            "channels:read,channels:manage,channels:join,groups:read,"
            "groups:write,im:write,mpim:write,users:read,users:read.email,"
            "chat:write.customize,channels:history,groups:history,"
            "mpim:history,im:history,files:read,files:write"
        ),
        hook_type="account",
    ),
    IntegrationApp(
        id="dialogflow",
        name="Dialogflow",
        description="Route incoming messages through a Dialogflow agent.",
        short_description="Dialogflow router",
        action="/dialogflow",
        hook_type="inbox",
    ),
    IntegrationApp(
        id="webhook",
        name="Webhook",
        description="Generic outbound webhook receiver.",
        short_description="HTTP receiver",
        allow_multiple_hooks=True,
        action="/webhook",
        hook_type="account",
    ),
    IntegrationApp(
        id="openai",
        name="OpenAI",
        description="AI-assisted reply suggestions powered by OpenAI.",
        short_description="OpenAI reply assist",
        action="/openai",
        hook_type="account",
    ),
    IntegrationApp(
        id="linear",
        name="Linear",
        description="Link conversations to Linear issues.",
        short_description="Linear issue link",
        action="https://linear.app/oauth/authorize",
        hook_type="account",
    ),
    IntegrationApp(
        id="shopify",
        name="Shopify",
        description="Show contact orders and account from Shopify.",
        short_description="Shopify customer info",
        hook_type="account",
    ),
    IntegrationApp(
        id="notion",
        name="Notion",
        description="Surface Notion docs in the agent sidebar.",
        short_description="Notion knowledge",
        hook_type="account",
    ),
    IntegrationApp(
        id="dyte",
        name="Dyte",
        description="Start a video call inside the conversation.",
        short_description="Embedded video",
        action="/dyte",
        hook_type="account",
    ),
)


def resolve_action(
    app: IntegrationApp,
    *,
    client_ids: dict[str, str | None],
    app_base_url: str,
) -> str | None:
    """Mirror ``Integrations::App#action``.

    Inline apps return their relative action verbatim. OAuth apps get their
    authorize URL augmented with the configured ``client_id`` + our callback
    ``redirect_uri`` — or ``None`` when no client id is configured (the app
    isn't connectable, matching Chatwoot's ``active?`` gate).
    """
    if app.action is None:
        return None
    if app.id in OAUTH_APPS:
        client_id = client_ids.get(app.id)
        if not client_id:
            return None
        redirect_uri = f"{app_base_url}/api/v1/integrations/{app.id}/callback"
        sep = "&" if "?" in app.action else "?"
        return (
            f"{app.action}{sep}client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
        )
    return app.action


def find_app(app_id: str) -> IntegrationApp | None:
    for app in INTEGRATION_APPS:
        if app.id == app_id:
            return app
    return None


__all__ = [
    "HOOK_STATUS_DISABLED",
    "HOOK_STATUS_ENABLED",
    "HOOK_TYPE_ACCOUNT",
    "HOOK_TYPE_INBOX",
    "INTEGRATION_APPS",
    "OAUTH_APPS",
    "IntegrationApp",
    "IntegrationsHook",
    "find_app",
    "hook_type_from_str",
    "hook_type_to_str",
    "resolve_action",
]
