"""Instagram webhook ``changes`` processor (I.8).

Phase 5e's :mod:`app.domains.instagram.incoming` handles the DM path
(``entry[].messaging[]``). This module handles the *other* half of the
``object=instagram`` webhook — the ``entry[].changes[]`` array Meta uses
for non-message events:

  * ``comments``       — a new comment (or reply) on owned media.
  * ``mentions``       — the business was @-mentioned in a comment.
  * ``story_insights`` — a story expired; Meta delivers its metrics.

Each change carries ``{"field": ..., "value": {...}}``. We resolve the
``InstagramChannel`` from ``entry.id`` (the IG Business account id),
then upsert into the local mirror tables. Unknown accounts / fields are
skipped (logged), never raised — the webhook always 200-acks.

Payload shape (changes variant):

    {
      "object": "instagram",
      "entry": [
        {
          "id": "<INSTAGRAM_ID>",
          "time": <s>,
          "changes": [
            {"field": "comments", "value": {
                "id": "<comment-id>", "text": "...",
                "from": {"id": "<igsid>", "username": "..."},
                "media": {"id": "<media-id>"},
                "parent_id": "<parent-comment-id>"}},
            {"field": "mentions", "value": {
                "media_id": "<media-id>", "comment_id": "<comment-id>"}},
            {"field": "story_insights", "value": {
                "media_id": "<media-id>", "impressions": N, "reach": N,
                "taps_forward": N, "taps_back": N, "exits": N,
                "replies": N}}
          ]
        }
      ]
    }

References: PLAN.instagram-graph.md (I.8, verified webhook fields).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.inboxes.models import InstagramChannel
from app.domains.instagram import publishing_service as svc
from app.domains.instagram.models import InstagramPost

log = logging.getLogger(__name__)


async def _resolve_channel(
    session: AsyncSession, *, instagram_id: str
) -> InstagramChannel | None:
    return (
        await session.exec(
            select(InstagramChannel).where(
                InstagramChannel.instagram_id == instagram_id
            )
        )
    ).first()


async def _handle_comment(
    session: AsyncSession,
    *,
    channel: InstagramChannel,
    value: dict[str, Any],
) -> bool:
    """Upsert one ``field=comments`` event into the local mirror."""
    ig_comment_id = value.get("id")
    _media = value.get("media")
    media: dict[str, Any] = _media if isinstance(_media, dict) else {}
    ig_media_id = value.get("media_id") or media.get("id")
    if not ig_comment_id or not ig_media_id:
        return False
    _frm = value.get("from")
    frm: dict[str, Any] = _frm if isinstance(_frm, dict) else {}
    await svc.upsert_comment(
        session,
        account_id=channel.account_id,
        channel_instagram_id=channel.id,
        ig_comment_id=str(ig_comment_id),
        ig_media_id=str(ig_media_id),
        parent_comment_id=(
            str(value["parent_id"]) if value.get("parent_id") else None
        ),
        from_username=frm.get("username"),
        from_id=(str(frm["id"]) if frm.get("id") else None),
        text=value.get("text"),
    )
    return True


async def _handle_mention(
    session: AsyncSession,
    *,
    channel: InstagramChannel,
    value: dict[str, Any],
) -> bool:
    """Record an @-mention. Comment mentions become a comment row;
    caption-only mentions (no ``comment_id``) are skipped — our mirror
    is comment-keyed."""
    comment_id = value.get("comment_id")
    media_id = value.get("media_id")
    if not comment_id or not media_id:
        return False
    await svc.upsert_comment(
        session,
        account_id=channel.account_id,
        channel_instagram_id=channel.id,
        ig_comment_id=str(comment_id),
        ig_media_id=str(media_id),
    )
    return True


async def _handle_story_insights(
    session: AsyncSession,
    *,
    channel: InstagramChannel,
    value: dict[str, Any],
) -> bool:
    """Stamp story metrics onto the matching published STORIES post.

    Skips (logs) when we have no local post for the media — the story
    may have been published outside AloStudio."""
    media_id = value.get("media_id")
    if not media_id:
        return False
    post = (
        await session.exec(
            select(InstagramPost).where(
                InstagramPost.account_id == channel.account_id,
                InstagramPost.ig_media_id == str(media_id),
            )
        )
    ).first()
    if post is None:
        log.info(
            "instagram.webhook.story_insights.no_post media_id=%s", media_id
        )
        return False
    metrics = {k: v for k, v in value.items() if k != "media_id"}
    post.insights = metrics
    session.add(post)
    await session.flush()
    return True


async def process_instagram_changes(
    session: AsyncSession, *, payload: dict[str, Any]
) -> dict[str, int]:
    """Process every ``entry[].changes[]`` item. Returns a per-field
    count of successfully-handled changes (for tests + logging)."""
    counts = {"comments": 0, "mentions": 0, "story_insights": 0}
    if str((payload or {}).get("object", "")).lower() != "instagram":
        return counts
    entries = payload.get("entry") or []
    if not isinstance(entries, list):
        return counts

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        ig_id = str(entry.get("id") or "")
        changes = entry.get("changes")
        if not ig_id or not isinstance(changes, list):
            continue
        channel = await _resolve_channel(session, instagram_id=ig_id)
        if channel is None:
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            field = str(change.get("field") or "")
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            handled = False
            if field == "comments":
                handled = await _handle_comment(
                    session, channel=channel, value=value
                )
                if handled:
                    counts["comments"] += 1
            elif field == "mentions":
                handled = await _handle_mention(
                    session, channel=channel, value=value
                )
                if handled:
                    counts["mentions"] += 1
            elif field == "story_insights":
                handled = await _handle_story_insights(
                    session, channel=channel, value=value
                )
                if handled:
                    counts["story_insights"] += 1
    return counts


__all__ = ["process_instagram_changes"]
