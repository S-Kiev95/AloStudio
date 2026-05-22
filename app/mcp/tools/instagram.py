"""MCP tools — Instagram publishing + moderation + product context.

Surfaces the feat/instagram-graph extension to AI agents. Like the
other tool modules, account scope comes from the authenticated
:class:`MCPContext` (never an argument) so an agent can't cross-tenant.

The headline tool for AI agents is :func:`products_for_media`: when an
IG user comments or DMs about a post, the agent resolves
*media → post → products* to answer with the right product context.

Permission scopes:
  * **read**  — list/show posts, list products, products_for_media,
                list comments (local mirror)
  * **write** — create post (scheduled), post/reply/hide comments
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastmcp import FastMCP

from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.models import (
    CHANNEL_TYPE_INSTAGRAM,
    Inbox,
    InstagramChannel,
)
from app.domains.instagram import publishing_service as svc
from app.domains.instagram.presenters import present_comment, present_post
from app.domains.products.presenters import present_product
from app.mcp.context import current_mcp_context
from app.mcp.permissions import requires


# ---------------------------------------------------------------------------
# Helpers (account-scoped resolution)
# ---------------------------------------------------------------------------
async def _channel_for_inbox(inbox_id: int) -> int:
    ctx = current_mcp_context()
    inbox = await ctx.session.get(Inbox, inbox_id)
    if inbox is None or inbox.account_id != ctx.account.id:
        raise ValueError(f"inbox {inbox_id} not found in this account")
    if inbox.channel_type != CHANNEL_TYPE_INSTAGRAM:
        raise ValueError(f"inbox {inbox_id} is not an Instagram inbox")
    return inbox.channel_id


async def _post_or_raise(post_id: int):
    ctx = current_mcp_context()
    post = await svc.get_post(
        ctx.session, account_id=ctx.account.id, post_id=post_id
    )
    if post is None:
        raise ValueError(f"instagram post {post_id} not found")
    return post


async def _comment_or_raise(comment_id: int):
    ctx = current_mcp_context()
    comment = await svc.get_comment(
        ctx.session, account_id=ctx.account.id, comment_id=comment_id
    )
    if comment is None:
        raise ValueError(f"instagram comment {comment_id} not found")
    return comment


async def _channel_or_raise(channel_instagram_id: int) -> InstagramChannel:
    ctx = current_mcp_context()
    channel = await ctx.session.get(InstagramChannel, channel_instagram_id)
    if channel is None:
        raise ValueError("instagram channel not found")
    return channel


def _as_value_error(exc: ChatwootHTTPException) -> ValueError:
    detail = exc.detail
    msg = detail.get("message") or detail.get("error") or str(detail)
    return ValueError(msg)


# ===========================================================================
# Tools
# ===========================================================================
def register(mcp: FastMCP) -> None:
    # ---- read ----------------------------------------------------------
    @mcp.tool(name="list_instagram_posts")
    @requires("read")
    async def list_instagram_posts(
        state: Literal[
            "pending", "publishing", "published", "failed", "deleted"
        ]
        | None = None,
        page: int = 1,
    ) -> dict[str, Any]:
        """List Instagram posts on the current account (newest first).
        Optional ``state`` filter."""
        ctx = current_mcp_context()
        rows = await svc.list_posts(
            ctx.session, account_id=ctx.account.id, state=state, page=page
        )
        return {"page": page, "posts": [present_post(p) for p in rows]}

    @mcp.tool(name="show_instagram_post")
    @requires("read")
    async def show_instagram_post(post_id: int) -> dict[str, Any]:
        """Read one post with its containers + linked products."""
        ctx = current_mcp_context()
        post = await _post_or_raise(post_id)
        containers = await svc.list_containers(ctx.session, post_id=post.id)
        products = await svc.products_for_post(ctx.session, post_id=post.id)
        return present_post(post, containers=containers, products=products)

    @mcp.tool(name="list_instagram_products")
    @requires("read")
    async def list_instagram_products(
        enabled: bool | None = None, page: int = 1
    ) -> dict[str, Any]:
        """List the account's product catalogue."""
        from app.domains.products import service as psvc

        ctx = current_mcp_context()
        rows = await psvc.list_products(
            ctx.session, account_id=ctx.account.id, enabled=enabled, page=page
        )
        return {"page": page, "products": [present_product(p) for p in rows]}

    @mcp.tool(name="instagram_products_for_media")
    @requires("read")
    async def instagram_products_for_media(
        ig_media_id: str,
    ) -> dict[str, Any]:
        """**AI context hook.** Given the Instagram media id a comment or
        DM is about, return the product(s) that post/story promotes — so
        the agent answers with the right product knowledge. Empty list
        when the media isn't ours or has no linked products."""
        ctx = current_mcp_context()
        products = await svc.products_for_media(
            ctx.session, account_id=ctx.account.id, ig_media_id=ig_media_id
        )
        return {
            "ig_media_id": ig_media_id,
            "products": [present_product(p) for p in products],
        }

    @mcp.tool(name="list_instagram_comments")
    @requires("read")
    async def list_instagram_comments(
        ig_media_id: str, include_hidden: bool = False
    ) -> dict[str, Any]:
        """List locally-mirrored comments for a media (no Meta call —
        reads the rows the webhook/sync already stored)."""
        ctx = current_mcp_context()
        rows = await svc.list_comments_for_media(
            ctx.session,
            account_id=ctx.account.id,
            ig_media_id=ig_media_id,
            include_hidden=include_hidden,
        )
        return {
            "ig_media_id": ig_media_id,
            "comments": [present_comment(c) for c in rows],
        }

    # ---- write ---------------------------------------------------------
    @mcp.tool(name="create_instagram_post")
    @requires("write")
    async def create_instagram_post(
        inbox_id: int,
        media_type: Literal["IMAGE", "VIDEO", "REELS", "CAROUSEL", "STORIES"],
        source: dict[str, Any],
        caption: str | None = None,
        scheduled_for: str | None = None,
        product_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """Create a publish request. ``source`` shape depends on
        ``media_type`` (e.g. IMAGE → ``{"image_url": "..."}``).

        ``scheduled_for`` (ISO 8601) must be in the future; omit it to
        publish at the next scheduler tick (~5 min). Optionally link
        catalogue ``product_ids`` for later AI context.
        """
        ctx = current_mcp_context()
        when: datetime
        if scheduled_for:
            try:
                when = datetime.fromisoformat(scheduled_for)
            except ValueError as exc:
                raise ValueError(
                    "scheduled_for must be ISO 8601"
                ) from exc
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
            if when <= datetime.now(UTC):
                raise ValueError("scheduled_for must be in the future")
        else:
            # Omitted → fire at the next scheduler tick.
            when = datetime.now(UTC)

        channel_id = await _channel_for_inbox(inbox_id)
        try:
            post = await svc.create_post(
                ctx.session,
                account_id=ctx.account.id,
                inbox_id=inbox_id,
                channel_instagram_id=channel_id,
                media_type=media_type,
                source=source,
                caption=caption,
                scheduled_for=when,
                product_ids=product_ids,
            )
        except ChatwootHTTPException as exc:
            raise _as_value_error(exc) from exc
        products = await svc.products_for_post(ctx.session, post_id=post.id)
        return present_post(post, products=products)

    @mcp.tool(name="post_instagram_comment")
    @requires("write")
    async def post_instagram_comment(
        post_id: int, message: str
    ) -> dict[str, Any]:
        """Post a comment on one of our published posts."""
        ctx = current_mcp_context()
        post = await _post_or_raise(post_id)
        if not post.ig_media_id:
            raise ValueError("post has no published media yet")
        channel = await _channel_or_raise(post.channel_instagram_id)
        try:
            comment = await svc.post_comment_on_meta(
                ctx.session,
                channel=channel,
                account_id=ctx.account.id,
                ig_media_id=post.ig_media_id,
                message=message,
            )
        except ChatwootHTTPException as exc:
            raise _as_value_error(exc) from exc
        return present_comment(comment)

    @mcp.tool(name="reply_to_instagram_comment")
    @requires("write")
    async def reply_to_instagram_comment(
        comment_id: int, message: str
    ) -> dict[str, Any]:
        """Reply to a comment (the agent answering an IG user)."""
        ctx = current_mcp_context()
        parent = await _comment_or_raise(comment_id)
        channel = await _channel_or_raise(parent.channel_instagram_id)
        try:
            reply = await svc.reply_comment_on_meta(
                ctx.session,
                channel=channel,
                account_id=ctx.account.id,
                parent_comment=parent,
                message=message,
            )
        except ChatwootHTTPException as exc:
            raise _as_value_error(exc) from exc
        return present_comment(reply)

    @mcp.tool(name="hide_instagram_comment")
    @requires("write")
    async def hide_instagram_comment(
        comment_id: int, hide: bool = True
    ) -> dict[str, Any]:
        """Hide (or unhide) a comment — moderation."""
        ctx = current_mcp_context()
        comment = await _comment_or_raise(comment_id)
        channel = await _channel_or_raise(comment.channel_instagram_id)
        try:
            updated = await svc.hide_comment_on_meta(
                ctx.session, channel=channel, comment=comment, hide=hide
            )
        except ChatwootHTTPException as exc:
            raise _as_value_error(exc) from exc
        return present_comment(updated)


__all__ = ["register"]
