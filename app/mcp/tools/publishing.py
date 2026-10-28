"""MCP tools — multi-network publishing and the media library it draws on."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from app.core.errors import ChatwootHTTPException
from app.domains.media_library import service as media_svc
from app.domains.media_library.presenters import present_asset
from app.domains.publishing import analytics
from app.domains.publishing import service as svc
from app.domains.publishing.presenters import (
    present_channel,
    present_one_publication,
    present_publications,
)
from app.mcp.context import current_mcp_context
from app.mcp.permissions import requires


def _as_value_error(exc: ChatwootHTTPException) -> ValueError:
    detail = exc.detail
    if not isinstance(detail, dict):
        return ValueError(str(detail))
    msg = detail.get("message") or detail.get("error") or str(detail)
    errors = detail.get("errors")
    if errors:
        msg = f"{msg}: {'; '.join(errors)}"
    return ValueError(msg)


def _parse_datetime(raw: str | None, field: str) -> datetime | None:
    if raw is None:
        return None
    try:
        return datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO 8601 datetime") from exc


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="list_publication_channels")
    @requires("read")
    async def list_publication_channels() -> dict[str, Any]:
        """Social channels of the current account that can publish posts
        (use their inbox_id in create_publication)."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        channels = await svc.list_channels(ctx.session, account_id=ctx.account.id)
        return {
            "channels": [present_channel(inbox, net) for inbox, net in channels]
        }

    @mcp.tool(name="list_media")
    @requires("read")
    async def list_media(
        kind: str | None = None, page: int = 1
    ) -> dict[str, Any]:
        """Images and videos in the account's media library, newest first
        (use their id as ``{"media_id": id}`` in create_publication)."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        try:
            rows = await media_svc.list_assets(
                ctx.session, account_id=ctx.account.id, kind=kind, page=page
            )
        except ChatwootHTTPException as exc:
            raise _as_value_error(exc) from exc
        return {"media": [present_asset(a) for a in rows]}

    @mcp.tool(name="list_publications")
    @requires("read")
    async def list_publications(
        from_: Annotated[str | None, Field(alias="from")] = None,
        to: str | None = None,
        state: str | None = None,
    ) -> dict[str, Any]:
        """List publications by date (scheduled date, ascending), with the
        state and result of each channel."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        try:
            rows = await svc.list_publications(
                ctx.session,
                account_id=ctx.account.id,
                starts_from=_parse_datetime(from_, "from"),
                starts_to=_parse_datetime(to, "to"),
                state=state,
            )
        except ChatwootHTTPException as exc:
            raise _as_value_error(exc) from exc
        return {"publications": await present_publications(ctx.session, rows)}

    @mcp.tool(name="create_publication")
    @requires("write")
    async def create_publication(
        inbox_ids: list[int],
        content: str | None = None,
        media: list[dict[str, Any]] | None = None,
        scheduled_for: str | None = None,
        settings: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Schedule a post to one or more channels.

        ``media`` is an ordered list; each item is ``{"media_id": id}`` from
        list_media (preferred) or ``{"type": "image"|"video", "url"}`` with a
        public URL. ``settings`` maps an inbox_id (as a string) to that
        channel's options, e.g. ``{"12": {"post_type": "reels"}}``. Without
        ``scheduled_for`` the post goes out on the next scheduler run
        (within about 5 minutes).
        """
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        per_channel = settings or {}
        try:
            publication = await svc.create_publication(
                ctx.session,
                account_id=ctx.account.id,
                created_by_id=ctx.user.id,
                payload={
                    "content": content,
                    "media": media or [],
                    "scheduled_for": _parse_datetime(
                        scheduled_for, "scheduled_for"
                    ),
                    "targets": [
                        {
                            "inbox_id": inbox_id,
                            "settings": per_channel.get(str(inbox_id)) or {},
                        }
                        for inbox_id in inbox_ids
                    ],
                },
            )
        except ChatwootHTTPException as exc:
            raise _as_value_error(exc) from exc
        return await present_one_publication(ctx.session, publication)

    @mcp.tool(name="get_publishing_analytics")
    @requires("read")
    async def get_publishing_analytics(
        from_: Annotated[str | None, Field(alias="from")] = None,
        to: str | None = None,
        inbox_id: int | None = None,
    ) -> dict[str, Any]:
        """Results of published posts in a period (default: last 30 days):
        totals, per-channel figures and follower growth, and the best posts.
        Post figures are refreshed hourly, channel figures daily."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        until = _parse_datetime(to, "to") or datetime.now(UTC)
        since = _parse_datetime(from_, "from") or until - timedelta(days=30)
        if until.tzinfo is None:
            until = until.replace(tzinfo=UTC)
        if since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        try:
            return await analytics.analytics_summary(
                ctx.session,
                account_id=ctx.account.id,
                starts_from=since,
                starts_to=until,
                inbox_id=inbox_id,
            )
        except ChatwootHTTPException as exc:
            raise _as_value_error(exc) from exc

    @mcp.tool(name="cancel_publication")
    @requires("write")
    async def cancel_publication(publication_id: int) -> dict[str, Any]:
        """Delete a publication that has not gone out (draft, scheduled or failed)."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        publication = await svc.get_publication(
            ctx.session, account_id=ctx.account.id, publication_id=publication_id
        )
        if publication is None:
            raise ValueError(
                f"publication {publication_id} not found in this account"
            )
        try:
            await svc.delete_publication(ctx.session, publication=publication)
        except ChatwootHTTPException as exc:
            raise _as_value_error(exc) from exc
        return {"deleted": publication_id}


__all__ = ["register"]
