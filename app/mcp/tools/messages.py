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

from app.domains.conversations.message_search import search_messages
from app.domains.conversations.models import (
    Conversation,
    Message,
    message_type_to_str,
)
from app.domains.conversations.service import (
    MessageBuilderParams,
    _AttachmentSpec,
    create_message,
)
from app.domains.inboxes.models import (
    CHANNEL_TYPE_WHATSAPP,
    Inbox,
    WhatsappChannel,
)
from app.domains.whatsapp.template_processor import find_approved_template
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


_FILE_TYPES = frozenset({"image", "audio", "video", "file"})


def _attachment_specs(raw: list[dict[str, Any]] | None) -> list[_AttachmentSpec] | None:
    """``[{"url": "https://…", "file_type": "image"}]`` → message
    attachments. The URL has to be public: the channel (WhatsApp,
    Instagram…) downloads it from there."""
    if not raw:
        return None
    specs: list[_AttachmentSpec] = []
    for item in raw:
        url = str((item or {}).get("url") or "").strip()
        if not url.startswith("https://"):
            raise ValueError("each attachment needs a public https url")
        file_type = str(item.get("file_type") or "file")
        if file_type not in _FILE_TYPES:
            raise ValueError(f"file_type must be one of {sorted(_FILE_TYPES)}")
        specs.append(_AttachmentSpec(file_type=file_type, external_url=url))
    return specs


async def _whatsapp_channel(inbox_id: int) -> WhatsappChannel:
    ctx = current_mcp_context()
    inbox = await ctx.session.get(Inbox, inbox_id)
    if inbox is None or inbox.account_id != ctx.account.id:
        raise ValueError(f"inbox {inbox_id} not found in this account")
    if inbox.channel_type != CHANNEL_TYPE_WHATSAPP:
        raise ValueError(f"inbox {inbox_id} is not a WhatsApp inbox")
    channel = await ctx.session.get(WhatsappChannel, inbox.channel_id)
    if channel is None:
        raise ValueError(f"inbox {inbox_id} has no WhatsApp channel")
    return channel


def _body_text(template: dict[str, Any]) -> str:
    for component in template.get("components") or []:
        if isinstance(component, dict) and str(component.get("type")).upper() == "BODY":
            return str(component.get("text") or "")
    return ""


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

    @mcp.tool(name="search_messages")
    @requires("read")
    async def search_messages_tool(
        query: str,
        conversation_id: int | None = None,
        page: int = 1,
    ) -> dict[str, Any]:
        """Find messages by what they say, across every conversation or
        inside one.

        Accents and capitals are ignored, a word finds its other forms
        ("cuota" finds "cuotas"), a fragment is enough, and a typo of two
        swapped letters still matches. Accepts quotes for an exact phrase
        and ``-palabra`` to exclude one. Returns the matching messages with
        a snippet, the conversation, contact and date — 20 per page; ask
        for the next ``page`` while ``has_more`` is true. Then use
        ``list_messages`` on the conversation for the full context.
        ``conversation_id`` is the internal id, as everywhere in these
        tools.
        """
        ctx = current_mcp_context()
        display_id = None
        if conversation_id is not None:
            display_id = (await _find_conv(conversation_id)).display_id
        result = await search_messages(
            ctx.session,
            account_id=ctx.account.id,
            current_user_id=None,
            q=query,
            conversation_display_id=display_id,
            page=max(page, 1),
        )
        return {"messages": result["payload"], **result["meta"]}

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
        content: str | None = None,
        private: bool = False,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Reply to the conversation as the agent.

        With ``private=true`` becomes a private note (not visible to
        the contact — used for handoff comments). With
        ``private=false`` (default) the message is delivered to the
        contact via the conversation's channel (email, WhatsApp,
        Telegram, etc.) by the outbound listener cascade.

        ``attachments``: ``[{"url": "https://…", "file_type": "image"}]``
        (``image``, ``audio``, ``video`` or ``file``), public URLs; the
        text goes as the caption. On WhatsApp, outside the 24 h window use
        send_whatsapp_template instead."""
        specs = _attachment_specs(attachments)
        if not (isinstance(content, str) and content.strip()) and not specs:
            raise ValueError("content can't be blank")
        conv = await _find_conv(conversation_id)
        ctx = current_mcp_context()
        msg = await create_message(
            ctx.session,
            conversation=conv,
            params=MessageBuilderParams(
                content=content or "",
                message_type="outgoing",
                private=private,
                attachments=specs,
            ),
            user_id=ctx.user.id,
        )
        return _present(msg)

    @mcp.tool(name="list_whatsapp_templates")
    @requires("read")
    async def list_whatsapp_templates(inbox_id: int) -> dict[str, Any]:
        """Approved WhatsApp templates of a WhatsApp inbox: name, language,
        category, body text and how many ``{{n}}`` variables it takes. Only
        approved ones can be sent (send_whatsapp_template)."""
        channel = await _whatsapp_channel(inbox_id)
        templates = []
        for tpl in channel.message_templates or []:
            if not isinstance(tpl, dict) or str(tpl.get("status", "")).upper() != "APPROVED":
                continue
            body = _body_text(tpl)
            templates.append(
                {
                    "name": tpl.get("name"),
                    "language": tpl.get("language"),
                    "category": tpl.get("category"),
                    "body": body,
                    "variables": body.count("{{"),
                }
            )
        return {"inbox_id": inbox_id, "templates": templates}

    @mcp.tool(name="send_whatsapp_template")
    @requires("write")
    async def send_whatsapp_template(
        conversation_id: int,
        name: str,
        language: str,
        body_params: list[str] | None = None,
    ) -> dict[str, Any]:
        """Send an approved WhatsApp template (list_whatsapp_templates) on a
        WhatsApp conversation. It is the only way to write to a contact who
        has not written in the last 24 h. ``body_params`` fill ``{{1}}``,
        ``{{2}}``… in order. Meta charges each template it delivers."""
        conv = await _find_conv(conversation_id)
        channel = await _whatsapp_channel(conv.inbox_id)
        template = find_approved_template(channel.message_templates, name, language)
        if template is None:
            raise ValueError(
                f"no approved template {name!r} in {language!r}; see list_whatsapp_templates"
            )
        params = [str(p) for p in body_params or []]
        body = _body_text(template)
        if body.count("{{") != len(params):
            raise ValueError(
                f"template {name!r} takes {body.count('{{')} body params, got {len(params)}"
            )
        text = body
        for position, value in enumerate(params, start=1):
            text = text.replace(f"{{{{{position}}}}}", value)
        ctx = current_mcp_context()
        msg = await create_message(
            ctx.session,
            conversation=conv,
            params=MessageBuilderParams(
                content=text or name,
                message_type="outgoing",
                template_params={
                    "name": name,
                    "language": language,
                    "processed_params": {
                        "body": {str(i): v for i, v in enumerate(params, start=1)}
                    },
                },
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
