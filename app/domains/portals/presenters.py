"""Wire-shape presenters for Portal / Category / Article."""

from __future__ import annotations

from typing import Any

from app.domains.portals.models import (
    Article,
    Category,
    Portal,
    article_status_to_str,
)


def present_portal(portal: Portal) -> dict[str, Any]:
    return {
        "id": portal.id,
        "account_id": portal.account_id,
        "name": portal.name,
        "slug": portal.slug,
        "custom_domain": portal.custom_domain,
        "color": portal.color,
        "homepage_link": portal.homepage_link,
        "page_title": portal.page_title,
        "header_text": portal.header_text,
        "config": portal.config or {},
        "archived": portal.archived,
    }


def present_category(category: Category) -> dict[str, Any]:
    return {
        "id": category.id,
        "account_id": category.account_id,
        "portal_id": category.portal_id,
        "name": category.name,
        "description": category.description,
        "position": category.position,
        "locale": category.locale,
        "slug": category.slug,
        "icon": category.icon,
        "parent_category_id": category.parent_category_id,
        "associated_category_id": category.associated_category_id,
    }


def present_article(article: Article) -> dict[str, Any]:
    return {
        "id": article.id,
        "account_id": article.account_id,
        "portal_id": article.portal_id,
        "category_id": article.category_id,
        "title": article.title,
        "description": article.description,
        "content": article.content,
        "status": article_status_to_str(article.status),
        "views": article.views,
        "author_id": article.author_id,
        "slug": article.slug,
        "locale": article.locale,
        "position": article.position,
        "meta": article.meta or {},
    }


__all__ = ["present_article", "present_category", "present_portal"]
