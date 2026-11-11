"""MCP tools — multi-network publishing and the media library it draws on."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import httpx
from fastmcp import FastMCP
from pydantic import Field

from app.core.errors import ChatwootHTTPException
from app.core.outbound import guarded_client
from app.domains.media_library import service as media_svc
from app.domains.media_library.presenters import present_asset
from app.domains.publishing import analytics
from app.domains.publishing import service as svc
from app.domains.publishing.models import Publication
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


async def _download(url: str) -> tuple[bytes, str | None]:
    """Fetch a public file, refusing private addresses (outbound guard) and
    anything over the media library's largest size."""
    limit = media_svc.MAX_UPLOAD_BYTES
    try:
        async with (
            guarded_client(timeout=30.0, follow_redirects=True) as client,
            client.stream("GET", url) as resp,
        ):
            if resp.status_code >= 400:
                raise ValueError(f"could not download the file (HTTP {resp.status_code})")
            chunks: list[bytes] = []
            size = 0
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > limit:
                    raise ValueError("the file is too big for the media library")
                chunks.append(chunk)
            content_type = resp.headers.get("content-type")
    except httpx.HTTPError as exc:
        raise ValueError(f"could not download the file: {exc}") from exc
    return b"".join(chunks), (content_type or "").split(";", 1)[0] or None


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="list_publication_channels")
    @requires("read")
    async def list_publication_channels() -> dict[str, Any]:
        """Social channels of the current account that can publish posts
        (use their id as channel_ids in create_publication). A channel with
        status "reconnect" has to be connected again before it can publish."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        channels = await svc.list_channels(ctx.session, account_id=ctx.account.id)
        return {"channels": [present_channel(channel) for channel in channels]}

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
        channel_ids: list[int],
        content: str | None = None,
        media: list[dict[str, Any]] | None = None,
        scheduled_for: str | None = None,
        settings: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Schedule a post to one or more channels.

        ``media`` is an ordered list; each item is ``{"media_id": id}`` from
        list_media (preferred) or ``{"type": "image"|"video", "url"}`` with a
        public URL. ``settings`` maps a channel id (as a string) to that
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
                            "channel_id": channel_id,
                            "settings": per_channel.get(str(channel_id)) or {},
                        }
                        for channel_id in channel_ids
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
        channel_id: int | None = None,
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
                channel_id=channel_id,
            )
        except ChatwootHTTPException as exc:
            raise _as_value_error(exc) from exc

    async def _publication(
        publication_id: int, *, for_update: bool = False
    ) -> Publication:
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        publication = await svc.get_publication(
            ctx.session,
            account_id=ctx.account.id,
            publication_id=publication_id,
            for_update=for_update,
        )
        if publication is None:
            raise ValueError(f"publication {publication_id} not found in this account")
        return publication

    @mcp.tool(name="show_publication")
    @requires("read")
    async def show_publication(publication_id: int) -> dict[str, Any]:
        """One publication with each channel's state, result, link and
        error (if it failed)."""
        ctx = current_mcp_context()
        publication = await _publication(publication_id)
        return await present_one_publication(ctx.session, publication)

    @mcp.tool(name="update_publication")
    @requires("write")
    async def update_publication(
        publication_id: int,
        content: str | None = None,
        media: list[dict[str, Any]] | None = None,
        scheduled_for: str | None = None,
        channel_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """Change a draft or scheduled publication: text, media (same shape
        as create_publication), date (ISO 8601) or channels. Fields left out
        stay as they are. A date in the past sends it now."""
        ctx = current_mcp_context()
        publication = await _publication(publication_id, for_update=True)
        payload: dict[str, Any] = {}
        if content is not None:
            payload["content"] = content
        if media is not None:
            payload["media"] = media
        if scheduled_for is not None:
            payload["scheduled_for"] = _parse_datetime(scheduled_for, "scheduled_for")
        if channel_ids is not None:
            payload["targets"] = [{"channel_id": cid, "settings": {}} for cid in channel_ids]
        if not payload:
            raise ValueError("nothing to update")
        updated = await svc.update_publication(
            ctx.session, publication=publication, payload=payload
        )
        await svc.publish_now_if_due(ctx.session, updated)
        return await present_one_publication(ctx.session, updated)

    @mcp.tool(name="retry_publication")
    @requires("write")
    async def retry_publication(publication_id: int) -> dict[str, Any]:
        """Send again the channels that failed in a publication (the ones
        already published stay). It goes out right away."""
        ctx = current_mcp_context()
        publication = await _publication(publication_id, for_update=True)
        updated = await svc.retry_publication(ctx.session, publication=publication)
        await svc.publish_now_if_due(ctx.session, updated)
        return await present_one_publication(ctx.session, updated)

    @mcp.tool(name="upload_media")
    @requires("write")
    async def upload_media(url: str, filename: str | None = None) -> dict[str, Any]:
        """Copy an image or MP4 video from a public https URL into the
        account's media library, ready for create_publication
        (``{"media_id": id}``). Images are converted to JPG."""
        url = (url or "").strip()
        if not url.startswith("https://"):
            raise ValueError("url must be a public https address")
        data, content_type = await _download(url)
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        asset = await media_svc.upload_asset(
            ctx.session,
            account_id=ctx.account.id,
            filename=filename or url.rsplit("/", 1)[-1].split("?", 1)[0] or None,
            content_type=content_type,
            data=data,
            uploaded_by_id=ctx.user.id,
        )
        return present_asset(asset)

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
