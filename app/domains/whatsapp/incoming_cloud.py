"""WhatsApp Cloud webhook payload processor.

5c.2 ships a stub so the router can call it unconditionally without
guarding on import. The real implementation lands with 5c.3 — it
parses the Meta payload (``entry[0].changes[0].value.messages[]``)
into Contact + Conversation + Message rows.

The stub silently no-ops: returning ``[]`` lets the webhook
acknowledge the payload (Meta retries 5xx but accepts 200), so we
get the right wire behaviour the moment the agent installs the
webhook even if 5c.3 hasn't shipped yet.
"""

from __future__ import annotations

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.conversations.models import Message
from app.domains.inboxes.models import Inbox, WhatsappChannel


async def process_cloud_webhook(
    session: AsyncSession,
    *,
    channel: WhatsappChannel,
    inbox: Inbox,
    payload: dict[str, Any],
) -> list[Message]:
    """Stub for 5c.2 — no-op. 5c.3 fills it in."""
    return []


__all__ = ["process_cloud_webhook"]
