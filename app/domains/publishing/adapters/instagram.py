"""Instagram adapter: publishes through the existing Instagram service.

Each target becomes an :class:`InstagramPost` created with
``publishing_service.create_post`` and driven by ``publish_post`` — the
same path the Instagram screen uses — so the post shows up there and the
comment auto-replies keep working. Scheduling is the publishing domain's
job, so the post is created without ``scheduled_for`` and published
right away. The post id is kept in ``target.extra`` so a retry resumes
the same post instead of creating a second one.
"""

from __future__ import annotations

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.models import CHANNEL_TYPE_INSTAGRAM, Inbox
from app.domains.publishing.adapters.base import (
    PublishingAdapter,
    PublishResult,
    target_text,
)
from app.domains.publishing.models import Publication, PublicationTarget

POST_TYPES: tuple[str, ...] = ("feed", "reels", "story")
CAPTION_MAX = 2200
CAROUSEL_MAX = 10


def _post_type(target: PublicationTarget) -> str:
    return (target.settings or {}).get("post_type") or "feed"


def _media_source(item: dict[str, Any]) -> dict[str, Any]:
    key = "video_url" if item["type"] == "video" else "image_url"
    return {key: item["url"]}


def build_instagram_post(
    publication: Publication, target: PublicationTarget
) -> tuple[str, dict[str, Any]]:
    """``(media_type, source)`` in the shape ``create_post`` expects.
    Assumes :meth:`InstagramAdapter.validate` passed."""
    media = publication.media or []
    post_type = _post_type(target)
    if post_type == "story":
        return "STORIES", _media_source(media[0])
    if post_type == "reels":
        return "REELS", {"video_url": media[0]["url"]}
    if len(media) > 1:
        return "CAROUSEL", {"children": [_media_source(m) for m in media]}
    if media[0]["type"] == "video":
        # Meta retired single feed videos; a Reel shared to the feed is
        # how a video lands in the grid today.
        return "REELS", {"video_url": media[0]["url"], "share_to_feed": True}
    return "IMAGE", {"image_url": media[0]["url"]}


class InstagramAdapter(PublishingAdapter):
    network = "instagram"

    def supports(self, inbox: Inbox) -> bool:
        return inbox.channel_type == CHANNEL_TYPE_INSTAGRAM

    def validate(
        self, publication: Publication, target: PublicationTarget
    ) -> list[str]:
        errors: list[str] = []
        media = publication.media or []
        post_type = _post_type(target)
        if post_type not in POST_TYPES:
            errors.append(
                "Tipo de publicación de Instagram inválido: usá feed, reels o story."
            )
            return errors
        if len(target_text(publication, target)) > CAPTION_MAX:
            errors.append(
                f"El texto para Instagram supera los {CAPTION_MAX} caracteres."
            )
        if not media:
            errors.append("Instagram necesita al menos una imagen o un video.")
        elif post_type == "feed" and len(media) > CAROUSEL_MAX:
            errors.append(
                f"Un carrusel de Instagram admite hasta {CAROUSEL_MAX} imágenes o videos."
            )
        elif post_type == "reels" and (
            len(media) != 1 or media[0]["type"] != "video"
        ):
            errors.append("Un reel de Instagram lleva exactamente un video.")
        elif post_type == "story" and len(media) != 1:
            errors.append(
                "Una historia de Instagram lleva exactamente una imagen o un video."
            )
        return errors

    async def publish(
        self,
        session: AsyncSession,
        publication: Publication,
        target: PublicationTarget,
    ) -> PublishResult:
        from app.domains.instagram import publishing_service as ig
        from app.domains.instagram.publisher import is_throttle_error

        inbox = await session.get(Inbox, target.inbox_id)
        if inbox is None:
            return PublishResult(
                ok=False,
                error_code="missing_inbox",
                error_message="El canal de Instagram ya no existe.",
            )

        post = None
        existing_id = (target.extra or {}).get("instagram_post_id")
        if existing_id is not None:
            post = await ig.get_post(
                session, account_id=target.account_id, post_id=existing_id
            )
        if post is None:
            media_type, source = build_instagram_post(publication, target)
            text = target_text(publication, target)
            try:
                post = await ig.create_post(
                    session,
                    account_id=target.account_id,
                    inbox_id=target.inbox_id,
                    channel_instagram_id=inbox.channel_id,
                    media_type=media_type,
                    source=source,
                    caption=text or None,
                )
            except ChatwootHTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, dict) else {}
                return PublishResult(
                    ok=False,
                    error_code="invalid_post",
                    error_message=detail.get("message")
                    or "Instagram rechazó la publicación.",
                )
        elif post.state == "failed":
            post = await ig.reset_for_retry(session, post=post)

        extra = {"instagram_post_id": post.id}
        if post.state == "pending":
            post = await ig.publish_post(session, post_id=post.id)

        if post.state == "published":
            return PublishResult(
                ok=True,
                external_id=post.ig_media_id,
                permalink=post.ig_permalink,
                extra=extra,
            )
        return PublishResult(
            ok=False,
            extra=extra,
            error_code=post.error_code or "publish_failed",
            error_message=post.error_message
            or "Instagram no pudo publicar el contenido.",
            retryable=is_throttle_error(post.error_code),
        )


__all__ = ["InstagramAdapter", "build_instagram_post"]
