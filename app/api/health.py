from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session

router = APIRouter(tags=["health"])


@router.get("/")
async def root() -> dict[str, str]:
    """Chatwoot returns a JSON object at `/` with version info — mirror that shape."""
    return {"version": "0.0.1", "timestamp": "", "queue_services": "ok", "data_services": "ok"}


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
