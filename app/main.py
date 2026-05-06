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
from app.domains.auth.router import resend_confirmation_router
from app.domains.auth.router import router as auth_router
from app.domains.contacts.router import actions_router as contact_actions_router
from app.domains.contacts.router import router as contacts_router
from app.domains.conversations.router import messages_router as conversations_messages_router
from app.domains.conversations.router import router as conversations_router
from app.domains.custom_attributes.router import router as custom_attributes_router
from app.domains.inboxes.router import inbox_members_router
from app.domains.inboxes.router import router as inboxes_router
from app.domains.teams.router import router as teams_router
from app.domains.teams.router import team_members_router
from app.domains.users.router import router as profile_router
from app.domains.facebook.router import router as facebook_webhook_router
from app.domains.instagram.router import router as instagram_webhook_router
from app.domains.web_widget.router import router as web_widget_router
from app.domains.whatsapp.router import router as whatsapp_webhook_router


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
    app.include_router(custom_attributes_router)
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
    # ActionCable-compatible WebSocket endpoint (Phase 4b.2). Mounted
    # last so HTTP routes take precedence in any path-overlap edge.
    app.include_router(cable_router)
    return app


app = create_app()
