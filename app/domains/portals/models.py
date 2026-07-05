"""Help Center models — Portal + Category + Article.

Ported from:
  reference/chatwoot/app/models/portal.rb
  reference/chatwoot/app/models/category.rb
  reference/chatwoot/app/models/article.rb
  reference/chatwoot/db/schema.rb (portals / categories / articles)

A Portal is an account's help-center site (slug-keyed). It owns a tree
of Categories (with parent/child + sibling associations) and a flat
list of Articles. Articles belong to a Category and a Portal and
have ``locale`` for multi-language.

Phase 9.3 ships the model + CRUD only. The public Help Center
surface (`/hc/<slug>`) lands as a Phase 9 follow-up — same posture
as Phase 5a's web widget public surface.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.base_model import TimestampMixin

# enum status: {draft: 0, published: 1, archived: 2}
ARTICLE_STATUS_DRAFT = 0
ARTICLE_STATUS_PUBLISHED = 1
ARTICLE_STATUS_ARCHIVED = 2


def article_status_from_str(s: str | None) -> int:
    if s is None or s == "draft":
        return ARTICLE_STATUS_DRAFT
    if s == "published":
        return ARTICLE_STATUS_PUBLISHED
    if s == "archived":
        return ARTICLE_STATUS_ARCHIVED
    raise ValueError(f"unknown article status: {s!r}")


def article_status_to_str(v: int | None) -> str:
    if v == ARTICLE_STATUS_PUBLISHED:
        return "published"
    if v == ARTICLE_STATUS_ARCHIVED:
        return "archived"
    return "draft"


class Portal(TimestampMixin, table=True):
    __tablename__ = "portals"
    __table_args__ = (
        UniqueConstraint("slug", name="index_portals_on_slug"),
        UniqueConstraint(
            "custom_domain", name="index_portals_on_custom_domain"
        ),
        Index(
            "index_portals_on_channel_web_widget_id",
            "channel_web_widget_id",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    slug: str = Field(sa_column=Column(String, nullable=False))
    custom_domain: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    color: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    homepage_link: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    page_title: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    header_text: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    # Portal logo — URL of an uploaded image (our MinIO/S3 pipeline).
    # Chatwoot models this as an ActiveStorage attachment; we store the
    # resolved URL directly, set via the portal update after a direct upload.
    logo: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    config: dict = Field(
        default_factory=lambda: {"allowed_locales": ["en"]},
        sa_column=Column(
            JSONB,
            nullable=False,
            server_default='{"allowed_locales": ["en"]}',
        ),
    )
    archived: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )
    channel_web_widget_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, nullable=True),
    )
    ssl_settings: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )


class Category(TimestampMixin, table=True):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint(
            "slug",
            "locale",
            "portal_id",
            name="index_categories_on_slug_and_locale_and_portal_id",
        ),
        Index(
            "index_categories_on_locale_and_account_id",
            "locale",
            "account_id",
        ),
        Index("index_categories_on_locale", "locale"),
        Index(
            "index_categories_on_parent_category_id",
            "parent_category_id",
        ),
        Index(
            "index_categories_on_associated_category_id",
            "associated_category_id",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    portal_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("portals.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    description: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    position: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    locale: str = Field(
        default="en",
        sa_column=Column(String, nullable=False, server_default="en"),
    )
    slug: str = Field(sa_column=Column(String, nullable=False))
    parent_category_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    associated_category_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    icon: str = Field(
        default="",
        sa_column=Column(String, nullable=False, server_default=""),
    )


class Article(TimestampMixin, table=True):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("slug", name="index_articles_on_slug"),
        Index("index_articles_on_account_id", "account_id"),
        Index("index_articles_on_portal_id", "portal_id"),
        Index("index_articles_on_author_id", "author_id"),
        Index("index_articles_on_status", "status"),
        Index("index_articles_on_views", "views"),
        Index(
            "index_articles_on_associated_article_id",
            "associated_article_id",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    portal_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("portals.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    category_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    folder_id: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    title: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    description: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    content: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    status: int = Field(
        default=ARTICLE_STATUS_DRAFT,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    views: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    author_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    associated_article_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("articles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    meta: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    slug: str = Field(sa_column=Column(String, nullable=False))
    position: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    locale: str = Field(
        default="en",
        sa_column=Column(String, nullable=False, server_default="en"),
    )


__all__ = [
    "ARTICLE_STATUS_ARCHIVED",
    "ARTICLE_STATUS_DRAFT",
    "ARTICLE_STATUS_PUBLISHED",
    "Article",
    "Category",
    "Portal",
    "article_status_from_str",
    "article_status_to_str",
]
