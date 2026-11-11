"""MCP tools — conversation operations.

Each tool wraps the underlying service-layer function from
:mod:`app.domains.conversations`. Account scope is taken from the
authenticated :class:`MCPContext` — tools never accept account_id as
an argument so an agent can't cross-tenant by mistake.

Permission scopes (mirrors :class:`MCPScope`):

  * **read**  — list / show / get_ai_mode
  * **write** — resolve / reopen / assign_* / change_* / add_label /
                remove_label / set_ai_mode
  * **admin** — none in this module (reserved for tools that mutate
                global account state — labels CRUD, agent_bot admin,
                etc.)
"""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP
from sqlmodel import select

from app.core.errors import ChatwootHTTPException
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.events import (
    CONVERSATION_UPDATED,
    dispatcher,
)
from app.domains.conversations.models import (
    CONVERSATION_STATUS_OPEN,
    Conversation,
    Message,
    conversation_priority_to_str,
    conversation_status_to_str,
    message_type_to_str,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    create_message,
    toggle_priority,
    toggle_status,
    update_assignee,
    update_labels,
    update_team,
)
from app.domains.conversations.service import (
    create_conversation as build_conversation,
)
from app.domains.inboxes.models import (
    CHANNEL_TYPE_API,
    CHANNEL_TYPE_EMAIL,
    CHANNEL_TYPE_WEB_WIDGET,
    CHANNEL_TYPE_WHATSAPP,
    Inbox,
)
from app.domains.teams.models import Team
from app.mcp.context import current_mcp_context
from app.mcp.permissions import requires


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _find_conversation(conversation_id: int) -> Conversation:
    """Locate a conversation within the active account's scope.

    Raises a tool-friendly ``ValueError`` (which FastMCP renders as a
    user-facing tool error) when not found / cross-account."""
    ctx = current_mcp_context()
    conv = await ctx.session.get(Conversation, conversation_id)
    if conv is None or conv.account_id != ctx.account.id:
        raise ValueError(
            f"conversation {conversation_id} not found in this account"
        )
    return conv


def _present_conv(conv: Conversation) -> dict[str, Any]:
    """Compact wire shape — tools that need every field can call
    ``show_conversation`` to get the message tail too."""
    return {
        "id": conv.id,
        "display_id": conv.display_id,
        "status": conversation_status_to_str(conv.status),
        "priority": conversation_priority_to_str(conv.priority),
        "assignee_id": conv.assignee_id,
        "team_id": conv.team_id,
        "inbox_id": conv.inbox_id,
        "contact_id": conv.contact_id,
        "labels": [
            t.strip()
            for t in (conv.cached_label_list or "").split(",")
            if t.strip()
        ],
        "additional_attributes": conv.additional_attributes or {},
        "created_at": (
            int(conv.created_at.timestamp()) if conv.created_at else None
        ),
    }


def _present_msg(msg: Message) -> dict[str, Any]:
    return {
        "id": msg.id,
        "content": msg.content,
        "message_type": message_type_to_str(msg.message_type),
        "private": bool(msg.private),
        "sender_type": msg.sender_type,
        "sender_id": msg.sender_id,
        "created_at": (
            int(msg.created_at.timestamp()) if msg.created_at else None
        ),
    }


# ===========================================================================
# Tools
# ===========================================================================
# Channels where AloStudio can write first: the address comes from the
# contact itself. Everywhere else (Instagram, Messenger, Telegram, SMS) the
# platform only lets a business answer someone who wrote before.
_STARTABLE = frozenset(
    {CHANNEL_TYPE_API, CHANNEL_TYPE_WEB_WIDGET, CHANNEL_TYPE_EMAIL}
)


async def _contact_inbox_for(contact: Contact, inbox: Inbox) -> ContactInbox:
    """The contact's address in this inbox: the existing one if they wrote
    before, else a new one where the channel allows writing first."""
    ctx = current_mcp_context()
    existing = (
        await ctx.session.exec(
            select(ContactInbox).where(
                ContactInbox.contact_id == contact.id,
                ContactInbox.inbox_id == inbox.id,
            )
        )
    ).first()
    if existing is not None:
        return existing
    source_id: str | None = None
    if inbox.channel_type == CHANNEL_TYPE_WHATSAPP:
        digits = "".join(ch for ch in contact.phone_number or "" if ch.isdigit())
        if not digits:
            raise ValueError(
                "the contact has no phone number; set it with update_contact first"
            )
        source_id = digits
    elif inbox.channel_type not in _STARTABLE:
        raise ValueError(
            "this channel only allows answering a contact who wrote first; "
            "this contact has no conversation in that inbox"
        )
    if inbox.channel_type == CHANNEL_TYPE_EMAIL and not contact.email:
        raise ValueError("the contact has no email; set it with update_contact first")
    return await ContactInboxBuilder(
        session=ctx.session, contact=contact, inbox=inbox, source_id=source_id
    ).perform()


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="list_conversations")
    @requires("read")
    async def list_conversations(
        status: Literal["open", "resolved", "pending", "snoozed"]
        | None = None,
        assignee_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> dict[str, Any]:
        """List conversations on the current account.

        Filters: ``status`` (default ``open``), ``assignee_id``.
        Paginated (``per_page`` capped at 100). Returns the most
        recently active conversations first.
        """
        ctx = current_mcp_context()
        per_page = min(max(1, per_page), 100)
        page = max(1, page)

        stmt = select(Conversation).where(
            Conversation.account_id == ctx.account.id
        )
        # Default to ``open`` when caller doesn't specify — matches
        # the dashboard's default filter.
        if status is None:
            stmt = stmt.where(
                Conversation.status == CONVERSATION_STATUS_OPEN
            )
        else:
            from app.domains.conversations.models import (
                conversation_status_from_str,
            )

            stmt = stmt.where(
                Conversation.status
                == conversation_status_from_str(status)
            )
        if assignee_id is not None:
            stmt = stmt.where(Conversation.assignee_id == assignee_id)

        stmt = stmt.order_by(
            Conversation.last_activity_at.desc().nullslast(),
            Conversation.id.desc(),
        )
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        rows = list((await ctx.session.exec(stmt)).all())
        return {
            "page": page,
            "per_page": per_page,
            "conversations": [_present_conv(c) for c in rows],
        }

    @mcp.tool(name="show_conversation")
    @requires("read")
    async def show_conversation(
        conversation_id: int,
        message_tail: int = 10,
    ) -> dict[str, Any]:
        """Read one conversation plus the N most recent messages.

        ``message_tail`` capped at 50."""
        conv = await _find_conversation(conversation_id)
        ctx = current_mcp_context()
        tail = min(max(0, message_tail), 50)
        msgs: list[Message] = []
        if tail > 0:
            stmt = (
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.id.desc())
                .limit(tail)
            )
            msgs = list((await ctx.session.exec(stmt)).all())
            msgs.reverse()  # chronological for the agent's prompt
        return {
            **_present_conv(conv),
            "messages": [_present_msg(m) for m in msgs],
        }

    @mcp.tool(name="resolve_conversation")
    @requires("write")
    async def resolve_conversation(
        conversation_id: int,
    ) -> dict[str, Any]:
        """Mark a conversation as resolved (fires the post-create
        cascade — CSAT survey, reporting events, listeners)."""
        conv = await _find_conversation(conversation_id)
        ctx = current_mcp_context()
        await toggle_status(
            ctx.session, conversation=conv, status="resolved"
        )
        return _present_conv(conv)

    @mcp.tool(name="reopen_conversation")
    @requires("write")
    async def reopen_conversation(
        conversation_id: int,
    ) -> dict[str, Any]:
        """Flip a resolved / snoozed / pending conversation back to
        ``open``."""
        conv = await _find_conversation(conversation_id)
        ctx = current_mcp_context()
        await toggle_status(
            ctx.session, conversation=conv, status="open"
        )
        return _present_conv(conv)

    @mcp.tool(name="change_status")
    @requires("write")
    async def change_status(
        conversation_id: int,
        status: Literal["open", "resolved", "pending", "snoozed"],
    ) -> dict[str, Any]:
        """Set the conversation status explicitly. Use ``snoozed``
        only with a ``snoozed_until`` follow-up (not exposed here —
        agents typically don't snooze; they resolve or hand off)."""
        conv = await _find_conversation(conversation_id)
        ctx = current_mcp_context()
        await toggle_status(
            ctx.session, conversation=conv, status=status
        )
        return _present_conv(conv)

    @mcp.tool(name="change_priority")
    @requires("write")
    async def change_priority(
        conversation_id: int,
        priority: Literal["low", "medium", "high", "urgent", "none"],
    ) -> dict[str, Any]:
        """Change priority. ``none`` clears the field."""
        conv = await _find_conversation(conversation_id)
        ctx = current_mcp_context()
        priority_arg: str | None = None if priority == "none" else priority
        await toggle_priority(
            ctx.session, conversation=conv, priority=priority_arg
        )
        return _present_conv(conv)

    @mcp.tool(name="create_conversation")
    @requires("write")
    async def create_conversation(
        inbox_id: int,
        contact_id: int,
        message: str | None = None,
        assignee_id: int | None = None,
        team_id: int | None = None,
    ) -> dict[str, Any]:
        """Start a conversation with a contact in an inbox (list_inboxes,
        list_contacts), optionally with a first message and an assignee or
        team (list_agents, list_teams).

        On WhatsApp, Meta refuses free text when the contact has not
        written in the last 24 h: start without ``message`` and send an
        approved template with send_whatsapp_template."""
        ctx = current_mcp_context()
        inbox = await ctx.session.get(Inbox, inbox_id)
        if inbox is None or inbox.account_id != ctx.account.id:
            raise ValueError(f"inbox {inbox_id} not found in this account")
        contact = await ctx.session.get(Contact, contact_id)
        if contact is None or contact.account_id != ctx.account.id:
            raise ValueError(f"contact {contact_id} not found in this account")
        if team_id is not None:
            team = await ctx.session.get(Team, team_id)
            if team is None or team.account_id != ctx.account.id:
                raise ValueError(f"team {team_id} not found in this account")

        contact_inbox = await _contact_inbox_for(contact, inbox)
        conv = await build_conversation(
            ctx.session,
            contact_inbox=contact_inbox,
            params=ConversationBuilderParams(),
        )
        if assignee_id is not None and (
            await update_assignee(
                ctx.session, conversation=conv, assignee_id=assignee_id
            )
            is None
        ):
            raise ValueError(f"agent {assignee_id} not found in this account")
        if team_id is not None:
            await update_team(ctx.session, conversation=conv, team_id=team_id)
        if message and message.strip():
            await create_message(
                ctx.session,
                conversation=conv,
                params=MessageBuilderParams(
                    content=message, message_type="outgoing"
                ),
                user_id=ctx.user.id,
            )
        return _present_conv(conv)

    @mcp.tool(name="assign_agent")
    @requires("write")
    async def assign_agent(
        conversation_id: int,
        agent_id: int | None,
    ) -> dict[str, Any]:
        """Assign a human agent (or pass ``null`` to unassign).

        Typical use: an AI agent decides it can't handle the
        conversation and calls this to route to a human."""
        conv = await _find_conversation(conversation_id)
        ctx = current_mcp_context()
        try:
            await update_assignee(
                ctx.session, conversation=conv, assignee_id=agent_id
            )
        except ChatwootHTTPException as exc:
            raise ValueError(exc.detail) from exc
        return _present_conv(conv)

    @mcp.tool(name="assign_team")
    @requires("write")
    async def assign_team(
        conversation_id: int,
        team_id: int | None,
    ) -> dict[str, Any]:
        """Route to a team. ``null`` clears the team."""
        conv = await _find_conversation(conversation_id)
        ctx = current_mcp_context()
        await update_team(
            ctx.session, conversation=conv, team_id=team_id
        )
        return _present_conv(conv)

    @mcp.tool(name="add_label")
    @requires("write")
    async def add_label(
        conversation_id: int,
        labels: list[str],
    ) -> dict[str, Any]:
        """Append labels (titles, lowercased internally) without
        removing existing ones."""
        conv = await _find_conversation(conversation_id)
        ctx = current_mcp_context()
        existing = [
            t.strip()
            for t in (conv.cached_label_list or "").split(",")
            if t.strip()
        ]
        merged = existing + [t for t in labels if t not in existing]
        await update_labels(
            ctx.session, conversation=conv, titles=merged
        )
        return _present_conv(conv)

    @mcp.tool(name="remove_label")
    @requires("write")
    async def remove_label(
        conversation_id: int,
        labels: list[str],
    ) -> dict[str, Any]:
        """Drop the given labels (silently no-op for missing)."""
        conv = await _find_conversation(conversation_id)
        ctx = current_mcp_context()
        existing = [
            t.strip()
            for t in (conv.cached_label_list or "").split(",")
            if t.strip()
        ]
        keep = [t for t in existing if t not in set(labels)]
        await update_labels(
            ctx.session, conversation=conv, titles=keep
        )
        return _present_conv(conv)

    @mcp.tool(name="get_ai_mode")
    @requires("read")
    async def get_ai_mode(conversation_id: int) -> dict[str, Any]:
        """Read the AI takeover flag from the conversation.

        Returns ``ai_mode`` (bool, default ``false`` = human-controlled)
        plus the optional ``ai_assignee`` string an agent stamped on
        takeover (e.g. ``"alicia-v3"``). Both come from real columns
        added in migration ``c2d3e4f5a6b7``; pre-existing rows default
        to off via the ``server_default``.
        """
        conv = await _find_conversation(conversation_id)
        return {
            "conversation_id": conv.id,
            "ai_mode": bool(conv.ai_mode),
            "ai_assignee": conv.ai_assignee,
        }

    @mcp.tool(name="set_ai_mode")
    @requires("write")
    async def set_ai_mode(
        conversation_id: int,
        on: bool,
        ai_assignee: str | None = None,
    ) -> dict[str, Any]:
        """Flip the AI takeover flag.

        Setting ``on=true`` is the AI agent's way of telling the platform
        "I've got this — please don't fire automation rules on top of me."
        Setting ``on=false`` hands the conversation back to the human
        agents and re-enables the normal automation cascade.

        ``ai_assignee`` is a free-form identifier the agent stamps on
        takeover (e.g. ``"alicia-v3"``) so the dashboard can show which
        AI is on duty. Clearing the field requires passing the empty
        string (``""``) — passing ``None`` leaves the existing value
        untouched, which matches PATCH-merge semantics elsewhere.

        Dispatches ``conversation.updated`` with a ``changed_attributes``
        diff so the cable layer invalidates the conversation cache on
        every connected human dashboard.
        """
        conv = await _find_conversation(conversation_id)
        ctx = current_mcp_context()
        prev_mode = bool(conv.ai_mode)
        prev_assignee = conv.ai_assignee
        conv.ai_mode = bool(on)
        if ai_assignee is not None:
            # Empty string clears the slot; non-empty stamps the new owner.
            conv.ai_assignee = ai_assignee or None
        ctx.session.add(conv)
        await ctx.session.flush()

        # Only emit when something actually changed — avoids cable churn
        # when an agent re-asserts its existing claim.
        changed: dict[str, Any] = {}
        if prev_mode != conv.ai_mode:
            changed["ai_mode"] = [prev_mode, conv.ai_mode]
        if prev_assignee != conv.ai_assignee:
            changed["ai_assignee"] = [prev_assignee, conv.ai_assignee]
        if changed:
            await dispatcher.dispatch(
                ctx.session,
                CONVERSATION_UPDATED,
                conversation=conv,
                changed_attributes=changed,
            )

        return {
            "conversation_id": conv.id,
            "ai_mode": bool(conv.ai_mode),
            "ai_assignee": conv.ai_assignee,
        }


__all__ = ["register"]
