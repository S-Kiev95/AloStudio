"""Calls' share of the 5-minute tick (F7)."""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.calls.service import expire_stale
from app.domains.calls.summary import summarize_pending
from app.domains.calls.whatsapp import retry_pending_media


async def run(session: AsyncSession) -> dict[str, int]:
    """Close calls whose end never came, and copy recordings and transcripts
    a first attempt could not (Meta deletes them after 7 days), and summarize
    the transcribed ones when the AI summary is on."""
    return {
        "closed": await expire_stale(session),
        "media_copied": await retry_pending_media(session),
        "summarized": await summarize_pending(session),
    }


__all__ = ["run"]
