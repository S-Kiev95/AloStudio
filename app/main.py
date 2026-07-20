from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.cable import router as cable_router
from app.core.config import get_settings
from app.core.db import dispose_engine
from app.core.errors import ChatwootHTTPException, chatwoot_http_exception_handler
from app.core.logging import configure_logging, get_logger
from app.domains.accounts.router import router as accounts_router
from app.domains.agent_bots.router import (
    inbox_set_agent_bot_router,
)
from app.domains.agent_bots.router import (
    router as agent_bots_router,
)
from app.domains.assignment_policies.router import (
    inbox_router as inbox_assignment_policy_router,
)
from app.domains.assignment_policies.router import (
    router as assignment_policies_router,
)
from app.domains.auth.router import resend_confirmation_router
from app.domains.auth.router import router as auth_router
from app.domains.automation.router import router as automation_rules_router
from app.domains.bulk_actions.router import router as bulk_actions_router
from app.domains.campaigns.router import router as campaigns_router
from app.domains.canned_responses.router import router as canned_responses_router
from app.domains.contacts.router import actions_router as contact_actions_router
from app.domains.contacts.router import router as contacts_router
from app.domains.conversations.attachments_router import (
    public_router as public_attachments_router,
)
from app.domains.conversations.attachments_router import (
    router as attachments_router,
)
from app.domains.conversations.router import messages_router as conversations_messages_router
from app.domains.conversations.router import (
    participants_router as conversations_participants_router,
)
from app.domains.conversations.router import router as conversations_router
from app.domains.csat.public_router import router as csat_public_router
from app.domains.csat.router import router as csat_router
from app.domains.custom_attributes.router import router as custom_attributes_router
from app.domains.custom_views.router import router as custom_views_router
from app.domains.facebook.router import router as facebook_webhook_router
from app.domains.inboxes.router import inbox_members_router
from app.domains.inboxes.router import router as inboxes_router
from app.domains.instagram.comments_router import router as instagram_comments_router
from app.domains.instagram.connect_router import (
    callback_router as instagram_oauth_callback_router,
)
from app.domains.instagram.connect_router import (
    router as instagram_connect_router,
)
from app.domains.instagram.publishing_router import router as instagram_publishing_router
from app.domains.instagram.router import router as instagram_webhook_router
from app.domains.integrations.router import router as integrations_router
from app.domains.labels.router import router as labels_router
from app.domains.macros.router import router as macros_router
from app.domains.notifications.router import (
    router as notifications_router,
)
from app.domains.notifications.router import (
    settings_router as notification_settings_router,
)
from app.domains.notifications.subscriptions_router import (
    router as notification_subscriptions_router,
)
from app.domains.portals.public_router import public_router as portals_public_router
from app.domains.portals.router import router as portals_router
from app.domains.products.router import router as products_router
from app.domains.reporting.router import (
    live_reports_router,
    summary_reports_router,
)
from app.domains.reporting.router import (
    router as reports_router,
)
from app.domains.sms_bandwidth.router import router as bandwidth_webhook_router
from app.domains.teams.router import router as teams_router
from app.domains.teams.router import team_members_router
from app.domains.telegram.router import router as telegram_webhook_router
from app.domains.twilio.router import router as twilio_webhook_router
from app.domains.uploads.public_router import router as public_media_router
from app.domains.uploads.router import router as uploads_router
from app.domains.users.router import router as profile_router
from app.domains.web_widget.router import router as web_widget_router
from app.domains.webhooks.router import router as outbound_webhooks_router
from app.domains.whatsapp.router import router as whatsapp_webhook_router
from app.domains.working_hours.router import (
    inbox_router as working_hours_inbox_router,
)
from app.domains.working_hours.router import (
    single_router as working_hours_single_router,
)
from app.mcp.router import router as mcp_tokens_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log = get_logger("app.lifespan")
    settings = get_settings()
    log.info("startup", env=settings.app_env)
    app.state.started_at = datetime.now(UTC)
    try:
        yield
    finally:
        await dispose_engine()
        # The realtime broadcaster's underlying ``redis.asyncio.Redis``
        # client is bound to the event loop active at first-use. Our
        # per-test fixture spins up a new loop each time, so we must
        # close+forget the singleton here to avoid "Future attached to
        # a different loop" on the next test.
        from app.core.realtime import reset_broadcaster

        await reset_broadcaster()
        log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.0.1",
        lifespan=lifespan,
    )
    # Controllers raise ChatwootHTTPException for error envelopes that
    # must match the Ruby ``render json: {...}`` body byte-for-byte —
    # i.e. unwrapped (no FastAPI ``"detail"`` key). See the docstring
    # on the marker class for context.
    app.add_exception_handler(
        ChatwootHTTPException, chatwoot_http_exception_handler  # type: ignore[arg-type]
    )
    # Request-id middleware (Phase 10.3) — reads/mints ``X-Request-Id``
    # and binds it onto the structured-log context so every log entry
    # carries the correlation id. Mirrors Rails'
    # ``ActionDispatch::RequestId``.
    from app.core.middleware import RequestIdMiddleware

    app.add_middleware(RequestIdMiddleware)
    app.include_router(health_router)
    app.include_router(accounts_router)
    app.include_router(auth_router)
    app.include_router(resend_confirmation_router)
    app.include_router(profile_router)
    app.include_router(inboxes_router)
    app.include_router(inbox_members_router)
    app.include_router(teams_router)
    app.include_router(team_members_router)
    app.include_router(contacts_router)
    app.include_router(contact_actions_router)
    app.include_router(conversations_router)
    app.include_router(conversations_messages_router)
    # Conversation participants — the agent "watcher" set (show/create/
    # update/destroy). A participant must be an assignable agent of the
    # conversation's inbox (inbox member or account admin).
    app.include_router(conversations_participants_router)
    app.include_router(bulk_actions_router)
    app.include_router(custom_attributes_router)
    # Saved views (``custom_filters``). Per-user named filter-DSL views;
    # any account member manages their own. Backs the conversation list's
    # "save this filter" affordance.
    app.include_router(custom_views_router)
    # Attachment uploads — mint a pre-signed direct-upload URL (MinIO/S3)
    # the dashboard composer PUTs the file to before sending the message.
    app.include_router(uploads_router)
    # Label CRUD (Phase 6.1). admin-only on writes; admin OR agent on
    # index. The Label model + ConversationLabel join landed in 4a so
    # ``update_labels`` could write through them — 6.1 promotes them
    # to a first-class CRUD surface and adds the rename cascade.
    app.include_router(labels_router)
    # CannedResponse CRUD (Phase 6.x). ``/short_code`` reply snippets any
    # account member manages; ``?search=`` ranks short_code prefix > substring
    # > content substring. Backs the composer's ``/`` quick-insert.
    app.include_router(canned_responses_router)
    # MCP token admin CRUD (own extension, not a Chatwoot mirror).
    # Account-scoped Bearer tokens consumed by the MCP server for AI
    # agents; this is the dashboard side admins use to manage them.
    app.include_router(mcp_tokens_router)
    # Macro CRUD + execute (Phase 6.2). Personal vs global visibility,
    # author/admin policy gates, ``POST /macros/:id/execute`` runs the
    # action plan against a given set of conversation_ids.
    app.include_router(macros_router)
    # AutomationRule CRUD + clone (Phase 6.3). Admin-only. The actual
    # listener wiring (which dispatcher event_name fires which rule)
    # lands in 6.4 — for now the model + condition evaluator + action
    # executor are exposed as a runnable surface that the listener can
    # plug into without further refactoring.
    app.include_router(automation_rules_router)
    # CSAT survey dashboard + public submit (Phase 6.5).
    # Dashboard: index + metrics (admin OR agent).
    # Public:    show + submit, keyed on the conversation UUID.
    app.include_router(csat_router)
    app.include_router(csat_public_router)
    # V2 reports surface (Phase 7.2-7.5). admin OR agent. Summary
    # cards, timeseries, live conversation metrics, per-entity summaries.
    app.include_router(reports_router)
    app.include_router(live_reports_router)
    app.include_router(summary_reports_router)
    # AgentBot CRUD (Phase 8.1). admin OR agent on read; admin-only on
    # writes + reset_secret. The inbox-side attach/detach lives under
    # ``/inboxes/{iid}/set_agent_bot`` per Chatwoot's member action.
    app.include_router(agent_bots_router)
    app.include_router(inbox_set_agent_bot_router)
    # Outbound Webhook CRUD (Phase 8.3). admin-only. Listener auto-
    # delivers subscribed events to each row's URL.
    app.include_router(outbound_webhooks_router)
    # Integration hooks scaffold (Phase 8.4). admin OR agent on read;
    # admin-only on writes. Per-vendor adapters (Slack/Dialogflow/etc.)
    # defer to vendor-specific follow-up commits.
    app.include_router(integrations_router)
    # Working hours (Phase 9.1). admin-only. Bulk schedule update
    # under the inbox + single-row update at the account level.
    # Powers Phase 7's value_in_business_hours math.
    app.include_router(working_hours_single_router)
    app.include_router(working_hours_inbox_router)
    # Help Center (Phase 9.3). admin-only. Portal + Category + Article
    # CRUD.
    app.include_router(portals_router)
    # Public Help Center surface (Phase 10.2) — no auth, slug-keyed,
    # only published articles surface.
    app.include_router(portals_public_router)
    # Campaigns (Phase 9.4). admin-only. CRUD only — scheduler runtime
    # (one_off fire on scheduled_at + ongoing widget triggers) defers
    # to Phase 10 hardening.
    app.include_router(campaigns_router)
    # Public widget surface (Phase 5a). Lives under ``/api/v1/widget``
    # — no devise auth, just the website_token + JWT scheme.
    app.include_router(web_widget_router)
    # WhatsApp webhook surface (Phase 5c). ``/webhooks/whatsapp/*``
    # — verify-token handshake (GET) + payload receive (POST). Auth
    # is per-channel via ``provider_config['webhook_verify_token']``.
    app.include_router(whatsapp_webhook_router)
    # Facebook Messenger webhook (Phase 5d). ``/webhooks/fb_messenger``
    # — installation-wide verify token via ``settings.fb_verify_token``
    # (env var FB_VERIFY_TOKEN), single endpoint shared across every
    # FB page.
    app.include_router(facebook_webhook_router)
    # Instagram DM webhook (Phase 5e). ``/webhooks/instagram`` —
    # installation-wide verify token via ``settings.ig_verify_token``
    # (env IG_VERIFY_TOKEN). Body must carry ``object: instagram``.
    app.include_router(instagram_webhook_router)
    # Instagram publishing surface (feat/instagram-graph I.2). admin-only.
    # Create/list/show posts; scheduling via ``scheduled_for``.
    app.include_router(instagram_publishing_router)
    # Instagram comment moderation (feat/instagram-graph I.7). admin-only.
    # List/post/reply/hide/delete comments on owned media.
    app.include_router(instagram_comments_router)
    # Instagram connection (feat/instagram-graph I.10). admin-only.
    # Manual/advanced connect (paste token) + channel capability view +
    # OAuth start. The OAuth callback is account-less (state-authed).
    app.include_router(instagram_connect_router)
    app.include_router(instagram_oauth_callback_router)
    # Product catalogue (feat/instagram-graph I.11). Account-scoped CRUD;
    # posts/stories link to products for AI/CRM context.
    app.include_router(products_router)
    # Twilio SMS webhook (Phase 5f). ``/twilio/callback`` —
    # form-encoded payload, channel resolved by MessagingServiceSid
    # then (AccountSid, To). Twilio's WhatsApp medium ships in 5f.6.
    app.include_router(twilio_webhook_router)
    # Bandwidth SMS webhook (Phase 5f). ``/webhooks/sms/{phone}`` —
    # JSON array payload, channel resolved by URL phone.
    app.include_router(bandwidth_webhook_router)
    # Telegram webhook (Phase 5g). ``/webhooks/telegram/{bot_token}``
    # — bot token in URL path acts as the credential, no verify-token
    # handshake. Body is a JSON Bot API Update object.
    app.include_router(telegram_webhook_router)
    # In-app notifications inbox (v2.5). Per-user rows produced by the
    # listener on CONVERSATION_CREATED / ASSIGNEE_CHANGED /
    # MESSAGE_CREATED; the bell badge polls /unread_count and the
    # cable channel emits notification.created for live updates.
    app.include_router(notifications_router)
    app.include_router(notification_settings_router)
    # Web-push subscriptions (RFC 8291) — the current user's browser push
    # endpoints + the VAPID public key the browser subscribes with.
    app.include_router(notification_subscriptions_router)
    # Assignment policies (auto-assignment config). admin-only CRUD +
    # the singular per-inbox link (one policy per inbox). Runtime
    # enforcement of the fair-distribution cap is a follow-up stage.
    app.include_router(assignment_policies_router)
    app.include_router(inbox_assignment_policy_router)
    # Authenticated media proxy — serves stored attachment bytes to the
    # dashboard (the object store is internal-only).
    app.include_router(attachments_router)
    # Signed, unauthenticated media links — Meta downloads outbound
    # attachments from its own side, so it can't use the proxy above.
    app.include_router(public_attachments_router)
    # Signed public links for post media — Meta fetches image_url/video_url
    # itself at publish time, which may be days after a scheduled upload.
    app.include_router(public_media_router)
    # ActionCable-compatible WebSocket endpoint (Phase 4b.2). Mounted
    # last so HTTP routes take precedence in any path-overlap edge.
    app.include_router(cable_router)
    return app


app = create_app()
