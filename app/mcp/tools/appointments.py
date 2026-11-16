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

    @mcp.tool(name="create_product")
    @requires("write")
    async def create_product(
        name: str,
        description: str | None = None,
        price: float | None = None,
        currency: str | None = None,
        sku: str | None = None,
        url: str | None = None,
        image_url: str | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        """Add a product or service to the account's catalogue (the one
        appointments and Instagram posts can point to)."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        product = await psvc.create_product(
            ctx.session,
            account_id=ctx.account.id,
            payload={
                "name": name,
                "description": description,
                "price": price,
                "currency": currency,
                "sku": sku,
                "url": url,
                "image_url": image_url,
                "enabled": enabled,
            },
        )
        return present_product(product)

    @mcp.tool(name="update_product")
    @requires("write")
    async def update_product(
        product_id: int,
        name: str | None = None,
        description: str | None = None,
        price: float | None = None,
        currency: str | None = None,
        sku: str | None = None,
        url: str | None = None,
        image_url: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        """Change a product; fields left out stay as they are. ``enabled``
        false hides it from the catalogue without deleting it."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        product = await psvc.get_product(
            ctx.session, account_id=ctx.account.id, product_id=product_id
        )
        if product is None:
            raise ValueError(f"product {product_id} not found in this account")
        payload = {
            key: value
            for key, value in (
                ("name", name),
                ("description", description),
                ("price", price),
                ("currency", currency),
                ("sku", sku),
                ("url", url),
                ("image_url", image_url),
                ("enabled", enabled),
            )
            if value is not None
        }
        if not payload:
            raise ValueError("nothing to update")
        updated = await psvc.update_product(ctx.session, product=product, payload=payload)
        return present_product(updated)

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

    @mcp.tool(name="update_appointment")
    @requires("write")
    async def update_appointment(
        appointment_id: int,
        title: str | None = None,
        starts_at: str | None = None,
        ends_at: str | None = None,
        product_id: int | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Edit or reschedule an appointment (dates in ISO 8601); fields left
        out stay as they are. For the status use update_appointment_status."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        appt = await asvc.get_appointment(
            ctx.session, account_id=ctx.account.id, appointment_id=appointment_id
        )
        if appt is None:
            raise ValueError(f"appointment {appointment_id} not found in this account")
        payload = {
            key: value
            for key, value in (
                ("title", title),
                ("starts_at", starts_at),
                ("ends_at", ends_at),
                ("product_id", product_id),
                ("notes", notes),
            )
            if value is not None
        }
        if not payload:
            raise ValueError("nothing to update")
        updated = await asvc.update_appointment(
            ctx.session, appointment=appt, payload=payload
        )
        return await present_one_appointment(ctx.session, updated)

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
