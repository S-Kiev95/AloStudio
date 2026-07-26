"""Service layer for Instagram publishing.

Read + validation + the full publish state machine. The Meta Graph
HTTP calls live in :mod:`app.domains.instagram.publisher` (which never
raises — it returns result dataclasses with ``ok``/``error_code``); this
module orchestrates them: ``create_post`` → ``publish_post`` drives a
post through container creation → polling → ``media_publish``, stamping
``error_code`` + flipping to ``failed`` on any Meta-side failure instead
of raising into the worker.

State machine (see :func:`_validate_state_transition`):
  pending → publishing → published → deleted, with failed as the
  catch-all and ``failed → pending`` for operator/throttle retries.

History note: I.1 shipped this as a read+state-machine skeleton (Meta
calls stubbed); I.2–I.6 wired the real publisher, carousel, stories,
and delete paths. The skeleton framing is historical — every path here
is live.
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
    the param.

    ``VIDEO`` is folded to ``REELS``: Meta deprecated single feed videos —
    container creation now 400s with subcode 2207067 ("El valor VIDEO para
    media_type es obsoleto. Usa REELS") — and a Reel surfaces in the feed
    just the same. Accepting VIDEO here keeps older API callers working.
    """
    if raw == "VIDEO":
        return "REELS"
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
    product_ids: list[int] | None = None,
) -> InstagramPost:
    """Persist a publish request in ``pending`` state.

    The ARQ task that actually creates Meta containers + polls + calls
    ``/media_publish`` is wired in Milestone I.2. Here we just persist
    + validate so the dashboard can show "Queued at HH:MM" immediately.

    ``product_ids`` (I.11) optionally links the post/story to catalogue
    products so an AI agent has product context when an IG user later
    comments/DMs about it. The ids must belong to the same account.
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
    if product_ids:
        await set_post_products(
            session,
            account_id=account_id,
            post=post,
            product_ids=product_ids,
        )
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
    stmt = stmt.order_by(InstagramPost.id.desc())
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
# Products (I.11) — link a post/story to catalogue products + resolvers
# ---------------------------------------------------------------------------
async def set_post_products(
    session: AsyncSession,
    *,
    account_id: int,
    post: InstagramPost,
    product_ids: list[int],
) -> None:
    """Replace the post's product links with ``product_ids``.

    The ids must belong to ``account_id`` (422 otherwise). Idempotent —
    existing links are cleared first, so this also works as an update.
    """
    from app.domains.instagram.models import InstagramPostProduct
    from app.domains.products.models import Product

    # Dedupe while keeping order.
    ids = list(dict.fromkeys(product_ids))
    if ids:
        found = set(
            (
                await session.exec(
                    select(Product.id).where(
                        Product.account_id == account_id,
                        Product.id.in_(ids),
                    )
                )
            ).all()
        )
        missing = [i for i in ids if i not in found]
        if missing:
            raise ChatwootHTTPException(
                status_code=422,
                detail={"message": f"unknown product ids: {missing}"},
            )

    existing = (
        await session.exec(
            select(InstagramPostProduct).where(
                InstagramPostProduct.post_id == post.id
            )
        )
    ).all()
    for row in existing:
        await session.delete(row)
    await session.flush()
    for pid in ids:
        session.add(
            InstagramPostProduct(post_id=post.id, product_id=pid)
        )
    await session.flush()


async def products_for_post(
    session: AsyncSession, *, post_id: int
) -> list[Any]:
    """The catalogue products linked to a post (ordered by id)."""
    from app.domains.instagram.models import InstagramPostProduct
    from app.domains.products.models import Product

    stmt = (
        select(Product)
        .join(
            InstagramPostProduct,
            InstagramPostProduct.product_id == Product.id,  # type: ignore[arg-type]
        )
        .where(InstagramPostProduct.post_id == post_id)
        .order_by(Product.id.asc())
    )
    return list((await session.exec(stmt)).all())


async def products_for_media(
    session: AsyncSession, *, account_id: int, ig_media_id: str
) -> list[Any]:
    """The products linked to the post whose ``ig_media_id`` matches.

    This is the AI-context hook: when a comment/DM arrives on a media,
    resolve *media → post → products* so an agent knows which product(s)
    the conversation is about. Returns ``[]`` when the media isn't ours
    or has no linked products.
    """
    from app.domains.instagram.models import InstagramPostProduct
    from app.domains.products.models import Product

    stmt = (
        select(Product)
        .join(
            InstagramPostProduct,
            InstagramPostProduct.product_id == Product.id,  # type: ignore[arg-type]
        )
        .join(
            InstagramPost,
            InstagramPost.id == InstagramPostProduct.post_id,  # type: ignore[arg-type]
        )
        .where(
            InstagramPost.account_id == account_id,
            InstagramPost.ig_media_id == ig_media_id,
        )
        .order_by(Product.id.asc())
    )
    return list((await session.exec(stmt)).all())


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
        stmt = stmt.where(InstagramComment.hidden.is_(False))
    stmt = stmt.order_by(InstagramComment.ig_created_at.asc().nullslast())  # type: ignore[union-attr]
    return list((await session.exec(stmt)).all())


# ---------------------------------------------------------------------------
# Meta-side actions (Milestones I.2-I.7 wire these — stubs here)
# ---------------------------------------------------------------------------
def _augment_throttle(
    error_code: str | None, error_message: str | None
) -> str | None:
    """Tag a failure message when the error is a Meta throttle code, so
    the dashboard + the worker's retry path can recognise rate-limiting
    distinctly from a hard failure."""
    from app.domains.instagram.publisher import is_throttle_error

    if is_throttle_error(error_code):
        return f"[rate-limited] {error_message or ''}".strip()
    return error_message


async def reset_for_retry(
    session: AsyncSession, *, post: InstagramPost
) -> InstagramPost:
    """Flip a ``failed`` post back to ``pending`` so the worker can
    re-attempt it (used by the throttle backoff path). No-op on posts
    that aren't ``failed``."""
    if post.state != "failed":
        return post
    return await transition_post_state(
        session, post=post, new_state="pending"
    )


async def _poll_container_and_record(
    session: AsyncSession,
    *,
    post: InstagramPost,
    channel: Any,
    container_id: str,
    sleep_fn=None,
):
    """Poll one container to a terminal status_code and stamp the
    matching ``instagram_post_containers`` row for audit. Returns the
    poller's :class:`StatusResult`."""
    from app.domains.instagram import poller

    poll_kwargs: dict[str, Any] = {}
    if sleep_fn is not None:
        poll_kwargs["sleep_fn"] = sleep_fn
    status = await poller.poll_until_terminal(
        channel, container_id=container_id, **poll_kwargs
    )
    containers = await list_containers(session, post_id=post.id)
    for c in containers:
        if c.ig_container_id == container_id:
            c.status_code = status.status_code or "ERROR"
            session.add(c)
            await session.flush()
            break
    return status


async def _finalize_publish(
    session: AsyncSession,
    *,
    post: InstagramPost,
    channel: Any,
    creation_id: str,
) -> InstagramPost:
    """``/media_publish`` the FINISHED container, fetch the permalink
    (best-effort), and flip the post to ``published`` — or to
    ``failed`` if the publish call errors. Shared by the single-
    container (IMAGE/VIDEO/REELS) and carousel paths."""
    from datetime import UTC, datetime

    from app.domains.instagram import publisher

    publish_res = await publisher.publish_container(
        channel, creation_id=creation_id
    )
    if not publish_res.ok or publish_res.ig_media_id is None:
        return await transition_post_state(
            session,
            post=post,
            new_state="failed",
            error_code=publish_res.error_code,
            error_message=_augment_throttle(
                publish_res.error_code, publish_res.error_message
            ),
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


async def _publish_carousel(
    session: AsyncSession,
    *,
    post: InstagramPost,
    channel: Any,
    sleep_fn=None,
) -> InstagramPost:
    """Carousel (I.4) — create one child container per source child,
    poll each to FINISHED, then create + poll + publish the parent.

    Container positions: children at ``1..N`` (creation order), parent
    at ``0`` (created last, after every child is FINISHED — Meta rejects
    a parent whose children aren't ready).

    Children are polled sequentially. Meta's 60s cadence means real
    videos finish around the same wall-clock time regardless; the
    single async session also makes sequential the safe choice over
    ``asyncio.gather`` here.
    """
    from app.domains.instagram import publisher

    source = post.source or {}
    children = source.get("children") or []
    # ``create_post`` already enforced 1-10 children each carrying an
    # image_url or video_url; re-guard defensively for direct callers.
    if not isinstance(children, list) or not children:
        return await transition_post_state(
            session,
            post=post,
            new_state="failed",
            error_code="missing_children",
            error_message="source.children empty at publish time",
        )
    if len(children) > 10:
        return await transition_post_state(
            session,
            post=post,
            new_state="failed",
            error_code="too_many_children",
            error_message="CAROUSEL accepts at most 10 children",
        )

    # 1) Create every child container.
    child_ids: list[str] = []
    for idx, child in enumerate(children, start=1):
        if not isinstance(child, dict):
            child = {}
        if child.get("video_url"):
            params = publisher.build_video_container_params(
                media_type="VIDEO",
                video_url=child["video_url"],
                is_carousel_item=True,
            )
        elif child.get("image_url"):
            params = publisher.build_image_container_params(
                image_url=child["image_url"], is_carousel_item=True
            )
        else:
            return await transition_post_state(
                session,
                post=post,
                new_state="failed",
                error_code="bad_carousel_child",
                error_message=(
                    f"carousel child {idx} has no image_url/video_url"
                ),
            )
        res = await publisher.create_container(channel, params=params)
        if not res.ok or res.container_id is None:
            return await transition_post_state(
                session,
                post=post,
                new_state="failed",
                error_code=res.error_code,
                error_message=_augment_throttle(
                    res.error_code, res.error_message
                ),
            )
        await add_container(
            session,
            post=post,
            ig_container_id=res.container_id,
            position=idx,
        )
        child_ids.append(res.container_id)

    # 2) Poll every child to FINISHED.
    for cid in child_ids:
        status = await _poll_container_and_record(
            session,
            post=post,
            channel=channel,
            container_id=cid,
            sleep_fn=sleep_fn,
        )
        if status.status_code != "FINISHED":
            return await transition_post_state(
                session,
                post=post,
                new_state="failed",
                error_code=status.status_code or status.error or "poll_failed",
                error_message=(
                    status.error or f"carousel child {cid} not FINISHED"
                ),
            )

    # 3) Create the parent container referencing the FINISHED children.
    parent_params: dict[str, Any] = {
        "media_type": "CAROUSEL",
        "children": ",".join(child_ids),
    }
    if post.caption:
        parent_params["caption"] = post.caption
    parent_res = await publisher.create_container(
        channel, params=parent_params
    )
    if not parent_res.ok or parent_res.container_id is None:
        return await transition_post_state(
            session,
            post=post,
            new_state="failed",
            error_code=parent_res.error_code,
            error_message=_augment_throttle(
                parent_res.error_code, parent_res.error_message
            ),
        )
    await add_container(
        session,
        post=post,
        ig_container_id=parent_res.container_id,
        position=0,
    )

    # 4) Poll the parent, then publish.
    parent_status = await _poll_container_and_record(
        session,
        post=post,
        channel=channel,
        container_id=parent_res.container_id,
        sleep_fn=sleep_fn,
    )
    if parent_status.status_code != "FINISHED":
        return await transition_post_state(
            session,
            post=post,
            new_state="failed",
            error_code=(
                parent_status.status_code
                or parent_status.error
                or "poll_failed"
            ),
            error_message=(
                parent_status.error or "carousel parent not FINISHED"
            ),
        )

    return await _finalize_publish(
        session,
        post=post,
        channel=channel,
        creation_id=parent_res.container_id,
    )


async def _publish_dispatch(
    session: AsyncSession,
    *,
    post: InstagramPost,
    channel: Any,
    sleep_fn=None,
) -> InstagramPost:
    """The publish state machine for one post, run inside the channel's
    Graph host context (Facebook vs Instagram Login — see
    :func:`publish_post`). Split out so the host contextvar wraps every
    Meta call without re-indenting the whole body."""
    from app.core.config import get_settings
    from app.domains.instagram import publisher

    await transition_post_state(
        session, post=post, new_state="publishing"
    )

    # ---- Quota pre-check (I.9, opt-in) ----
    # Saves a doomed container create when the 24h cap is already hit.
    # Best-effort: a failed quota call doesn't block publishing.
    if get_settings().meta_check_publishing_quota:
        quota = await publisher.fetch_publishing_limit(channel)
        if quota.exceeded:
            return await transition_post_state(
                session,
                post=post,
                new_state="failed",
                error_code="quota_exceeded",
                error_message=(
                    f"publishing quota reached "
                    f"({quota.quota_usage}/{quota.quota_total} in 24h)"
                ),
            )

    # ---- Carousel (I.4): multi-container orchestration ----
    if post.media_type == "CAROUSEL":
        return await _publish_carousel(
            session, post=post, channel=channel, sleep_fn=sleep_fn
        )

    # ---- Build the container params per media type ----
    # IMAGE (I.2) + VIDEO/REELS (I.3) all take the single-container
    # path below — only the param dict differs. STORIES (I.5) still
    # raises a clear ``failed`` here.
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
    elif post.media_type == "STORIES":
        image_url = source.get("image_url")
        video_url = source.get("video_url")
        if not (image_url or video_url):
            missing_field_error = (
                "missing_story_source",
                "source.image_url or source.video_url absent at publish time",
            )
        else:
            params = publisher.build_story_container_params(
                image_url=image_url, video_url=video_url
            )
    else:
        # Defensive fallback — ``media_type`` is validated at
        # create_post, so an unknown type shouldn't reach here.
        return await transition_post_state(
            session,
            post=post,
            new_state="failed",
            error_code="unsupported_media_type",
            error_message=f"{post.media_type} is not a supported media type",
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
            error_message=_augment_throttle(
                container_res.error_code, container_res.error_message
            ),
        )

    await add_container(
        session,
        post=post,
        ig_container_id=container_res.container_id,
        position=0,
    )

    status = await _poll_container_and_record(
        session,
        post=post,
        channel=channel,
        container_id=container_res.container_id,
        sleep_fn=sleep_fn,
    )
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

    return await _finalize_publish(
        session,
        post=post,
        channel=channel,
        creation_id=container_res.container_id,
    )


async def publish_post(
    session: AsyncSession,
    *,
    post_id: int,
    sleep_fn=None,
) -> InstagramPost:
    """Drive ``post_id`` through container creation → polling →
    publish on Meta.

    ``IMAGE`` (I.2), ``VIDEO`` / ``REELS`` (I.3) and ``STORIES`` (I.5)
    all share the single-container path (create → poll status_code →
    media_publish), differing only in the container params. CAROUSEL
    (I.4) takes the multi-container path in :func:`_publish_carousel`
    (per-child container → poll all → parent → publish). An unknown
    media type (which create_post validation already rejects) flips the
    post to ``failed`` rather than crashing the worker.

    The container is created HERE (in the task body), not at
    create-post time — Meta containers expire after 24h, so a post
    scheduled days ahead must defer container creation until fire
    time. See PLAN.instagram-graph.md.

    ``sleep_fn`` is forwarded to the poller so tests run instantly.

    Returns the post in its terminal state (published / failed).
    Never raises on Meta-side failures — stamps ``error_code`` /
    ``error_message`` + flips to ``failed`` instead.

    The whole state machine runs inside the channel's Graph host context
    (Facebook Login → graph.facebook.com, Instagram Login →
    graph.instagram.com) — see :func:`_publish_dispatch` + graph.py.
    """
    from app.domains.inboxes.models import InstagramChannel
    from app.domains.instagram import connect_service, graph

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

    # Select the Graph host (Facebook vs Instagram Login) for the whole
    # operation, then run the state machine inside it.
    setting = await connect_service.get_channel_setting(
        session, channel_instagram_id=post.channel_instagram_id
    )
    with graph.graph_host(
        graph.host_for_login_type(
            setting.login_type if setting else None
        )
    ):
        return await _publish_dispatch(
            session, post=post, channel=channel, sleep_fn=sleep_fn
        )


async def delete_media_on_meta(
    session: AsyncSession,
    *,
    account_id: int,
    post_id: int,
) -> InstagramPost:
    """Call ``DELETE /{ig-media-id}`` on Meta + flip our row to
    ``deleted`` (Milestone I.6).

    Only ``published`` posts (which actually have an ``ig_media_id`` on
    Meta) can be deleted. Other states have nothing on Meta to remove,
    so they 422 here — the dashboard handles local-only cleanup of
    pending/failed rows separately.

    Unlike the publish path (a background worker that swallows errors
    and stamps ``failed``), delete is an interactive admin action, so a
    Meta-side failure surfaces as a ``ChatwootHTTPException`` for the
    caller to see — but we still stamp ``error_code`` / ``error_message``
    on the row for audit before raising.
    """
    from app.domains.inboxes.models import InstagramChannel
    from app.domains.instagram import publisher

    post = await get_post(session, account_id=account_id, post_id=post_id)
    if post is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    if post.state == "deleted":
        # Idempotent: already gone on Meta.
        return post
    if post.state != "published" or not post.ig_media_id:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": "only published posts can be deleted on Instagram"
            },
        )

    channel = await session.get(
        InstagramChannel, post.channel_instagram_id
    )
    if channel is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "instagram channel row not found"},
        )

    # Capability gate (I.10): Meta's DELETE media only works on Facebook
    # Login connections. Instagram Login channels must remove the post
    # from the IG app.
    from app.domains.instagram.connect_service import can_delete_media

    if not await can_delete_media(
        session, channel_instagram_id=post.channel_instagram_id
    ):
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": (
                    "delete unavailable on Instagram Login connections "
                    "— remove the post from the Instagram app"
                )
            },
        )

    res = await publisher.delete_media(
        channel, ig_media_id=post.ig_media_id
    )
    if not res.ok:
        # Stamp the failure for audit, then surface it to the caller.
        post.error_code = res.error_code
        post.error_message = res.error_message
        session.add(post)
        await session.flush()
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": res.error_message or "instagram delete failed",
                "code": res.error_code,
            },
        )

    return await transition_post_state(
        session, post=post, new_state="deleted"
    )


def _parse_ig_timestamp(raw: str | None) -> datetime | None:
    """Best-effort parse of Meta's comment ``timestamp`` (ISO 8601,
    usually ``2026-05-20T12:00:00+0000``). Returns None if absent or
    unparseable — the row just keeps a null ``ig_created_at``."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        # Meta sometimes emits ``+0000`` instead of ``+00:00``.
        try:
            if len(raw) >= 5 and raw[-5] in "+-" and raw[-3] != ":":
                return datetime.fromisoformat(f"{raw[:-2]}:{raw[-2:]}")
        except ValueError:
            return None
    return None


async def _graph_host_for_channel(session: AsyncSession, channel: Any) -> str:
    """The Graph host for a channel, from its connection ``login_type``
    (Facebook → graph.facebook.com, Instagram → graph.instagram.com)."""
    from app.domains.instagram import connect_service, graph

    setting = await connect_service.get_channel_setting(
        session, channel_instagram_id=channel.id
    )
    return graph.host_for_login_type(
        setting.login_type if setting else None
    )


async def get_comment(
    session: AsyncSession, *, account_id: int, comment_id: int
) -> InstagramComment | None:
    """Fetch a local comment row scoped to the account (the moderation
    endpoints address comments by our row id, not the IG id)."""
    return (
        await session.exec(
            select(InstagramComment).where(
                InstagramComment.id == comment_id,
                InstagramComment.account_id == account_id,
            )
        )
    ).first()


async def list_comments_on_meta(
    session: AsyncSession,
    *,
    channel: Any,
    account_id: int,
    ig_media_id: str,
) -> list[InstagramComment]:
    """Live-fetch comments for a media from Meta, upsert each into the
    local mirror, and return the stored rows (hidden included).

    A Meta-side failure surfaces as a 422 — the caller is interactive."""
    from app.domains.instagram import comments_client, graph

    host = await _graph_host_for_channel(session, channel)
    with graph.graph_host(host):
        res = await comments_client.fetch_comments(
            channel, ig_media_id=ig_media_id
        )
    if not res.ok:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": res.error_message or "instagram comment fetch failed",
                "code": res.error_code,
            },
        )
    for node in res.comments:
        await upsert_comment(
            session,
            account_id=account_id,
            channel_instagram_id=channel.id,
            ig_comment_id=node.ig_comment_id,
            ig_media_id=ig_media_id,
            parent_comment_id=node.parent_comment_id,
            from_username=node.username,
            from_id=node.from_id,
            text=node.text,
            hidden=node.hidden,
            ig_created_at=_parse_ig_timestamp(node.timestamp),
        )
    return await list_comments_for_media(
        session,
        account_id=account_id,
        ig_media_id=ig_media_id,
        include_hidden=True,
    )


async def post_comment_on_meta(
    session: AsyncSession,
    *,
    channel: Any,
    account_id: int,
    ig_media_id: str,
    message: str,
) -> InstagramComment:
    """``POST /{ig-media-id}/comments`` then mirror the new comment
    locally. Returns the stored row (Milestone I.7)."""
    from app.domains.instagram import comments_client, graph

    host = await _graph_host_for_channel(session, channel)
    with graph.graph_host(host):
        res = await comments_client.create_comment(
            channel, ig_media_id=ig_media_id, message=message
        )
    if not res.ok or res.ig_comment_id is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": res.error_message or "instagram comment failed",
                "code": res.error_code,
            },
        )
    return await upsert_comment(
        session,
        account_id=account_id,
        channel_instagram_id=channel.id,
        ig_comment_id=res.ig_comment_id,
        ig_media_id=ig_media_id,
        text=message,
    )


async def reply_comment_on_meta(
    session: AsyncSession,
    *,
    channel: Any,
    account_id: int,
    parent_comment: InstagramComment,
    message: str,
) -> InstagramComment:
    """``POST /{ig-comment-id}/replies`` then mirror the reply locally
    with ``parent_comment_id`` set (Milestone I.7)."""
    from app.domains.instagram import comments_client, graph

    host = await _graph_host_for_channel(session, channel)
    with graph.graph_host(host):
        res = await comments_client.create_reply(
            channel,
            ig_comment_id=parent_comment.ig_comment_id,
            message=message,
        )
    if not res.ok or res.ig_comment_id is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": res.error_message or "instagram reply failed",
                "code": res.error_code,
            },
        )
    return await upsert_comment(
        session,
        account_id=account_id,
        channel_instagram_id=channel.id,
        ig_comment_id=res.ig_comment_id,
        ig_media_id=parent_comment.ig_media_id,
        parent_comment_id=parent_comment.ig_comment_id,
        text=message,
    )


async def hide_comment_on_meta(
    session: AsyncSession,
    *,
    channel: Any,
    comment: InstagramComment,
    hide: bool,
) -> InstagramComment:
    """``POST /{ig-comment-id}?hide=true|false`` then update the local
    row's ``hidden`` flag (Milestone I.7)."""
    from app.domains.instagram import comments_client, graph

    host = await _graph_host_for_channel(session, channel)
    with graph.graph_host(host):
        res = await comments_client.set_hidden(
            channel, ig_comment_id=comment.ig_comment_id, hide=hide
        )
    if not res.ok:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": res.error_message or "instagram hide failed",
                "code": res.error_code,
            },
        )
    comment.hidden = hide
    session.add(comment)
    await session.flush()
    await session.refresh(comment)
    return comment


async def delete_comment_on_meta(
    session: AsyncSession,
    *,
    channel: Any,
    comment: InstagramComment,
) -> None:
    """``DELETE /{ig-comment-id}`` then drop the local mirror row
    (Milestone I.7)."""
    from app.domains.instagram import comments_client, graph

    host = await _graph_host_for_channel(session, channel)
    with graph.graph_host(host):
        res = await comments_client.delete_comment(
            channel, ig_comment_id=comment.ig_comment_id
        )
    if not res.ok:
        raise ChatwootHTTPException(
            status_code=422,
            detail={
                "message": res.error_message or "instagram comment delete failed",
                "code": res.error_code,
            },
        )
    await session.delete(comment)
    await session.flush()


__all__ = [
    "add_container",
    "create_post",
    "delete_comment_on_meta",
    "delete_media_on_meta",
    "get_comment",
    "get_post",
    "hide_comment_on_meta",
    "list_comments_for_media",
    "list_comments_on_meta",
    "list_containers",
    "list_posts",
    "post_comment_on_meta",
    "products_for_media",
    "products_for_post",
    "publish_post",
    "reply_comment_on_meta",
    "reset_for_retry",
    "set_post_products",
    "transition_post_state",
    "upsert_comment",
]
