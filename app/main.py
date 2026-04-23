from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from app.api.health import router as health_router
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
    return app


app = create_app()
