"""MCP tools — CRM products and appointments operations."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from app.core.errors import ChatwootHTTPException
from app.domains.appointments import service as asvc
from app.domains.appointments.presenters import (
    present_appointments,
    present_one_appointment,
)
from app.domains.products import service as psvc
from app.domains.products.presenters import present_product
from app.mcp.context import current_mcp_context
from app.mcp.permissions import requires


def _as_value_error(exc: ChatwootHTTPException) -> ValueError:
    detail = exc.detail
    if not isinstance(detail, dict):
        return ValueError(str(detail))
    msg = detail.get("message") or detail.get("error") or str(detail)
    return ValueError(msg)


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="list_products")
    @requires("read")
    async def list_products(
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        """List products/services in the current account's catalogue."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        rows = await psvc.list_products(
            ctx.session,
            account_id=ctx.account.id,
            enabled=enabled,
        )
        return {"products": [present_product(p) for p in rows]}

    @mcp.tool(name="list_appointments")
    @requires("read")
    async def list_appointments(
        from_: Annotated[str | None, Field(alias="from")] = None,
        to: str | None = None,
        contact_id: int | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """List appointments on the current account ordered by starts_at asc."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        try:
            rows = await asvc.list_appointments(
                ctx.session,
                account_id=ctx.account.id,
                starts_from=from_,
                starts_to=to,
                contact_id=contact_id,
                status=status,
            )
        except ChatwootHTTPException as exc:
            raise _as_value_error(exc) from exc
        return {
            "appointments": await present_appointments(ctx.session, rows),
        }

    @mcp.tool(name="create_appointment")
    @requires("write")
    async def create_appointment(
        contact_id: int,
        title: str,
        starts_at: str,
        ends_at: str | None = None,
        product_id: int | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Schedule an appointment for a contact in the current account."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        try:
            appt = await asvc.create_appointment(
                ctx.session,
                account_id=ctx.account.id,
                created_by_id=ctx.user.id,
                payload={
                    "contact_id": contact_id,
                    "title": title,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "product_id": product_id,
                    "notes": notes,
                },
            )
        except ChatwootHTTPException as exc:
            raise _as_value_error(exc) from exc
        return await present_one_appointment(ctx.session, appt)

    @mcp.tool(name="update_appointment_status")
    @requires("write")
    async def update_appointment_status(
        appointment_id: int,
        status: str,
    ) -> dict[str, Any]:
        """Change the status of an appointment (scheduled/confirmed/cancelled/done)."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        appt = await asvc.get_appointment(
            ctx.session,
            account_id=ctx.account.id,
            appointment_id=appointment_id,
        )
        if appt is None:
            raise ValueError(
                f"appointment {appointment_id} not found in this account"
            )
        try:
            updated = await asvc.update_appointment(
                ctx.session,
                appointment=appt,
                payload={"status": status},
            )
        except ChatwootHTTPException as exc:
            raise _as_value_error(exc) from exc
        return await present_one_appointment(ctx.session, updated)


__all__ = ["register"]
