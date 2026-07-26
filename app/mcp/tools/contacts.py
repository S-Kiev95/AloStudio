"""MCP tools — contact operations.

Read + targeted custom_attribute writes. Phase 3's
``ContactIdentifyAction`` / ``ContactMergeAction`` are NOT exposed
here — those are admin-config flows that aren't typical agent
operations and would let an agent rewrite contact identity by
accident.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from sqlalchemy import or_
from sqlmodel import select

from app.domains.contacts.models import Contact
from app.domains.conversations.models import Conversation
from app.mcp.context import current_mcp_context
from app.mcp.permissions import requires


def _present(contact: Contact) -> dict[str, Any]:
    return {
        "id": contact.id,
        "name": contact.name,
        "email": contact.email,
        "phone_number": contact.phone_number,
        "identifier": contact.identifier,
        "blocked": contact.blocked,
        "additional_attributes": contact.additional_attributes or {},
        "custom_attributes": contact.custom_attributes or {},
        "created_at": (
            int(contact.created_at.timestamp())
            if contact.created_at
            else None
        ),
    }


async def _find_contact(contact_id: int) -> Contact:
    ctx = current_mcp_context()
    contact = await ctx.session.get(Contact, contact_id)
    if contact is None or contact.account_id != ctx.account.id:
        raise ValueError(
            f"contact {contact_id} not found in this account"
        )
    return contact


async def _find_conversation(conversation_id: int) -> Conversation:
    ctx = current_mcp_context()
    conv = await ctx.session.get(Conversation, conversation_id)
    if conv is None or conv.account_id != ctx.account.id:
        raise ValueError(
            f"conversation {conversation_id} not found in this account"
        )
    return conv


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="list_contacts")
    @requires("read")
    async def list_contacts(
        query: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> dict[str, Any]:
        """Search contacts by name / email / phone / identifier.

        ``query`` is matched case-insensitively against each of the
        four fields with ``ILIKE %query%`` (matches the dashboard's
        contact-search semantics). Without ``query`` returns the most
        recently active contacts.
        """
        ctx = current_mcp_context()
        per_page = min(max(1, per_page), 100)
        page = max(1, page)

        stmt = select(Contact).where(Contact.account_id == ctx.account.id)
        if query:
            needle = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    Contact.name.ilike(needle),
                    Contact.email.ilike(needle),  # type: ignore[union-attr]
                    Contact.phone_number.ilike(needle),  # type: ignore[union-attr]
                    Contact.identifier.ilike(needle),  # type: ignore[union-attr]
                )
            )
        stmt = stmt.order_by(
            Contact.last_activity_at.desc().nullslast(),  # type: ignore[union-attr]
            Contact.id.desc(),
        )
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        rows = list((await ctx.session.exec(stmt)).all())
        return {
            "page": page,
            "per_page": per_page,
            "contacts": [_present(c) for c in rows],
        }

    @mcp.tool(name="show_contact")
    @requires("read")
    async def show_contact(contact_id: int) -> dict[str, Any]:
        """Full contact payload."""
        contact = await _find_contact(contact_id)
        return _present(contact)

    @mcp.tool(name="set_contact_custom_attribute")
    @requires("write")
    async def set_contact_custom_attribute(
        contact_id: int,
        key: str,
        value: Any,
    ) -> dict[str, Any]:
        """Set a single key on ``contact.custom_attributes``.

        Pass ``value=null`` to remove the key. The JSONB column is
        merged in-place — other keys stay untouched.
        """
        if not isinstance(key, str) or not key.strip():
            raise ValueError("key can't be blank")
        contact = await _find_contact(contact_id)
        ctx = current_mcp_context()
        attrs = dict(contact.custom_attributes or {})
        if value is None:
            attrs.pop(key, None)
        else:
            attrs[key] = value
        contact.custom_attributes = attrs
        ctx.session.add(contact)
        await ctx.session.flush()
        return _present(contact)

    @mcp.tool(name="set_conversation_custom_attribute")
    @requires("write")
    async def set_conversation_custom_attribute(
        conversation_id: int,
        key: str,
        value: Any,
    ) -> dict[str, Any]:
        """Set a single key on ``conversation.custom_attributes``.

        Same shape as the contact-side tool but writes to the
        conversation's JSONB instead. Useful for an agent to stash
        per-conversation state ("intent_detected": "refund",
        "summary_generated": true).
        """
        if not isinstance(key, str) or not key.strip():
            raise ValueError("key can't be blank")
        conv = await _find_conversation(conversation_id)
        ctx = current_mcp_context()
        attrs = dict(conv.custom_attributes or {})
        if value is None:
            attrs.pop(key, None)
        else:
            attrs[key] = value
        conv.custom_attributes = attrs
        ctx.session.add(conv)
        await ctx.session.flush()
        return {
            "conversation_id": conv.id,
            "custom_attributes": attrs,
        }


__all__ = ["register"]
