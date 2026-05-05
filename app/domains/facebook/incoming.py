"""Facebook Messenger webhook payload processor.

5d.2 ships a stub. The real implementation lands with 5d.3 — it
walks ``entry[].messaging[]`` and creates Contact + Conversation +
Message rows.

The stub returning ``[]`` lets the receiver acknowledge the payload
(Meta retries on 5xx but accepts 2xx) so we get the right wire
behaviour the moment the agent installs the webhook even before
5d.3 ships.
"""

from __future__ import annotations

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Message


async def process_facebook_webhook(
    session: AsyncSession,
    *,
    payload: dict[str, Any],
) -> list[Message]:
    """Stub for 5d.2 — no-op. 5d.3 fills it in."""
    return []


__all__ = ["process_facebook_webhook"]
