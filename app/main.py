from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.db import dispose_engine
from app.core.logging import configure_logging, get_logger
from app.domains.accounts.router import router as accounts_router
from app.domains.auth.router import router as auth_router
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
    app.include_router(health_router)
    app.include_router(accounts_router)
    app.include_router(auth_router)
    app.include_router(profile_router)
    return app


app = create_app()
