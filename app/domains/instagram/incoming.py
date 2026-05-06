"""Instagram DM webhook payload processor.

5e.2 ships a stub. The real implementation lands with 5e.3 — it
walks the IG webhook payload (``entry[].messaging[]``, same shape
as Messenger) and creates Contact + Conversation + Message rows.
"""

from __future__ import annotations

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Message


async def process_instagram_webhook(
    session: AsyncSession,
    *,
    payload: dict[str, Any],
) -> list[Message]:
    """Stub for 5e.2 — no-op. 5e.3 fills it in."""
    return []


__all__ = ["process_instagram_webhook"]
