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
from sqlmodel import col, select

from app.domains.canned_responses import service as canned_service
from app.domains.inboxes.models import Inbox
from app.domains.labels import service as label_service
from app.domains.labels.models import Label
from app.domains.reporting.service import (
    build_summary,
    live_conversation_metrics,
)
from app.domains.teams.models import Team
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_ADMINISTRATOR,
    AccountUser,
    User,
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

    @mcp.tool(name="create_label")
    @requires("write")
    async def create_label(
        title: str,
        description: str | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        """Create a label on the current account (title in lowercase, no
        spaces; duplicates are refused). add_label also creates a missing
        label on the fly; use this one to give it a description or color."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        label = await label_service.create_label(
            ctx.session,
            account_id=ctx.account.id,
            payload={"title": title, "description": description, "color": color},
        )
        return {
            "id": label.id,
            "title": label.title,
            "description": label.description,
            "color": label.color,
        }

    @mcp.tool(name="list_inboxes")
    @requires("read")
    async def list_inboxes() -> dict[str, Any]:
        """The account's inboxes (one per connected channel: WhatsApp,
        Instagram, email, web chat…). Use their id in create_conversation
        and to read the channel of a conversation."""
        ctx = current_mcp_context()
        rows = list(
            (
                await ctx.session.exec(
                    select(Inbox)
                    .where(Inbox.account_id == ctx.account.id)
                    .order_by(col(Inbox.id).asc())
                )
            ).all()
        )
        return {
            "inboxes": [
                {
                    "id": inbox.id,
                    "name": inbox.name,
                    "channel_type": inbox.channel_type,
                    "enable_auto_assignment": inbox.enable_auto_assignment,
                }
                for inbox in rows
            ]
        }

    @mcp.tool(name="list_agents")
    @requires("read")
    async def list_agents() -> dict[str, Any]:
        """The people of the account (agents and administrators). Use their
        id in assign_agent and create_conversation."""
        ctx = current_mcp_context()
        rows = list(
            (
                await ctx.session.exec(
                    select(User, AccountUser)
                    .join(AccountUser, col(AccountUser.user_id) == col(User.id))
                    .where(AccountUser.account_id == ctx.account.id)
                    .order_by(col(User.name).asc())
                )
            ).all()
        )
        return {
            "agents": [
                {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "role": (
                        "administrator"
                        if account_user.role == ACCOUNT_USER_ROLE_ADMINISTRATOR
                        else "agent"
                    ),
                }
                for user, account_user in rows
            ]
        }

    @mcp.tool(name="list_teams")
    @requires("read")
    async def list_teams() -> dict[str, Any]:
        """The account's teams. Use their id in assign_team and
        create_conversation."""
        ctx = current_mcp_context()
        rows = list(
            (
                await ctx.session.exec(
                    select(Team)
                    .where(Team.account_id == ctx.account.id)
                    .order_by(col(Team.name).asc())
                )
            ).all()
        )
        return {
            "teams": [
                {"id": team.id, "name": team.name, "description": team.description}
                for team in rows
            ]
        }

    @mcp.tool(name="list_canned_responses")
    @requires("read")
    async def list_canned_responses(search: str | None = None) -> dict[str, Any]:
        """The account's canned responses (short code + text), optionally
        filtered by ``search`` in the short code or the text. Useful to reply
        with the wording the team already agreed on."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        rows = await canned_service.list_canned_responses(
            ctx.session, account_id=ctx.account.id, search=search
        )
        return {
            "canned_responses": [
                {"id": row.id, "short_code": row.short_code, "content": row.content}
                for row in rows
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
