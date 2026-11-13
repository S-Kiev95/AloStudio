"""MCP tools — CRM sales pipeline (F11): pipelines, opportunities and
activities (tasks, calls, meetings, emails).

The CRM services check that every referenced contact, product,
conversation, stage and owner belongs to the token's account; these tools
only wrap them. An opportunity moves through the pipeline by changing its
``stage_id``; a stage of kind won or lost closes it.
"""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from app.domains.crm import activities as activity_service
from app.domains.crm import service as crm_service
from app.domains.crm.presenters import (
    present_activities,
    present_opportunities,
    present_pipeline,
)
from app.mcp.context import current_mcp_context
from app.mcp.permissions import requires


def _set_fields(**values: Any) -> dict[str, Any]:
    return {k: v for k, v in values.items() if v is not None}


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="list_pipelines")
    @requires("read")
    async def list_pipelines() -> dict[str, Any]:
        """Sales pipelines with their stages in order (each stage: id, name,
        kind open/won/lost). Use a stage id in create_opportunity and to
        move one with update_opportunity."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        pipelines = await crm_service.list_pipelines(ctx.session, account_id=ctx.account.id)
        stages = await crm_service.stages_for(
            ctx.session, [p.id for p in pipelines if p.id is not None]
        )
        return {"pipelines": [present_pipeline(p, stages) for p in pipelines]}

    @mcp.tool(name="list_opportunities")
    @requires("read")
    async def list_opportunities(
        pipeline_id: int | None = None,
        contact_id: int | None = None,
        owner_id: int | None = None,
        status: Literal["open", "won", "lost"] | None = None,
        query: str | None = None,
    ) -> dict[str, Any]:
        """Opportunities (deals) of the account, filtered by pipeline,
        contact, owner, status or a text ``query`` in the title."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        rows = await crm_service.list_opportunities(
            ctx.session,
            account_id=ctx.account.id,
            pipeline_id=pipeline_id,
            contact_id=contact_id,
            owner_id=owner_id,
            status=status,
            q=query,
            company_id=None,
        )
        return {"opportunities": await present_opportunities(ctx.session, rows)}

    @mcp.tool(name="create_opportunity")
    @requires("write")
    async def create_opportunity(
        title: str,
        contact_id: int | None = None,
        stage_id: int | None = None,
        value: float | None = None,
        currency: str | None = None,
        product_id: int | None = None,
        conversation_id: int | None = None,
        expected_close_on: str | None = None,
        description: str | None = None,
        owner_id: int | None = None,
    ) -> dict[str, Any]:
        """Open an opportunity, for example a lead that came in a
        conversation. Without ``stage_id`` it goes to the first stage of the
        first pipeline; without ``owner_id`` the token's user works it.
        ``expected_close_on`` is a date (YYYY-MM-DD)."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        payload = _set_fields(
            title=title,
            contact_id=contact_id,
            stage_id=stage_id,
            value=value,
            currency=currency,
            product_id=product_id,
            conversation_id=conversation_id,
            expected_close_on=expected_close_on,
            description=description,
        )
        payload["owner_id"] = owner_id if owner_id is not None else ctx.user.id
        row = await crm_service.save_opportunity(
            ctx.session, account_id=ctx.account.id, opportunity=None, payload=payload
        )
        return (await present_opportunities(ctx.session, [row]))[0]

    @mcp.tool(name="update_opportunity")
    @requires("write")
    async def update_opportunity(
        opportunity_id: int,
        stage_id: int | None = None,
        title: str | None = None,
        value: float | None = None,
        currency: str | None = None,
        expected_close_on: str | None = None,
        description: str | None = None,
        owner_id: int | None = None,
        lost_reason: str | None = None,
    ) -> dict[str, Any]:
        """Move an opportunity to another stage (``stage_id``; a won or lost
        stage closes it, with ``lost_reason`` when lost) or change its
        details. Fields left out stay as they are."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        row = await crm_service.get_opportunity(
            ctx.session, account_id=ctx.account.id, opportunity_id=opportunity_id
        )
        if row is None:
            raise ValueError(f"opportunity {opportunity_id} not found in this account")
        payload = _set_fields(
            stage_id=stage_id,
            title=title,
            value=value,
            currency=currency,
            expected_close_on=expected_close_on,
            description=description,
            owner_id=owner_id,
            lost_reason=lost_reason,
        )
        if not payload:
            raise ValueError("nothing to update")
        row = await crm_service.save_opportunity(
            ctx.session, account_id=ctx.account.id, opportunity=row, payload=payload
        )
        return (await present_opportunities(ctx.session, [row]))[0]

    @mcp.tool(name="list_crm_activities")
    @requires("read")
    async def list_crm_activities(
        owner_id: int | None = None,
        contact_id: int | None = None,
        opportunity_id: int | None = None,
        status: Literal["pending", "overdue", "done"] | None = None,
    ) -> dict[str, Any]:
        """Follow-ups (tasks, calls, meetings, emails), filtered by owner,
        contact, opportunity or status."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        rows = await activity_service.list_activities(
            ctx.session,
            account_id=ctx.account.id,
            owner_id=owner_id,
            contact_id=contact_id,
            opportunity_id=opportunity_id,
            status=status,
        )
        return {"activities": await present_activities(ctx.session, rows)}

    @mcp.tool(name="create_crm_activity")
    @requires("write")
    async def create_crm_activity(
        title: str,
        kind: Literal["task", "call", "meeting", "email"] = "task",
        due_at: str | None = None,
        contact_id: int | None = None,
        opportunity_id: int | None = None,
        description: str | None = None,
        owner_id: int | None = None,
    ) -> dict[str, Any]:
        """Schedule a follow-up (``due_at`` ISO 8601). Without ``owner_id``
        it is the token's user's; the owner gets a reminder when it is due."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        payload = _set_fields(
            title=title,
            kind=kind,
            due_at=due_at,
            contact_id=contact_id,
            opportunity_id=opportunity_id,
            description=description,
        )
        payload["owner_id"] = owner_id if owner_id is not None else ctx.user.id
        row = await activity_service.save_activity(
            ctx.session,
            account_id=ctx.account.id,
            activity=None,
            payload=payload,
            user_id=ctx.user.id,
        )
        return (await present_activities(ctx.session, [row]))[0]

    @mcp.tool(name="update_crm_activity")
    @requires("write")
    async def update_crm_activity(
        activity_id: int,
        done: bool | None = None,
        title: str | None = None,
        due_at: str | None = None,
        description: str | None = None,
        owner_id: int | None = None,
    ) -> dict[str, Any]:
        """Mark a follow-up done (``done=true``) or change it."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        row = await activity_service.get_activity(
            ctx.session, account_id=ctx.account.id, activity_id=activity_id
        )
        if row is None:
            raise ValueError(f"activity {activity_id} not found in this account")
        payload = _set_fields(
            done=done, title=title, due_at=due_at, description=description, owner_id=owner_id
        )
        if not payload:
            raise ValueError("nothing to update")
        row = await activity_service.save_activity(
            ctx.session, account_id=ctx.account.id, activity=row, payload=payload
        )
        return (await present_activities(ctx.session, [row]))[0]


__all__ = ["register"]
