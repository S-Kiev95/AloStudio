"""MCP tools — campaigns (one-off sends to a list of contacts).

A one-off campaign sends one message to each contact of its audience at
``scheduled_at`` (the scheduler runs every 5 minutes). On WhatsApp the
message must be an approved template: outside the 24 h window Meta refuses
free text.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from sqlmodel import col, select

from app.domains.campaigns import service as campaign_service
from app.domains.campaigns.presenters import present_campaign
from app.domains.contacts.models import Contact
from app.domains.inboxes.models import CHANNEL_TYPE_WHATSAPP, Inbox
from app.mcp.context import current_mcp_context
from app.mcp.permissions import requires


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="list_campaigns")
    @requires("read")
    async def list_campaigns() -> dict[str, Any]:
        """The account's campaigns with their state (pending / completed),
        inbox, audience and schedule. ``id`` is the one the other campaign
        tools take."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        rows = await campaign_service.list_campaigns(ctx.session, account_id=ctx.account.id)
        return {"campaigns": [present_campaign(c) for c in rows]}

    @mcp.tool(name="create_campaign")
    @requires("write")
    async def create_campaign(
        title: str,
        inbox_id: int,
        contact_ids: list[int],
        message: str,
        scheduled_at: str,
        template_name: str | None = None,
        template_language: str | None = None,
        template_params: list[str] | None = None,
    ) -> dict[str, Any]:
        """Schedule a one-off campaign: ``message`` to each contact in
        ``contact_ids`` through ``inbox_id`` at ``scheduled_at`` (ISO 8601).

        On a WhatsApp inbox pass an approved template too
        (list_whatsapp_templates): ``template_name``, ``template_language``
        and ``template_params`` for its ``{{1}}``, ``{{2}}``… Meta charges
        each template delivered."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        if not contact_ids:
            raise ValueError("contact_ids can't be empty")
        inbox = await ctx.session.get(Inbox, inbox_id)
        if inbox is None or inbox.account_id != ctx.account.id:
            raise ValueError(f"inbox {inbox_id} not found in this account")
        wanted = set(contact_ids)
        rows = (
            await ctx.session.exec(
                select(Contact.id).where(
                    Contact.account_id == ctx.account.id,
                    col(Contact.id).in_(wanted),
                )
            )
        ).all()
        found = {cid for cid in rows if cid is not None}
        if missing := sorted(wanted - found):
            raise ValueError(f"contacts not found in this account: {missing}")

        template: dict[str, Any] | None = None
        if inbox.channel_type == CHANNEL_TYPE_WHATSAPP:
            if not (template_name and template_language):
                raise ValueError(
                    "a WhatsApp campaign needs an approved template "
                    "(template_name and template_language)"
                )
            template = {
                "name": template_name,
                "language": template_language,
                "processed_params": {
                    "body": {
                        str(i): str(v) for i, v in enumerate(template_params or [], start=1)
                    }
                },
            }

        campaign = await campaign_service.create_campaign(
            ctx.session,
            account_id=ctx.account.id,
            payload={
                "title": title,
                "message": message,
                "inbox_id": inbox_id,
                "campaign_type": "one_off",
                "scheduled_at": scheduled_at,
                "audience": [{"type": "Contact", "id": cid} for cid in sorted(found)],
                "sender_id": ctx.user.id,
                "template_params": template,
            },
        )
        return present_campaign(campaign)

    @mcp.tool(name="get_campaign_result")
    @requires("read")
    async def get_campaign_result(campaign_id: int) -> dict[str, Any]:
        """Delivery figures of a campaign: messages sent, delivered, read,
        failed and replies."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        campaign = await campaign_service.fetch_campaign_by_display_id(
            ctx.session, account_id=ctx.account.id, display_id=campaign_id
        )
        if campaign is None:
            raise ValueError(f"campaign {campaign_id} not found in this account")
        return {
            "campaign": present_campaign(campaign),
            "result": await campaign_service.campaign_analytics(
                ctx.session, campaign=campaign
            ),
        }


__all__ = ["register"]
