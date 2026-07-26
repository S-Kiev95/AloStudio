"""MCP tools — message operations.

The headline tool here is ``send_message`` — how an AI agent actually
replies. Goes through ``MessageBuilder`` so:
  * The post-create event cascade fires (reporting, AgentBot relay,
    webhooks).
  * Flooding cap is enforced.
  * Outbound channel routing kicks in (email, WhatsApp, Telegram,
    etc. — the message gets sent to the contact via the right
    transport).

``user_id`` for outgoing messages: when the MCP token has a bound
user, we sender_type=User + sender_id=that user. Otherwise the
message is sent without a sender (Chatwoot accepts this — shows as
"system" on the wire).
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from sqlmodel import select

from app.domains.conversations.models import (
    Conversation,
    Message,
    message_type_to_str,
)
from app.domains.conversations.service import (
    MessageBuilderParams,
    create_message,
)
from app.mcp.context import current_mcp_context
from app.mcp.permissions import requires


async def _find_conv(conversation_id: int) -> Conversation:
    ctx = current_mcp_context()
    conv = await ctx.session.get(Conversation, conversation_id)
    if conv is None or conv.account_id != ctx.account.id:
        raise ValueError(
            f"conversation {conversation_id} not found in this account"
        )
    return conv


async def _find_message(message_id: int) -> Message:
    ctx = current_mcp_context()
    msg = await ctx.session.get(Message, message_id)
    if msg is None or msg.account_id != ctx.account.id:
        raise ValueError(
            f"message {message_id} not found in this account"
        )
    return msg


def _present(msg: Message) -> dict[str, Any]:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "content": msg.content,
        "message_type": message_type_to_str(msg.message_type),
        "private": bool(msg.private),
        "sender_type": msg.sender_type,
        "sender_id": msg.sender_id,
        "content_attributes": msg.content_attributes or {},
        "additional_attributes": msg.additional_attributes or {},
        "source_id": msg.source_id,
        "created_at": (
            int(msg.created_at.timestamp()) if msg.created_at else None
        ),
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="list_messages")
    @requires("read")
    async def list_messages(
        conversation_id: int,
        before_id: int | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Paginate messages on a conversation, newest-first.

        Pass ``before_id`` to walk backward — for fetching a chunk
        older than the previous batch. Limit capped at 200.
        """
        conv = await _find_conv(conversation_id)
        ctx = current_mcp_context()
        limit = min(max(1, limit), 200)
        stmt = select(Message).where(Message.conversation_id == conv.id)
        if before_id is not None:
            stmt = stmt.where(Message.id < before_id)
        stmt = stmt.order_by(Message.id.desc()).limit(limit)
        rows = list((await ctx.session.exec(stmt)).all())
        return {
            "conversation_id": conv.id,
            "messages": [_present(m) for m in rows],
        }

    @mcp.tool(name="show_message")
    @requires("read")
    async def show_message(message_id: int) -> dict[str, Any]:
        """Read one message with full content_attributes."""
        msg = await _find_message(message_id)
        return _present(msg)

    @mcp.tool(name="send_message")
    @requires("write")
    async def send_message(
        conversation_id: int,
        content: str,
        private: bool = False,
    ) -> dict[str, Any]:
        """Reply to the conversation as the agent.

        With ``private=true`` becomes a private note (not visible to
        the contact — used for handoff comments). With
        ``private=false`` (default) the message is delivered to the
        contact via the conversation's channel (email, WhatsApp,
        Telegram, etc.) by the outbound listener cascade."""
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content can't be blank")
        conv = await _find_conv(conversation_id)
        ctx = current_mcp_context()
        msg = await create_message(
            ctx.session,
            conversation=conv,
            params=MessageBuilderParams(
                content=content,
                message_type="outgoing",
                private=private,
            ),
            user_id=ctx.user.id,
        )
        return _present(msg)

    @mcp.tool(name="add_private_note")
    @requires("write")
    async def add_private_note(
        conversation_id: int,
        content: str,
    ) -> dict[str, Any]:
        """Sugar for ``send_message(..., private=true)`` — pins the
        common "agent leaves a note for the human takeover" pattern."""
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content can't be blank")
        conv = await _find_conv(conversation_id)
        ctx = current_mcp_context()
        msg = await create_message(
            ctx.session,
            conversation=conv,
            params=MessageBuilderParams(
                content=content,
                message_type="outgoing",
                private=True,
            ),
            user_id=ctx.user.id,
        )
        return _present(msg)


__all__ = ["register"]
