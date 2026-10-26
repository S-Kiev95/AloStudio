"""Media library model (account-scoped).

One row per uploaded image or video. Only the object-store ``key`` is
stored, never a public link: those are signed and expire, so a link is
minted whenever one is needed (the preview, or the moment a post goes
out — which can be weeks after the upload).
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, ForeignKey, Index, String
from sqlmodel import Field

from app.core.base_model import TimestampMixin

MEDIA_KIND_IMAGE = "image"
MEDIA_KIND_VIDEO = "video"
MEDIA_KINDS: tuple[str, ...] = (MEDIA_KIND_IMAGE, MEDIA_KIND_VIDEO)


class MediaAsset(TimestampMixin, table=True):
    """An image or video in an account's library."""

    __tablename__ = "media_assets"
    __table_args__ = (
        Index(
            "index_media_assets_on_account_id_and_created_at",
            "account_id",
            "created_at",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    kind: str = Field(sa_column=Column(String, nullable=False))
    key: str = Field(sa_column=Column(String, nullable=False, unique=True))
    filename: str = Field(sa_column=Column(String, nullable=False))
    content_type: str = Field(sa_column=Column(String, nullable=False))
    size_bytes: int = Field(sa_column=Column(BigInteger, nullable=False))
    uploaded_by_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


__all__ = ["MEDIA_KINDS", "MEDIA_KIND_IMAGE", "MEDIA_KIND_VIDEO", "MediaAsset"]
