"""MCP tools — account configuration (``admin`` scope).

Automation rules, outgoing webhooks, business hours, RSS autoposts,
publishing plugs and Help Center articles. Every lookup is scoped to the
token's account; these change how the account behaves for everyone, so
they need an ``admin`` token.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from app.domains.automation import service as automation_service
from app.domains.automation.presenters import present_rule
from app.domains.inboxes.models import Inbox
from app.domains.portals import service as portal_service
from app.domains.portals.models import Portal
from app.domains.portals.presenters import present_article, present_portal
from app.domains.publishing import autopost as autopost_service
from app.domains.publishing import plugs as plug_service
from app.domains.publishing.presenters import present_autopost, present_plug
from app.domains.webhooks import service as webhook_service
from app.domains.webhooks.presenters import present_webhook
from app.domains.working_hours import service as hours_service
from app.domains.working_hours.presenters import present_working_hour
from app.mcp.context import current_mcp_context
from app.mcp.permissions import requires


async def _inbox(inbox_id: int) -> Inbox:
    ctx = current_mcp_context()
    inbox = await ctx.session.get(Inbox, inbox_id)
    if inbox is None or inbox.account_id != ctx.account.id:
        raise ValueError(f"inbox {inbox_id} not found in this account")
    return inbox


async def _portal(slug: str) -> Portal:
    ctx = current_mcp_context()
    assert ctx.account.id is not None
    portal = await portal_service.fetch_portal_by_slug(
        ctx.session, account_id=ctx.account.id, slug=slug
    )
    if portal is None:
        raise ValueError(f"help center {slug!r} not found in this account")
    return portal


async def _category_in(portal: Portal, category_id: int | None) -> None:
    if category_id is None:
        return
    ctx = current_mcp_context()
    category = await portal_service.fetch_category(
        ctx.session, portal_id=portal.id, category_id=category_id  # type: ignore[arg-type]
    )
    if category is None:
        raise ValueError(f"category {category_id} not found in this help center")


def _only_set(**values: Any) -> dict[str, Any]:
    payload = {k: v for k, v in values.items() if v is not None}
    if not payload:
        raise ValueError("nothing to update")
    return payload


def register(mcp: FastMCP) -> None:
    # --- automation rules -------------------------------------------------
    @mcp.tool(name="list_automation_rules")
    @requires("admin")
    async def list_automation_rules() -> dict[str, Any]:
        """The account's automation rules: event, conditions, actions and
        whether each is active."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        rows = await automation_service.list_rules(ctx.session, account_id=ctx.account.id)
        return {"rules": [present_rule(r) for r in rows]}

    @mcp.tool(name="create_automation_rule")
    @requires("admin")
    async def create_automation_rule(
        name: str,
        event_name: str,
        conditions: list[dict[str, Any]],
        actions: list[dict[str, Any]],
        description: str | None = None,
        active: bool = True,
    ) -> dict[str, Any]:
        """Create a rule. ``event_name``: conversation_created,
        conversation_updated, conversation_opened, conversation_resolved or
        message_created. ``conditions``: ``[{"attribute_key", "filter_operator",
        "values", "query_operator"}]``; ``actions``: ``[{"action_name",
        "action_params"}]`` (same shape list_automation_rules shows)."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        rule = await automation_service.create_rule(
            ctx.session,
            account_id=ctx.account.id,
            payload={
                "name": name,
                "event_name": event_name,
                "conditions": conditions,
                "actions": actions,
                "description": description,
                "active": active,
            },
        )
        return present_rule(rule)

    @mcp.tool(name="update_automation_rule")
    @requires("admin")
    async def update_automation_rule(
        rule_id: int,
        name: str | None = None,
        description: str | None = None,
        active: bool | None = None,
        conditions: list[dict[str, Any]] | None = None,
        actions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Change a rule; fields left out stay. ``active=false`` pauses it."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        rule = await automation_service.fetch_rule(
            ctx.session, account_id=ctx.account.id, rule_id=rule_id
        )
        if rule is None:
            raise ValueError(f"rule {rule_id} not found in this account")
        rule = await automation_service.update_rule(
            ctx.session,
            rule=rule,
            payload=_only_set(
                name=name,
                description=description,
                active=active,
                conditions=conditions,
                actions=actions,
            ),
        )
        return present_rule(rule)

    @mcp.tool(name="delete_automation_rule")
    @requires("admin")
    async def delete_automation_rule(rule_id: int) -> dict[str, Any]:
        """Delete a rule (to only pause it, update_automation_rule active=false)."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        rule = await automation_service.fetch_rule(
            ctx.session, account_id=ctx.account.id, rule_id=rule_id
        )
        if rule is None:
            raise ValueError(f"rule {rule_id} not found in this account")
        await automation_service.destroy_rule(ctx.session, rule=rule)
        return {"deleted": rule_id}

    # --- outgoing webhooks --------------------------------------------------
    @mcp.tool(name="list_webhooks")
    @requires("admin")
    async def list_webhooks() -> dict[str, Any]:
        """Webhooks the account sends its events to, with their signing
        secret."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        rows = await webhook_service.list_webhooks(ctx.session, account_id=ctx.account.id)
        return {"webhooks": [present_webhook(w) for w in rows]}

    @mcp.tool(name="create_webhook")
    @requires("admin")
    async def create_webhook(
        url: str,
        subscriptions: list[str],
        name: str | None = None,
        inbox_id: int | None = None,
    ) -> dict[str, Any]:
        """Send the account's events to ``url`` (public https).
        ``subscriptions``: event names such as message_created,
        conversation_created, conversation_status_changed. Each delivery
        is signed with the webhook's secret."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        inbox = await _inbox(inbox_id) if inbox_id is not None else None
        webhook = await webhook_service.create_webhook(
            ctx.session,
            account_id=ctx.account.id,
            payload={
                "url": url,
                "subscriptions": subscriptions,
                "name": name,
                "inbox_id": inbox_id,
            },
        )
        return present_webhook(webhook, inbox=inbox)

    @mcp.tool(name="delete_webhook")
    @requires("admin")
    async def delete_webhook(webhook_id: int) -> dict[str, Any]:
        """Stop sending events to a webhook."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        webhook = await webhook_service.fetch_webhook(
            ctx.session, account_id=ctx.account.id, webhook_id=webhook_id
        )
        if webhook is None:
            raise ValueError(f"webhook {webhook_id} not found in this account")
        await webhook_service.destroy_webhook(ctx.session, webhook=webhook)
        return {"deleted": webhook_id}

    # --- business hours -----------------------------------------------------
    @mcp.tool(name="get_working_hours")
    @requires("admin")
    async def get_working_hours(inbox_id: int) -> dict[str, Any]:
        """An inbox's business hours, one row per day of the week
        (0 = Sunday)."""
        inbox = await _inbox(inbox_id)
        ctx = current_mcp_context()
        assert inbox.id is not None
        rows = await hours_service.list_for_inbox(ctx.session, inbox_id=inbox.id)
        return {
            "inbox_id": inbox.id,
            "working_hours_enabled": inbox.working_hours_enabled,
            "working_hours": [present_working_hour(r) for r in rows],
        }

    @mcp.tool(name="set_working_hours")
    @requires("admin")
    async def set_working_hours(
        inbox_id: int, schedule: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Change some days of an inbox's business hours. Each item:
        ``{"day_of_week": 0-6, "closed_all_day": bool, "open_hour",
        "open_minutes", "close_hour", "close_minutes", "open_all_day"}``
        (fields left out stay)."""
        inbox = await _inbox(inbox_id)
        ctx = current_mcp_context()
        rows = await hours_service.bulk_update_for_inbox(
            ctx.session, inbox=inbox, schedule=schedule
        )
        return {"inbox_id": inbox.id, "working_hours": [present_working_hour(r) for r in rows]}

    # --- RSS autoposts and plugs --------------------------------------------
    @mcp.tool(name="list_autoposts")
    @requires("admin")
    async def list_autoposts() -> dict[str, Any]:
        """RSS feeds that publish (or draft) a post for each new item."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        rows = await autopost_service.list_autoposts(ctx.session, account_id=ctx.account.id)
        return {"autoposts": [present_autopost(a) for a in rows]}

    @mcp.tool(name="set_autopost_active")
    @requires("admin")
    async def set_autopost_active(autopost_id: int, active: bool) -> dict[str, Any]:
        """Pause or resume an RSS autopost."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        autopost = await autopost_service.get_autopost(
            ctx.session, account_id=ctx.account.id, autopost_id=autopost_id
        )
        if autopost is None:
            raise ValueError(f"autopost {autopost_id} not found in this account")
        autopost = await autopost_service.save_autopost(
            ctx.session, autopost=autopost, values={"active": active}
        )
        return present_autopost(autopost)

    @mcp.tool(name="list_plugs")
    @requires("admin")
    async def list_plugs() -> dict[str, Any]:
        """Automatic actions on published posts (for example: repost when a
        post passes N likes), with their recent runs."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        rows = await plug_service.list_plugs(ctx.session, account_id=ctx.account.id)
        runs = await plug_service.runs_by_plug(
            ctx.session, plug_ids=[p.id for p in rows if p.id is not None]
        )
        return {"plugs": [present_plug(p, runs.get(p.id, [])) for p in rows]}  # type: ignore[arg-type]

    @mcp.tool(name="set_plug_active")
    @requires("admin")
    async def set_plug_active(plug_id: int, active: bool) -> dict[str, Any]:
        """Pause or resume a plug."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        plug = await plug_service.get_plug(
            ctx.session, account_id=ctx.account.id, plug_id=plug_id
        )
        if plug is None:
            raise ValueError(f"plug {plug_id} not found in this account")
        plug = await plug_service.save_plug(ctx.session, plug=plug, values={"active": active})
        runs = await plug_service.runs_by_plug(ctx.session, plug_ids=[plug.id])  # type: ignore[list-item]
        return present_plug(plug, runs.get(plug.id, []))  # type: ignore[arg-type]

    # --- Help Center ----------------------------------------------------------
    @mcp.tool(name="list_help_centers")
    @requires("admin")
    async def list_help_centers() -> dict[str, Any]:
        """The account's Help Centers (portals); their ``slug`` is what the
        article tools take."""
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        rows = await portal_service.list_portals(ctx.session, account_id=ctx.account.id)
        return {"help_centers": [present_portal(p) for p in rows]}

    @mcp.tool(name="list_articles")
    @requires("admin")
    async def list_articles(
        portal_slug: str, query: str | None = None, locale: str | None = None
    ) -> dict[str, Any]:
        """Articles of a Help Center (drafts too), optionally searched by
        ``query``."""
        portal = await _portal(portal_slug)
        ctx = current_mcp_context()
        rows = await portal_service.list_articles(
            ctx.session, portal_id=portal.id, locale=locale, query=query  # type: ignore[arg-type]
        )
        return {"articles": [present_article(a) for a in rows]}

    @mcp.tool(name="create_article")
    @requires("admin")
    async def create_article(
        portal_slug: str,
        title: str,
        content: str,
        description: str | None = None,
        category_id: int | None = None,
        locale: str | None = None,
        publish: bool = False,
    ) -> dict[str, Any]:
        """Write a Help Center article (Markdown ``content``). It stays a
        draft unless ``publish`` is true; published ones are indexed for
        the bot's answers."""
        portal = await _portal(portal_slug)
        await _category_in(portal, category_id)
        ctx = current_mcp_context()
        assert ctx.account.id is not None
        article = await portal_service.create_article(
            ctx.session,
            account_id=ctx.account.id,
            portal=portal,
            author_id=ctx.user.id,
            payload={
                "title": title,
                "content": content,
                "description": description,
                "category_id": category_id,
                "locale": locale or "es",
                "status": "published" if publish else "draft",
            },
        )
        return present_article(article)

    @mcp.tool(name="update_article")
    @requires("admin")
    async def update_article(
        portal_slug: str,
        article_id: int,
        title: str | None = None,
        content: str | None = None,
        description: str | None = None,
        category_id: int | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Edit an article; fields left out stay. ``status``: draft,
        published or archived."""
        portal = await _portal(portal_slug)
        await _category_in(portal, category_id)
        ctx = current_mcp_context()
        article = await portal_service.fetch_article(
            ctx.session, portal_id=portal.id, article_id=article_id  # type: ignore[arg-type]
        )
        if article is None:
            raise ValueError(f"article {article_id} not found in this help center")
        article = await portal_service.update_article(
            ctx.session,
            article=article,
            payload=_only_set(
                title=title,
                content=content,
                description=description,
                category_id=category_id,
                status=status,
            ),
        )
        return present_article(article)



__all__ = ["register"]
