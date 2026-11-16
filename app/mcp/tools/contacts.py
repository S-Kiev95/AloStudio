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

from app.domains.contacts import service as contact_service
from app.domains.contacts.models import Contact
from app.domains.contacts.service import contact_snapshot, dispatch_contact_updated
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

    @mcp.tool(name="create_contact")
    @requires("write")
    async def create_contact(
        name: str,
        email: str | None = None,
        phone_number: str | None = None,
        identifier: str | None = None,
        custom_attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a contact. ``phone_number`` in international format
        (``+59899123456``). Email, phone and identifier are unique within the
        account: a duplicate is refused, so search with list_contacts first."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name can't be blank")
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        payload: dict[str, Any] = {"name": name.strip()}
        for key, value in (
            ("email", email),
            ("phone_number", phone_number),
            ("identifier", identifier),
            ("custom_attributes", custom_attributes),
        ):
            if value is not None:
                payload[key] = value
        contact = await contact_service.create_contact(
            ctx.session, account_id=ctx.account.id, payload=payload
        )
        return _present(contact)

    @mcp.tool(name="update_contact")
    @requires("write")
    async def update_contact(
        contact_id: int,
        name: str | None = None,
        email: str | None = None,
        phone_number: str | None = None,
        identifier: str | None = None,
    ) -> dict[str, Any]:
        """Change a contact's name, email, phone or identifier; fields left
        out stay as they are. For custom attributes use
        set_contact_custom_attribute."""
        contact = await _find_contact(contact_id)
        ctx = current_mcp_context()
        payload = {
            key: value
            for key, value in (
                ("name", name),
                ("email", email),
                ("phone_number", phone_number),
                ("identifier", identifier),
            )
            if value is not None
        }
        if not payload:
            raise ValueError("nothing to update")
        contact = await contact_service.update_contact(
            ctx.session, contact=contact, payload=payload
        )
        return _present(contact)

    @mcp.tool(name="merge_contacts")
    @requires("admin")
    async def merge_contacts(base_contact_id: int, mergee_contact_id: int) -> dict[str, Any]:
        """Merge a duplicate into another contact of the account: the
        ``mergee``'s conversations, notes and addresses move to the
        ``base`` and the ``mergee`` is deleted. Not reversible."""
        if base_contact_id == mergee_contact_id:
            raise ValueError("can't merge a contact with itself")
        base = await _find_contact(base_contact_id)
        mergee = await _find_contact(mergee_contact_id)
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        merged = await contact_service.ContactMergeAction(
            session=ctx.session, account_id=ctx.account.id, base=base, mergee=mergee
        ).perform()
        return _present(merged)

    @mcp.tool(name="set_contact_blocked")
    @requires("admin")
    async def set_contact_blocked(contact_id: int, blocked: bool) -> dict[str, Any]:
        """Mark a contact as blocked or unblocked: the same flag as muting
        a conversation in the inbox. It does not delete anything."""
        contact = await _find_contact(contact_id)
        ctx = current_mcp_context()
        contact = await contact_service.update_contact(
            ctx.session, contact=contact, payload={"blocked": blocked}
        )
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
        before = contact_snapshot(contact)
        attrs = dict(contact.custom_attributes or {})
        if value is None:
            attrs.pop(key, None)
        else:
            attrs[key] = value
        contact.custom_attributes = attrs
        ctx.session.add(contact)
        await ctx.session.flush()
        await dispatch_contact_updated(ctx.session, contact, before)
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
