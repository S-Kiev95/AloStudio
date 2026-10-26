"""Publishing service — account-scoped CRUD, validation and the publish loop.

Network-agnostic on purpose: every network decision goes through the
adapter registry (``adapter_for_inbox`` when a target is created,
``adapter_for_network`` when it is published).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.models import Inbox
from app.domains.media_library import service as media_library
from app.domains.publishing.adapters import (
    PublishResult,
    adapter_for_inbox,
    adapter_for_network,
)
from app.domains.publishing.models import (
    MEDIA_TYPES,
    PUBLICATION_EDITABLE_STATES,
    PUBLICATION_STATE_DRAFT,
    PUBLICATION_STATE_FAILED,
    PUBLICATION_STATE_PARTIALLY_PUBLISHED,
    PUBLICATION_STATE_PUBLISHED,
    PUBLICATION_STATE_PUBLISHING,
    PUBLICATION_STATE_SCHEDULED,
    PUBLICATION_STATES,
    TARGET_STATE_FAILED,
    TARGET_STATE_PENDING,
    TARGET_STATE_PUBLISHED,
    TARGET_STATE_PUBLISHING,
    Publication,
    PublicationTarget,
)

log = logging.getLogger(__name__)

# A date this far in the past is still accepted as "now" (clock skew,
# a form submitted a few seconds after it was filled).
_PAST_GRACE = timedelta(minutes=1)


def _unprocessable(message: str, errors: list[str] | None = None) -> ChatwootHTTPException:
    detail: dict[str, Any] = {"message": message}
    if errors:
        detail["errors"] = errors
    return ChatwootHTTPException(status_code=422, detail=detail)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


async def _normalize_media(
    session: AsyncSession, *, account_id: int, raw: Any
) -> list[dict[str, Any]]:
    """Each item is either ``{"media_id": int}`` — an asset of the account's
    library, stored with its kind and a current link — or an external
    ``{"type", "url"}``."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise _unprocessable("media tiene que ser una lista")

    def _asset_id(item: Any) -> int | None:
        # ``bool`` is an ``int`` in Python: ``true`` must not mean asset 1.
        value = item.get("media_id") if isinstance(item, dict) else None
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    asset_ids = [i for i in (_asset_id(item) for item in raw) if i is not None]
    assets = await media_library.get_assets(
        session, account_id=account_id, asset_ids=asset_ids
    )
    media: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise _unprocessable(f"media[{i}] es inválido")
        if item.get("media_id") is not None:
            asset = assets.get(_asset_id(item))  # type: ignore[arg-type]
            if asset is None:
                raise _unprocessable(
                    f"media[{i}] no está en la biblioteca de esta cuenta"
                )
            media.append(
                {
                    "type": asset.kind,
                    "url": media_library.asset_public_url(asset),
                    "media_id": asset.id,
                }
            )
            continue
        kind = item.get("type")
        url = item.get("url")
        if kind not in MEDIA_TYPES:
            raise _unprocessable(
                f"media[{i}].type tiene que ser {' o '.join(MEDIA_TYPES)}"
            )
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise _unprocessable(f"media[{i}].url tiene que ser una URL pública")
        media.append({"type": kind, "url": url})
    return media


async def _refresh_library_links(
    session: AsyncSession, publication: Publication
) -> bool:
    """Re-sign the links of library media right before publishing: the
    stored ones expire, and a post can go out weeks after it was written.
    Returns False when an asset was deleted from the library meanwhile."""
    media = publication.media or []
    asset_ids = [m["media_id"] for m in media if m.get("media_id") is not None]
    if not asset_ids:
        return True
    assets = await media_library.get_assets(
        session, account_id=publication.account_id, asset_ids=asset_ids
    )
    if len(assets) != len(set(asset_ids)):
        return False
    publication.media = [
        {**m, "url": media_library.asset_public_url(assets[m["media_id"]])}
        if m.get("media_id") is not None
        else m
        for m in media
    ]
    session.add(publication)
    return True


async def list_channels(
    session: AsyncSession, *, account_id: int
) -> list[tuple[Inbox, str]]:
    """The account's inboxes that some adapter can publish to, with the
    adapter's network key."""
    inboxes = (
        await session.exec(
            select(Inbox)
            .where(Inbox.account_id == account_id)
            .order_by(Inbox.id)  # type: ignore[arg-type]
        )
    ).all()
    channels: list[tuple[Inbox, str]] = []
    for inbox in inboxes:
        adapter = adapter_for_inbox(inbox)
        if adapter is not None:
            channels.append((inbox, adapter.network))
    return channels


async def _build_targets(
    session: AsyncSession,
    *,
    account_id: int,
    raw_targets: Any,
) -> tuple[list[PublicationTarget], dict[int, Inbox]]:
    if not isinstance(raw_targets, list) or not raw_targets:
        raise _unprocessable("Elegí al menos un canal")
    inbox_ids = [t.get("inbox_id") for t in raw_targets if isinstance(t, dict)]
    if len(inbox_ids) != len(raw_targets) or not all(
        isinstance(i, int) for i in inbox_ids
    ):
        raise _unprocessable("Cada canal necesita su inbox_id")
    if len(set(inbox_ids)) != len(inbox_ids):
        raise _unprocessable("Un canal aparece dos veces")

    inboxes = {
        inbox.id: inbox
        for inbox in (
            await session.exec(
                select(Inbox).where(
                    Inbox.account_id == account_id,
                    Inbox.id.in_(inbox_ids),  # type: ignore[union-attr]
                )
            )
        ).all()
    }
    targets: list[PublicationTarget] = []
    for raw in raw_targets:
        inbox = inboxes.get(raw["inbox_id"])
        if inbox is None:
            raise _unprocessable(
                "El canal no existe o no pertenece a esta cuenta"
            )
        adapter = adapter_for_inbox(inbox)
        if adapter is None:
            raise _unprocessable(f"El canal {inbox.name} no puede publicar")
        settings = raw.get("settings") or {}
        if not isinstance(settings, dict):
            raise _unprocessable(f"settings de {inbox.name} es inválido")
        targets.append(
            PublicationTarget(
                account_id=account_id,
                inbox_id=inbox.id,
                network=adapter.network,
                settings=settings,
                content_override=raw.get("content_override"),
            )
        )
    return targets, inboxes


def _validate_targets(
    publication: Publication,
    targets: list[PublicationTarget],
    inboxes: dict[int, Inbox],
) -> None:
    errors: list[str] = []
    for target in targets:
        adapter = adapter_for_network(target.network)
        if adapter is None:
            continue
        name = inboxes[target.inbox_id].name
        errors.extend(
            f"{name}: {problem}"
            for problem in adapter.validate(publication, target)
        )
    if errors:
        raise _unprocessable("La publicación no se puede enviar así", errors)


def _resolve_schedule(
    *, draft: bool, scheduled_for: datetime | None
) -> tuple[str, datetime | None]:
    """State and date for a new or edited publication. Without a date it
    goes out now (the next scheduler tick, or right away when the caller
    enqueues it)."""
    if draft:
        return PUBLICATION_STATE_DRAFT, scheduled_for
    now = datetime.now(UTC)
    if scheduled_for is None:
        return PUBLICATION_STATE_SCHEDULED, now
    if scheduled_for < now - _PAST_GRACE:
        raise _unprocessable("La fecha de publicación tiene que ser futura")
    return PUBLICATION_STATE_SCHEDULED, scheduled_for


async def create_publication(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
    created_by_id: int | None = None,
) -> Publication:
    media = await _normalize_media(
        session, account_id=account_id, raw=payload.get("media")
    )
    state, scheduled_for = _resolve_schedule(
        draft=bool(payload.get("draft")),
        scheduled_for=_aware(payload.get("scheduled_for")),
    )
    publication = Publication(
        account_id=account_id,
        content=payload.get("content"),
        media=media,
        scheduled_for=scheduled_for,
        state=state,
        created_by_id=created_by_id,
    )
    targets, inboxes = await _build_targets(
        session, account_id=account_id, raw_targets=payload.get("targets")
    )
    _validate_targets(publication, targets, inboxes)

    session.add(publication)
    await session.flush()
    for target in targets:
        target.publication_id = publication.id  # type: ignore[assignment]
        session.add(target)
    await session.flush()
    await session.refresh(publication)
    return publication


async def get_publication(
    session: AsyncSession,
    *,
    account_id: int,
    publication_id: int,
    for_update: bool = False,
) -> Publication | None:
    """``for_update`` locks the row for an edit, so the state check and the
    change can't interleave with the scheduler claiming it."""
    stmt = (
        select(Publication)
        .where(
            Publication.id == publication_id,
            Publication.account_id == account_id,
        )
        .execution_options(populate_existing=True)
    )
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.exec(stmt)).first()


async def targets_by_publication(
    session: AsyncSession, *, publication_ids: list[int]
) -> dict[int, list[PublicationTarget]]:
    if not publication_ids:
        return {}
    rows = (
        await session.exec(
            select(PublicationTarget)
            .where(
                PublicationTarget.publication_id.in_(publication_ids)  # type: ignore[attr-defined]
            )
            .order_by(PublicationTarget.id)  # type: ignore[arg-type]
            .execution_options(populate_existing=True)
        )
    ).all()
    grouped: dict[int, list[PublicationTarget]] = {i: [] for i in publication_ids}
    for target in rows:
        grouped[target.publication_id].append(target)
    return grouped


async def list_publications(
    session: AsyncSession,
    *,
    account_id: int,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
    state: str | None = None,
    inbox_id: int | None = None,
    page: int = 1,
    per_page: int = 50,
) -> list[Publication]:
    """For the calendar: by date (the scheduled date, or the creation date
    of an undated draft), ascending. ``from`` inclusive, ``to`` exclusive."""
    per_page = min(max(1, per_page), 200)
    page = max(1, page)
    when = func.coalesce(Publication.scheduled_for, Publication.created_at)

    stmt = select(Publication).where(Publication.account_id == account_id)
    if starts_from is not None:
        stmt = stmt.where(when >= _aware(starts_from))
    if starts_to is not None:
        stmt = stmt.where(when < _aware(starts_to))
    if state is not None:
        if state not in PUBLICATION_STATES:
            raise _unprocessable(
                f"state tiene que ser uno de: {', '.join(PUBLICATION_STATES)}"
            )
        stmt = stmt.where(Publication.state == state)
    if inbox_id is not None:
        stmt = stmt.where(
            Publication.id.in_(  # type: ignore[union-attr]
                select(PublicationTarget.publication_id).where(
                    PublicationTarget.inbox_id == inbox_id
                )
            )
        )
    stmt = stmt.order_by(when.asc(), Publication.id.asc())  # type: ignore[union-attr]
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    return list((await session.exec(stmt)).all())


def _ensure_editable(publication: Publication) -> None:
    if publication.state not in PUBLICATION_EDITABLE_STATES:
        raise _unprocessable(
            "Solo se puede cambiar una publicación en borrador o programada"
        )


async def update_publication(
    session: AsyncSession,
    *,
    publication: Publication,
    payload: dict[str, Any],
) -> Publication:
    _ensure_editable(publication)
    if "content" in payload:
        publication.content = payload["content"]
    if "media" in payload and payload["media"] is not None:
        publication.media = await _normalize_media(
            session, account_id=publication.account_id, raw=payload["media"]
        )

    # Only a new date or a draft toggle reschedules; editing the text of a
    # publication whose date just passed must not trip the future check.
    if "scheduled_for" in payload or payload.get("draft") is not None:
        draft = (
            bool(payload["draft"])
            if payload.get("draft") is not None
            else publication.state == PUBLICATION_STATE_DRAFT
        )
        scheduled_for = (
            _aware(payload["scheduled_for"])
            if "scheduled_for" in payload
            else publication.scheduled_for
        )
        publication.state, publication.scheduled_for = _resolve_schedule(
            draft=draft, scheduled_for=scheduled_for
        )

    if payload.get("targets") is not None:
        targets, inboxes = await _build_targets(
            session,
            account_id=publication.account_id,
            raw_targets=payload["targets"],
        )
        _validate_targets(publication, targets, inboxes)
        await session.exec(  # type: ignore[call-overload]
            delete(PublicationTarget).where(
                PublicationTarget.publication_id == publication.id  # type: ignore[arg-type]
            )
        )
        for target in targets:
            target.publication_id = publication.id  # type: ignore[assignment]
            session.add(target)
    else:
        current = (
            await targets_by_publication(
                session, publication_ids=[publication.id]  # type: ignore[list-item]
            )
        )[publication.id]  # type: ignore[index]
        inboxes = {
            inbox.id: inbox
            for inbox in (
                await session.exec(
                    select(Inbox).where(
                        Inbox.id.in_([t.inbox_id for t in current])  # type: ignore[union-attr]
                    )
                )
            ).all()
        }
        _validate_targets(publication, current, inboxes)

    session.add(publication)
    await session.flush()
    await session.refresh(publication)
    return publication


async def delete_publication(
    session: AsyncSession, *, publication: Publication
) -> None:
    if publication.state not in (
        *PUBLICATION_EDITABLE_STATES,
        PUBLICATION_STATE_FAILED,
    ):
        raise _unprocessable(
            "No se puede borrar una publicación que ya salió o está saliendo"
        )
    await session.delete(publication)
    await session.flush()


async def retry_publication(
    session: AsyncSession, *, publication: Publication
) -> Publication:
    """Put the failed targets back in the queue; published ones stay."""
    if publication.state not in (
        PUBLICATION_STATE_FAILED,
        PUBLICATION_STATE_PARTIALLY_PUBLISHED,
    ):
        raise _unprocessable("Solo se reintenta una publicación que falló")
    await session.exec(  # type: ignore[call-overload]
        update(PublicationTarget)
        .where(
            PublicationTarget.publication_id == publication.id,  # type: ignore[arg-type]
            PublicationTarget.state == TARGET_STATE_FAILED,  # type: ignore[arg-type]
        )
        .values(state=TARGET_STATE_PENDING, error_code=None, error_message=None)
    )
    publication.state = PUBLICATION_STATE_PUBLISHING
    session.add(publication)
    await session.flush()
    await session.refresh(publication)
    return publication


async def due_publication_ids(
    session: AsyncSession, *, now: datetime | None = None
) -> list[int]:
    now = now or datetime.now(UTC)
    rows = (
        await session.exec(
            select(Publication.id).where(
                Publication.state == PUBLICATION_STATE_SCHEDULED,
                Publication.scheduled_for <= now,  # type: ignore[operator]
            )
        )
    ).all()
    return [i for i in rows if i is not None]


async def start_publishing(
    session: AsyncSession, *, publication_id: int
) -> bool:
    """Claim a due publication for publishing. The conditional update makes
    it safe against two ticks or two workers (only one wins) and against an
    edit that moved the date forward after it was picked as due."""
    result = await session.exec(  # type: ignore[call-overload]
        update(Publication)
        .where(
            Publication.id == publication_id,  # type: ignore[arg-type]
            Publication.state == PUBLICATION_STATE_SCHEDULED,  # type: ignore[arg-type]
            Publication.scheduled_for <= datetime.now(UTC),  # type: ignore[operator]
        )
        .values(state=PUBLICATION_STATE_PUBLISHING)
    )
    return result.rowcount == 1


async def release_claim(session: AsyncSession, *, publication_id: int) -> None:
    """Undo :func:`start_publishing` when the job could not be enqueued, so
    the next tick tries again."""
    await session.exec(  # type: ignore[call-overload]
        update(Publication)
        .where(
            Publication.id == publication_id,  # type: ignore[arg-type]
            Publication.state == PUBLICATION_STATE_PUBLISHING,  # type: ignore[arg-type]
        )
        .values(state=PUBLICATION_STATE_SCHEDULED)
    )


async def recover_stale_publications(
    session: AsyncSession, *, older_than: timedelta
) -> list[int]:
    """Unstick publications left in ``publishing`` by a crashed or timed-out
    job. A target caught mid-publish may or may not have gone out, so it is
    marked failed with a warning rather than sent again; pending targets are
    returned to be enqueued once more. Returns the ids to re-enqueue."""
    cutoff = datetime.now(UTC) - older_than
    stale = (
        await session.exec(
            select(Publication).where(
                Publication.state == PUBLICATION_STATE_PUBLISHING,
                Publication.updated_at < cutoff,  # type: ignore[operator]
            )
        )
    ).all()
    requeue: list[int] = []
    for publication in stale:
        targets = (
            await targets_by_publication(
                session, publication_ids=[publication.id]  # type: ignore[list-item]
            )
        )[publication.id]  # type: ignore[index]
        for target in targets:
            if target.state == TARGET_STATE_PUBLISHING:
                target.state = TARGET_STATE_FAILED
                target.error_code = "interrupted"
                target.error_message = (
                    "La publicación se interrumpió y no se sabe si salió. "
                    "Revisá la red antes de reintentar."
                )
                session.add(target)
        if any(t.state == TARGET_STATE_PENDING for t in targets):
            requeue.append(publication.id)  # type: ignore[arg-type]
        else:
            publication.state = _aggregate_state(targets)
        # Touch it, so the next tick doesn't take it as stale again.
        publication.updated_at = datetime.now(UTC)
        session.add(publication)
    await session.flush()
    return requeue


def _aggregate_state(targets: list[PublicationTarget]) -> str:
    published = sum(1 for t in targets if t.state == TARGET_STATE_PUBLISHED)
    # No targets left (their inboxes were deleted): nothing went out.
    if not targets:
        return PUBLICATION_STATE_FAILED
    if published == len(targets):
        return PUBLICATION_STATE_PUBLISHED
    if published:
        return PUBLICATION_STATE_PARTIALLY_PUBLISHED
    return PUBLICATION_STATE_FAILED


def _apply_result(target: PublicationTarget, result: PublishResult, *, final_attempt: bool) -> None:
    target.extra = {**(target.extra or {}), **result.extra}
    if result.ok:
        target.state = TARGET_STATE_PUBLISHED
        target.external_id = result.external_id
        target.permalink = result.permalink
        target.error_code = None
        target.error_message = None
        target.published_at = datetime.now(UTC)
        return
    target.error_code = result.error_code
    target.error_message = result.error_message
    target.state = (
        TARGET_STATE_PENDING
        if result.retryable and not final_attempt
        else TARGET_STATE_FAILED
    )


async def publish_pending_targets(
    session: AsyncSession,
    *,
    publication_id: int,
    final_attempt: bool = True,
) -> bool:
    """Publish every pending target of a publication that is publishing.

    Targets are independent: one failing never stops the others. A target
    already published is never sent again. Returns True when some target
    failed with a retryable error and was left pending for another try
    (only when ``final_attempt`` is False).

    Commits around each target, unlike the rest of this service: once a
    network has accepted a post, that fact must survive a later crash or
    timeout of the job, or the next run would publish it twice. A target
    the job dies on stays ``publishing`` and is resolved by
    :func:`recover_stale_publications`.
    """
    publication = await session.get(Publication, publication_id)
    if publication is None or publication.state != PUBLICATION_STATE_PUBLISHING:
        return False

    targets = (
        await targets_by_publication(session, publication_ids=[publication_id])
    )[publication_id]
    if not await _refresh_library_links(session, publication):
        # Nothing pending can go out; the loop below skips them and the
        # usual wrap-up settles the publication.
        for target in targets:
            if target.state == TARGET_STATE_PENDING:
                target.state = TARGET_STATE_FAILED
                target.error_code = "missing_media"
                target.error_message = (
                    "Un archivo de la publicación ya no está en la biblioteca."
                )
                session.add(target)
    await session.commit()
    retry_needed = False
    for target in targets:
        if target.state != TARGET_STATE_PENDING:
            continue
        target_id = target.id
        target.state = TARGET_STATE_PUBLISHING
        target.attempts += 1
        session.add(target)
        await session.commit()

        adapter = adapter_for_network(target.network)
        if adapter is None:
            result = PublishResult(
                ok=False,
                error_code="unknown_network",
                error_message="Esta red ya no se puede publicar.",
            )
        else:
            try:
                # A savepoint, so an unexpected failure rolls back only
                # this target's writes and the others still go out.
                async with session.begin_nested():
                    result = await adapter.publish(session, publication, target)
            except Exception:
                log.exception(
                    "publishing.target.failed publication_id=%s target_id=%s",
                    publication_id,
                    target_id,
                )
                # The rollback expired what the savepoint touched; reload
                # before reading it again (async sessions can't lazy-load).
                await session.refresh(publication)
                await session.refresh(target)
                result = PublishResult(
                    ok=False,
                    error_code="unexpected_error",
                    error_message="Error inesperado al publicar.",
                )
        _apply_result(target, result, final_attempt=final_attempt)
        retry_needed = retry_needed or target.state == TARGET_STATE_PENDING
        session.add(target)
        # Touch the publication too: its ``updated_at`` is the liveness
        # signal the stale recovery reads.
        publication.updated_at = datetime.now(UTC)
        session.add(publication)
        await session.commit()

    # A target a crashed run left mid-publish is the stale recovery's to
    # settle; until then the publication isn't finished.
    unsettled = any(t.state == TARGET_STATE_PUBLISHING for t in targets)
    if not retry_needed and not unsettled:
        publication.state = _aggregate_state(targets)
        if publication.state != PUBLICATION_STATE_FAILED:
            publication.published_at = datetime.now(UTC)
        session.add(publication)
        await session.commit()
    return retry_needed


__all__ = [
    "create_publication",
    "delete_publication",
    "due_publication_ids",
    "get_publication",
    "list_channels",
    "list_publications",
    "publish_pending_targets",
    "recover_stale_publications",
    "release_claim",
    "retry_publication",
    "start_publishing",
    "targets_by_publication",
    "update_publication",
]
