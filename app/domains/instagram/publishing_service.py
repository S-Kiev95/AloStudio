"""Service layer for Instagram publishing (skeleton — Milestone I.1).

This file ships the **read + state-machine** surface only. Every
function that would call Meta's Graph API raises ``NotImplementedError``
with a reference to the milestone that wires it. The full publisher
lives in :mod:`app.domains.instagram.publisher` (Milestone I.2+).

Why split:
  * I.1 lets the dashboard render the publish history list and the
    state machine for an already-pending post without needing a Meta
    sandbox or env vars set.
  * Tests in I.1 exercise schema + service signatures only — they
    don't depend on ``respx`` because no HTTP call lands.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.instagram.models import (
    INSTAGRAM_MEDIA_TYPES,
    INSTAGRAM_POST_STATES,
    InstagramComment,
    InstagramPost,
    InstagramPostContainer,
)


# ---------------------------------------------------------------------------
# Validation helpers (shared between create + update paths)
# ---------------------------------------------------------------------------
def _validate_media_type(raw: Any) -> str:
    """Mirror Meta's ``media_type`` enum (uppercase). We carry
    ``IMAGE`` ourselves for the single-image case where Meta omits
    the param."""
    if not isinstance(raw, str) or raw not in INSTAGRAM_MEDIA_TYPES:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    f"media_type must be one of "
                    f"{', '.join(INSTAGRAM_MEDIA_TYPES)}"
                ),
            },
        )
    return raw


def _validate_source(media_type: str, source: Any) -> dict[str, Any]:
    """Lightweight shape check on the ``source`` JSONB.

    The full Meta-side validation (URL reachable, image dims, video
    codec) happens at container creation time in Milestone I.2. Here
    we just enforce the obvious shape per ``media_type``:

      * IMAGE / STORIES with image: ``image_url`` required
      * VIDEO / REELS / STORIES with video: ``video_url`` required
      * CAROUSEL: ``children`` array (1-10 entries) required
    """
    if not isinstance(source, dict):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "source must be a JSON object"},
        )
    if media_type == "IMAGE":
        if not source.get("image_url"):
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": "source.image_url required for IMAGE"},
            )
    elif media_type in ("VIDEO", "REELS"):
        if not source.get("video_url"):
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": f"source.video_url required for {media_type}"
                },
            )
    elif media_type == "STORIES":
        if not (source.get("image_url") or source.get("video_url")):
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "source.image_url or source.video_url required for STORIES"
                },
            )
    elif media_type == "CAROUSEL":
        children = source.get("children")
        if not isinstance(children, list) or not children:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "source.children must be a non-empty array for CAROUSEL"
                },
            )
        if len(children) > 10:
            raise ChatwootHTTPException(
                status_code=422,
                detail={
                    "message": "CAROUSEL accepts at most 10 children"
                },
            )
        for i, child in enumerate(children):
            if not isinstance(child, dict) or not (
                child.get("image_url") or child.get("video_url")
            ):
                raise ChatwootHTTPException(
                    status_code=422,
                    detail={
                        "message": (
                            f"source.children[{i}] needs image_url or video_url"
                        )
                    },
                )
    return source


def _validate_caption(raw: Any) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "caption must be a string"},
        )
    # Meta's documented cap is 2200 chars.
    if len(raw) > 2200:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "caption exceeds 2200 chars"},
        )
    return raw


def _validate_state_transition(current: str, new: str) -> str:
    """State machine guard.

    Allowed transitions:
      pending    → publishing | failed
      publishing → published | failed
      published  → deleted
      failed     → pending (operator-driven retry)
      deleted    → (terminal)
    """
    if new not in INSTAGRAM_POST_STATES:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": f"unknown state: {new!r}"},
        )
    transitions = {
        "pending": {"publishing", "failed"},
        "publishing": {"published", "failed"},
        "published": {"deleted"},
        "failed": {"pending"},
        "deleted": set(),
    }
    if new not in transitions.get(current, set()):
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": f"cannot transition {current!r} → {new!r}"
            },
        )
    return new


# ---------------------------------------------------------------------------
# Posts CRUD (read + state mutation only; publish flow lands in I.2)
# ---------------------------------------------------------------------------
async def create_post(
    session: AsyncSession,
    *,
    account_id: int,
    inbox_id: int,
    channel_instagram_id: int,
    media_type: str,
    source: dict[str, Any],
    caption: str | None = None,
    scheduled_for: datetime | None = None,
) -> InstagramPost:
    """Persist a publish request in ``pending`` state.

    The ARQ task that actually creates Meta containers + polls + calls
    ``/media_publish`` is wired in Milestone I.2. Here we just persist
    + validate so the dashboard can show "Queued at HH:MM" immediately.
    """
    media_type = _validate_media_type(media_type)
    source = _validate_source(media_type, source)
    caption = _validate_caption(caption)

    post = InstagramPost(
        account_id=account_id,
        inbox_id=inbox_id,
        channel_instagram_id=channel_instagram_id,
        state="pending",
        media_type=media_type,
        caption=caption,
        source=source,
        scheduled_for=scheduled_for,
    )
    session.add(post)
    await session.flush()
    await session.refresh(post)
    return post


async def list_posts(
    session: AsyncSession,
    *,
    account_id: int,
    state: str | None = None,
    channel_instagram_id: int | None = None,
    page: int = 1,
    per_page: int = 25,
) -> list[InstagramPost]:
    per_page = min(max(1, per_page), 100)
    page = max(1, page)
    stmt = select(InstagramPost).where(InstagramPost.account_id == account_id)
    if state is not None:
        stmt = stmt.where(InstagramPost.state == state)
    if channel_instagram_id is not None:
        stmt = stmt.where(
            InstagramPost.channel_instagram_id == channel_instagram_id
        )
    stmt = stmt.order_by(InstagramPost.id.desc())  # type: ignore[attr-defined]
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    return list((await session.exec(stmt)).all())


async def get_post(
    session: AsyncSession, *, account_id: int, post_id: int
) -> InstagramPost | None:
    return (
        await session.exec(
            select(InstagramPost).where(
                InstagramPost.id == post_id,
                InstagramPost.account_id == account_id,
            )
        )
    ).first()


async def transition_post_state(
    session: AsyncSession,
    *,
    post: InstagramPost,
    new_state: str,
    error_code: str | None = None,
    error_message: str | None = None,
    ig_media_id: str | None = None,
    ig_permalink: str | None = None,
    published_at: datetime | None = None,
) -> InstagramPost:
    """Atomic state-machine flip with side-effects.

    Used by the ARQ worker (Milestone I.2+) to advance pending →
    publishing → published, and by the delete service (I.6) to flip
    published → deleted.
    """
    new_state = _validate_state_transition(post.state, new_state)
    post.state = new_state
    if error_code is not None:
        post.error_code = error_code
    if error_message is not None:
        post.error_message = error_message
    if ig_media_id is not None:
        post.ig_media_id = ig_media_id
    if ig_permalink is not None:
        post.ig_permalink = ig_permalink
    if published_at is not None:
        post.published_at = published_at
    session.add(post)
    await session.flush()
    await session.refresh(post)
    return post


# ---------------------------------------------------------------------------
# Containers (created by the publisher worker — pure helpers here)
# ---------------------------------------------------------------------------
async def add_container(
    session: AsyncSession,
    *,
    post: InstagramPost,
    ig_container_id: str,
    position: int,
    status_code: str = "IN_PROGRESS",
) -> InstagramPostContainer:
    container = InstagramPostContainer(
        post_id=post.id,
        ig_container_id=ig_container_id,
        position=position,
        status_code=status_code,
    )
    session.add(container)
    await session.flush()
    await session.refresh(container)
    return container


async def list_containers(
    session: AsyncSession, *, post_id: int
) -> list[InstagramPostContainer]:
    return list(
        (
            await session.exec(
                select(InstagramPostContainer)
                .where(InstagramPostContainer.post_id == post_id)
                .order_by(InstagramPostContainer.position.asc())  # type: ignore[attr-defined]
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# Comments — read + record (write to Meta lands in I.7)
# ---------------------------------------------------------------------------
async def upsert_comment(
    session: AsyncSession,
    *,
    account_id: int,
    channel_instagram_id: int,
    ig_comment_id: str,
    ig_media_id: str,
    parent_comment_id: str | None = None,
    from_username: str | None = None,
    from_id: str | None = None,
    text: str | None = None,
    hidden: bool = False,
    ig_created_at: datetime | None = None,
    conversation_id: int | None = None,
) -> InstagramComment:
    """Idempotent upsert keyed on ``ig_comment_id``.

    The webhook receiver (I.8) is the main caller — Meta fires
    ``object=instagram&field=comments`` events out of order and
    occasionally duplicates, so we look up by IG-side id and update
    in place rather than relying on insert-and-handle-collision.
    """
    existing = (
        await session.exec(
            select(InstagramComment).where(
                InstagramComment.ig_comment_id == ig_comment_id
            )
        )
    ).first()
    if existing is not None:
        # Update mutable fields only.
        if text is not None:
            existing.text = text
        if hidden is not None:
            existing.hidden = hidden
        if conversation_id is not None:
            existing.conversation_id = conversation_id
        session.add(existing)
        await session.flush()
        await session.refresh(existing)
        return existing
    row = InstagramComment(
        account_id=account_id,
        channel_instagram_id=channel_instagram_id,
        ig_comment_id=ig_comment_id,
        ig_media_id=ig_media_id,
        parent_comment_id=parent_comment_id,
        from_username=from_username,
        from_id=from_id,
        text=text,
        hidden=hidden,
        ig_created_at=ig_created_at,
        conversation_id=conversation_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def list_comments_for_media(
    session: AsyncSession,
    *,
    account_id: int,
    ig_media_id: str,
    include_hidden: bool = False,
) -> list[InstagramComment]:
    stmt = select(InstagramComment).where(
        InstagramComment.account_id == account_id,
        InstagramComment.ig_media_id == ig_media_id,
    )
    if not include_hidden:
        stmt = stmt.where(InstagramComment.hidden.is_(False))  # type: ignore[union-attr]
    stmt = stmt.order_by(InstagramComment.ig_created_at.asc().nullslast())  # type: ignore[union-attr]
    return list((await session.exec(stmt)).all())


# ---------------------------------------------------------------------------
# Meta-side actions (Milestones I.2-I.7 wire these — stubs here)
# ---------------------------------------------------------------------------
async def publish_post(
    session: AsyncSession,
    *,
    post_id: int,
    sleep_fn=None,
) -> InstagramPost:
    """Drive ``post_id`` through container creation → polling →
    publish on Meta.

    Milestone I.2 handles ``media_type == "IMAGE"`` and I.3 adds
    ``VIDEO`` / ``REELS`` — all three share the single-container path
    (create → poll status_code → media_publish), differing only in the
    container params. CAROUSEL (I.4, multi-container) and STORIES (I.5)
    raise a clear ``not yet wired`` failure that flips the post to
    ``failed`` rather than crashing the worker.

    The container is created HERE (in the task body), not at
    create-post time — Meta containers expire after 24h, so a post
    scheduled days ahead must defer container creation until fire
    time. See PLAN.instagram-graph.md.

    ``sleep_fn`` is forwarded to the poller so tests run instantly.

    Returns the post in its terminal state (published / failed).
    Never raises on Meta-side failures — stamps ``error_code`` /
    ``error_message`` + flips to ``failed`` instead.
    """
    from datetime import UTC, datetime

    from app.domains.inboxes.models import InstagramChannel
    from app.domains.instagram import poller, publisher

    post = await session.get(InstagramPost, post_id)
    if post is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "instagram post not found"},
        )

    # Idempotency: only act on pending posts. A double-enqueue (REST +
    # scheduler racing) finds the post already publishing/published and
    # no-ops.
    if post.state != "pending":
        return post

    channel = await session.get(
        InstagramChannel, post.channel_instagram_id
    )
    if channel is None:
        return await transition_post_state(
            session,
            post=post,
            new_state="failed",
            error_code="missing_channel",
            error_message="instagram channel row not found",
        )

    await transition_post_state(
        session, post=post, new_state="publishing"
    )

    # ---- Build the container params per media type ----
    # IMAGE (I.2) + VIDEO/REELS (I.3) all take the single-container
    # path below — only the param dict differs. CAROUSEL (I.4, multi-
    # container) and STORIES (I.5) still raise a clear ``failed`` here.
    source = post.source or {}
    params: dict[str, Any] | None = None
    missing_field_error: tuple[str, str] | None = None

    if post.media_type == "IMAGE":
        image_url = source.get("image_url")
        if not image_url:
            missing_field_error = (
                "missing_image_url",
                "source.image_url absent at publish time",
            )
        else:
            params = publisher.build_image_container_params(
                image_url=image_url, caption=post.caption
            )
    elif post.media_type in ("VIDEO", "REELS"):
        video_url = source.get("video_url")
        if not video_url:
            missing_field_error = (
                "missing_video_url",
                "source.video_url absent at publish time",
            )
        else:
            params = publisher.build_video_container_params(
                media_type=post.media_type,
                video_url=video_url,
                caption=post.caption,
                cover_url=source.get("cover_url"),
                thumb_offset=source.get("thumb_offset"),
                share_to_feed=source.get("share_to_feed"),
                audio_name=source.get("audio_name"),
            )
    else:
        # CAROUSEL (I.4), STORIES (I.5) — not wired yet.
        return await transition_post_state(
            session,
            post=post,
            new_state="failed",
            error_code="unsupported_media_type",
            error_message=(
                f"{post.media_type} publishing wires in a later "
                "milestone (I.4 carousel, I.5 stories)"
            ),
        )

    if missing_field_error is not None:
        return await transition_post_state(
            session,
            post=post,
            new_state="failed",
            error_code=missing_field_error[0],
            error_message=missing_field_error[1],
        )
    assert params is not None

    container_res = await publisher.create_container(
        channel, params=params
    )
    if not container_res.ok or container_res.container_id is None:
        return await transition_post_state(
            session,
            post=post,
            new_state="failed",
            error_code=container_res.error_code,
            error_message=container_res.error_message,
        )

    await add_container(
        session,
        post=post,
        ig_container_id=container_res.container_id,
        position=0,
    )

    poll_kwargs: dict[str, Any] = {}
    if sleep_fn is not None:
        poll_kwargs["sleep_fn"] = sleep_fn
    status = await poller.poll_until_terminal(
        channel,
        container_id=container_res.container_id,
        **poll_kwargs,
    )
    # Refresh container row's status_code for audit.
    containers = await list_containers(session, post_id=post.id)
    if containers:
        containers[0].status_code = status.status_code or "ERROR"
        session.add(containers[0])
        await session.flush()

    if status.status_code != "FINISHED":
        return await transition_post_state(
            session,
            post=post,
            new_state="failed",
            # Prefer the terminal status_code (ERROR / EXPIRED); fall
            # back to the soft error label (timeout) when the poll
            # never got a status_code at all.
            error_code=status.status_code or status.error or "poll_failed",
            error_message=status.error or "container not FINISHED",
        )

    publish_res = await publisher.publish_container(
        channel, creation_id=container_res.container_id
    )
    if not publish_res.ok or publish_res.ig_media_id is None:
        return await transition_post_state(
            session,
            post=post,
            new_state="failed",
            error_code=publish_res.error_code,
            error_message=publish_res.error_message,
        )

    permalink = await publisher.fetch_permalink(
        channel, ig_media_id=publish_res.ig_media_id
    )
    return await transition_post_state(
        session,
        post=post,
        new_state="published",
        ig_media_id=publish_res.ig_media_id,
        ig_permalink=permalink,
        published_at=datetime.now(UTC),
    )


async def delete_media_on_meta(
    session: AsyncSession, *, post_id: int  # noqa: ARG001
) -> None:
    """Call ``DELETE /{ig-media-id}`` on Meta + flip our row to
    ``deleted``. Wired in Milestone I.6.
    """
    raise NotImplementedError("delete_media_on_meta wires in Milestone I.6")


async def post_comment_on_meta(
    session: AsyncSession,  # noqa: ARG001
    *,
    ig_media_id: str,  # noqa: ARG001
    message: str,  # noqa: ARG001
) -> str:
    """Call ``POST /{ig-media-id}/comments`` → returns the new
    comment id. Wired in Milestone I.7.
    """
    raise NotImplementedError("post_comment_on_meta wires in Milestone I.7")


async def reply_comment_on_meta(
    session: AsyncSession,  # noqa: ARG001
    *,
    ig_parent_comment_id: str,  # noqa: ARG001
    message: str,  # noqa: ARG001
) -> str:
    """Call ``POST /{ig-comment-id}/replies``. Wired in I.7."""
    raise NotImplementedError(
        "reply_comment_on_meta wires in Milestone I.7"
    )


async def hide_comment_on_meta(
    session: AsyncSession,  # noqa: ARG001
    *,
    ig_comment_id: str,  # noqa: ARG001
    hide: bool,  # noqa: ARG001
) -> None:
    """Call ``POST /{ig-comment-id}?hide=true|false``. Wired in I.7."""
    raise NotImplementedError(
        "hide_comment_on_meta wires in Milestone I.7"
    )


async def delete_comment_on_meta(
    session: AsyncSession,  # noqa: ARG001
    *,
    ig_comment_id: str,  # noqa: ARG001
) -> None:
    """Call ``DELETE /{ig-comment-id}``. Wired in I.7."""
    raise NotImplementedError(
        "delete_comment_on_meta wires in Milestone I.7"
    )


__all__ = [
    "add_container",
    "create_post",
    "delete_comment_on_meta",
    "delete_media_on_meta",
    "get_post",
    "hide_comment_on_meta",
    "list_comments_for_media",
    "list_containers",
    "list_posts",
    "post_comment_on_meta",
    "publish_post",
    "reply_comment_on_meta",
    "transition_post_state",
    "upsert_comment",
]
