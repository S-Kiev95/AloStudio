"""MCP tools — read-only metadata: labels + reports.

The agent uses these to:
  * Discover which labels exist on the account (so it knows what
    titles to pass to ``add_label`` / ``remove_label``).
  * Read dashboard metrics for self-reflection ("how am I doing?")
    or to feed into prompts ("conversations resolved today: 14").
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastmcp import FastMCP
from sqlmodel import select

from app.domains.labels.models import Label
from app.domains.reporting.service import (
    build_summary,
    live_conversation_metrics,
)
from app.mcp.context import current_mcp_context
from app.mcp.permissions import requires


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="list_labels")
    @requires("read")
    async def list_labels() -> dict[str, Any]:
        """Every label on the current account, ordered by title.

        Useful for an agent that wants to validate a label exists
        before calling ``add_label`` — labels are auto-created on
        first use anyway, but listing helps the agent stay
        within a curated set."""
        ctx = current_mcp_context()
        rows = list(
            (
                await ctx.session.exec(
                    select(Label)
                    .where(Label.account_id == ctx.account.id)
                    .order_by(Label.title.asc())  # type: ignore[attr-defined]
                )
            ).all()
        )
        return {
            "labels": [
                {
                    "id": lab.id,
                    "title": lab.title,
                    "description": lab.description,
                    "color": lab.color,
                }
                for lab in rows
            ]
        }

    @mcp.tool(name="get_account_summary")
    @requires("read")
    async def get_account_summary(
        since_hours: int = 168,
        business_hours: bool = False,
    ) -> dict[str, Any]:
        """Dashboard summary card payload over a lookback window.

        ``since_hours`` defaults to 7 days. The full Phase 7.2
        summary metric set ships: conversations_count,
        incoming/outgoing message counts, avg_first_response_time,
        avg_resolution_time, reply_time, resolutions_count.
        """
        if since_hours < 1 or since_hours > 24 * 365:
            raise ValueError("since_hours out of range")
        ctx = current_mcp_context()
        now = datetime.now(UTC)
        since = now - timedelta(hours=since_hours)
        body = await build_summary(
            ctx.session,
            account_id=ctx.account.id,
            type="account",
            id=None,
            since=since,
            until=now,
            business_hours=business_hours,
        )
        body["since"] = int(since.timestamp())
        body["until"] = int(now.timestamp())
        return body

    @mcp.tool(name="get_live_metrics")
    @requires("read")
    async def get_live_metrics() -> dict[str, Any]:
        """Current-state counters (open / unattended / unassigned /
        pending) for the account.

        Mirrors Phase 7.4's ``/live_reports/conversation_metrics``.
        Common use: an agent checks this at the start of its loop
        to decide whether to take on more work."""
        ctx = current_mcp_context()
        body = await live_conversation_metrics(
            ctx.session,
            account_id=ctx.account.id,
            type="account",
            id=None,
        )
        return body


__all__ = ["register"]
