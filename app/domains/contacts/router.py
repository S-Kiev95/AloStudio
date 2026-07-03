"""Contacts HTTP endpoints.

Ports ``Api::V1::Accounts::ContactsController`` +
``Api::V1::Accounts::Contacts::NotesController`` +
``Api::V1::Accounts::Contacts::ContactInboxesController`` +
``Api::V1::Accounts::Actions::ContactMergesController``.

Route map (Chatwoot — Phase 3 subset):

  * ``GET    /api/v1/accounts/:account_id/contacts``              → index
  * ``POST   /api/v1/accounts/:account_id/contacts``              → create
  * ``GET    /api/v1/accounts/:account_id/contacts/search``       → search
  * ``GET    /api/v1/accounts/:account_id/contacts/:id``          → show
  * ``PATCH  /api/v1/accounts/:account_id/contacts/:id``          → update
  * ``DELETE /api/v1/accounts/:account_id/contacts/:id``          → destroy (admin)
  * ``GET    /api/v1/accounts/:account_id/contacts/:id/contactable_inboxes``
  * ``POST   /api/v1/accounts/:account_id/contacts/:id/destroy_custom_attributes``
  * ``GET    /api/v1/accounts/:account_id/contacts/:contact_id/notes`` → notes index
  * ``POST   /api/v1/accounts/:account_id/contacts/:contact_id/notes`` → notes create
  * ``GET    /api/v1/accounts/:account_id/contacts/:contact_id/notes/:id`` → notes show
  * ``PATCH  /api/v1/accounts/:account_id/contacts/:contact_id/notes/:id`` → notes update
  * ``DELETE /api/v1/accounts/:account_id/contacts/:contact_id/notes/:id`` → notes destroy
  * ``POST   /api/v1/accounts/:account_id/contacts/:contact_id/contact_inboxes``
  * ``POST   /api/v1/accounts/:account_id/actions/contact_merge``

Deferred (Phase 4+):
  * ``import`` / ``export`` — need background job + CSV pipeline.
  * ``active``              — needs Redis OnlineStatusTracker (Phase 6+).
  * ``filter``              — needs ``ContactFilterService`` DSL.
  * ``avatar``              — needs Avatarable attachment (Phase 6+).

Policy map (per ``ContactPolicy``):
  * All read + create + update + contactable_inboxes +
    destroy_custom_attributes + notes + contact_inboxes + contact_merge
    are agent-level (any account member).
  * ``destroy`` is admin-only.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy import func, or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import (
    AccountContext,
    account_context,
    require_admin,
)
from app.core.errors import ChatwootHTTPException
from app.domains.contacts.filter import contact_filter
from app.domains.contacts.models import Contact, ContactInbox, Note
from app.domains.contacts.presenters import (
    _present_inbox_slim,
    present_contact,
    present_contact_create,
    present_contact_show,
    present_contacts_index,
    present_contacts_search,
    present_note,
    present_notes_index,
)
from app.domains.contacts.schemas import (
    ContactCreateRequest,
    ContactInboxCreateRequest,
    ContactMergeRequest,
    ContactUpdateRequest,
    DestroyCustomAttributesRequest,
    NoteEnvelope,
)
from app.domains.contacts.service import (
    ContactInboxBuilder,
    ContactMergeAction,
    company_name_expr,
    create_contact,
    list_companies,
    update_contact,
)
from app.domains.inboxes.models import CHANNEL_TYPE_API, Inbox
from app.domains.users.models import AccountUser

RESULTS_PER_PAGE = 15

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/contacts",
    tags=["contacts"],
)

# Sibling router for ``POST /actions/contact_merge`` — Chatwoot declares
# this under ``Api::V1::Accounts::Actions::`` at the account root, not
# nested under contacts.
actions_router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/actions",
    tags=["contacts"],
)


# ============================================================================
# Contacts CRUD
# ============================================================================
@router.get("")
async def index_contacts(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
    include_contact_inboxes: bool = Query(True),
    company: str | None = Query(None),
) -> dict[str, Any]:
    """``GET /contacts`` — paginated list, optionally filtered by company.

    ``?company=`` narrows to contacts whose
    ``additional_attributes['company_name']`` equals the value (the
    "companies" roll-up drills down through this). Chatwoot orders by
    ``(company_name, email)`` via its ``sort_on`` DSL default; Phase 3
    defers the full sort/filter DSL, so we keep the deterministic
    ``id DESC`` fallback order.
    """
    assert ctx.account.id is not None
    conds: list[Any] = [Contact.account_id == ctx.account.id]
    if company:
        conds.append(company_name_expr() == company)
    total = (
        await session.exec(
            select(func.count()).select_from(Contact).where(*conds)  # type: ignore[arg-type]
        )
    ).one()
    total = _count_scalar(total)

    offset = (page - 1) * RESULTS_PER_PAGE
    stmt = (
        select(Contact)
        .where(*conds)
        .order_by(Contact.id.desc())  # type: ignore[attr-defined]
        .offset(offset)
        .limit(RESULTS_PER_PAGE)
    )
    contacts = list((await session.exec(stmt)).all())
    return present_contacts_index(
        contacts,
        count=total,
        current_page=page,
        with_contact_inboxes=include_contact_inboxes,
    )


@router.get("/companies")
async def index_companies(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    """``GET /contacts/companies`` — the account's contacts rolled up by
    ``company_name`` (``[{"name", "count"}, ...]``, count desc).

    Not a Chatwoot port: an organisation is just the free-text
    ``company_name`` contact attribute, so this is a derived view. Declared
    before ``/{contact_id}`` so the literal path wins the route match.
    """
    assert ctx.account.id is not None
    return await list_companies(session, account_id=ctx.account.id)


@router.post("/filter")
async def filter_contacts_endpoint(
    body: dict[str, Any],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
) -> dict[str, Any]:
    """``POST /contacts/filter`` — contact filter-DSL (backs segments).

    Body ``{"payload": [<condition>, ...]}`` — same condition shape as the
    conversation filter, over contact attributes. Bad payloads → 400 with
    ``{"message": "..."}``. Declared before ``/{contact_id}`` so the literal
    path wins the route match.
    """
    assert ctx.account.id is not None
    conditions = body.get("payload")
    if not isinstance(conditions, list):
        raise ChatwootHTTPException(
            status_code=400,
            detail={"message": "payload key required and must be an array"},
        )
    rows, count = await contact_filter(
        session,
        account_id=ctx.account.id,
        payload=conditions,
        page=page,
    )
    return present_contacts_index(
        rows, count=count, current_page=page, with_contact_inboxes=True
    )


@router.get("/search")
async def search_contacts(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    include_contact_inboxes: bool = Query(True),
) -> dict[str, Any]:
    """``GET /contacts/search`` — ILIKE on name/email/phone/identifier.

    Chatwoot requires ``q`` and emits ``{"error": "Specify search string
    with parameter q"}`` at 422 when blank. Parity.
    """
    if not q or not q.strip():
        raise ChatwootHTTPException(
            status_code=422,
            detail={"error": "Specify search string with parameter q"},
        )
    assert ctx.account.id is not None
    needle = f"%{q.strip()}%"

    # One extra row fetched to decide ``has_more`` — mirrors Rails'
    # ``fetch_contacts_with_has_more`` which fetches RESULTS_PER_PAGE + 1.
    offset = (page - 1) * RESULTS_PER_PAGE
    stmt = (
        select(Contact)
        .where(
            Contact.account_id == ctx.account.id,
            or_(
                Contact.name.ilike(needle),  # type: ignore[attr-defined]
                Contact.email.ilike(needle),  # type: ignore[attr-defined]
                Contact.phone_number.ilike(needle),  # type: ignore[attr-defined]
                # NOTE: Chatwoot's SQL is ``contacts.identifier LIKE :search``
                # (case-sensitive) — we preserve that exactly.
                Contact.identifier.like(needle),  # type: ignore[attr-defined]
            ),
        )
        .order_by(Contact.id.desc())  # type: ignore[attr-defined]
        .offset(offset)
        .limit(RESULTS_PER_PAGE + 1)
    )
    rows = list((await session.exec(stmt)).all())
    has_more = len(rows) > RESULTS_PER_PAGE
    if has_more:
        rows = rows[:RESULTS_PER_PAGE]
    return present_contacts_search(
        rows,
        count=len(rows),
        current_page=page,
        has_more=has_more,
        with_contact_inboxes=include_contact_inboxes,
    )


@router.post("", status_code=status.HTTP_200_OK)
async def create_contact_endpoint(
    payload: ContactCreateRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /contacts`` — create contact (+ optionally ContactInbox).

    Chatwoot returns 200 on create (not 201) — we match. If
    ``inbox_id`` is supplied, Chatwoot also runs ``ContactInboxBuilder``
    inside the same transaction and renders both rows. The response
    envelope from ``create.json.jbuilder`` nests ``contact_inbox``
    alongside ``contact``.
    """
    contact_kwargs = payload.model_dump(
        exclude={"inbox_id", "source_id", "avatar_url"},
        exclude_none=True,
    )
    contact = await create_contact(
        session,
        account_id=ctx.account.id,  # type: ignore[arg-type]
        payload=contact_kwargs,
    )

    contact_inbox = None
    if payload.inbox_id is not None:
        inbox = await _find_inbox_in_account(session, ctx, payload.inbox_id)
        contact_inbox = await ContactInboxBuilder(
            session=session,
            contact=contact,
            inbox=inbox,
            source_id=payload.source_id,
        ).perform()
    return present_contact_create(contact, contact_inbox)


@router.get("/{contact_id}")
async def show_contact(
    contact_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    include_contact_inboxes: bool = Query(True),
) -> dict[str, Any]:
    """``GET /contacts/:id``."""
    contact = await _find_contact_in_account(session, ctx, contact_id)
    return present_contact_show(
        contact, with_contact_inboxes=include_contact_inboxes
    )


@router.patch("/{contact_id}")
async def update_contact_endpoint(
    contact_id: Annotated[int, Path()],
    payload: ContactUpdateRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    include_contact_inboxes: bool = Query(True),
) -> dict[str, Any]:
    """``PATCH /contacts/:id`` — update + deep-merge JSONB blobs.

    Wire shape matches ``update.json.jbuilder`` which reuses
    ``show.json.jbuilder`` — ``{"payload": <contact>}``.
    """
    contact = await _find_contact_in_account(session, ctx, contact_id)
    updates = payload.model_dump(exclude={"avatar_url"}, exclude_none=True)
    updated = await update_contact(
        session,
        contact=contact,
        payload=updates,
    )
    return present_contact_show(
        updated, with_contact_inboxes=include_contact_inboxes
    )


@router.delete("/{contact_id}", status_code=status.HTTP_200_OK)
async def destroy_contact(
    contact_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``DELETE /contacts/:id`` — admin-only.

    Chatwoot's ``OnlineStatusTracker`` online-contact guard is a Redis
    presence check (no persisted state). Phase 6+ wires the tracker;
    until then every contact is considered offline, so the guard is a
    no-op here and the destroy always proceeds.

    On success Chatwoot does ``head :ok`` — empty body, 200 status. We
    match.
    """
    contact = await _find_contact_in_account(session, ctx, contact_id)
    await session.delete(contact)
    await session.flush()
    return {}


@router.get("/{contact_id}/contactable_inboxes")
async def contactable_inboxes(
    contact_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``GET /contacts/:id/contactable_inboxes``.

    Phase 3 only supports Channel::Api (the only channel model we've
    ported). For API channels the source_id is either the existing
    ``ContactInbox.source_id`` or a freshly-minted UUID — mirroring
    ``Contacts::ContactableInboxesService#api_contactable_inbox``.

    Per the jbuilder (``contactable_inboxes.json.jbuilder``) we wrap
    the list under ``payload`` and nest each inbox via ``_inbox_slim``.
    """
    contact = await _find_contact_in_account(session, ctx, contact_id)
    assert ctx.account.id is not None

    # Load all account inboxes the caller is allowed to see. Agents are
    # scoped by ``policy(inbox).show?`` — we delegate to the same check
    # by filtering admins to all inboxes and agents to their member set.
    inbox_rows = await _visible_inboxes(session, ctx)
    latest_cis = await _latest_contact_inboxes(session, contact.id, inbox_rows)

    payload: list[dict[str, Any]] = []
    for inbox in inbox_rows:
        if inbox.channel_type != CHANNEL_TYPE_API:
            # Other channels defer to Phase 5 — skip rather than raise,
            # matching ``filter_map`` in the Ruby service.
            continue
        source_id = (
            latest_cis[inbox.id].source_id
            if inbox.id in latest_cis
            else str(uuid.uuid4())
        )
        payload.append(
            {
                "inbox": _present_inbox_slim(inbox),
                "source_id": source_id,
            }
        )
    return {"payload": payload}


@router.post("/{contact_id}/destroy_custom_attributes", status_code=status.HTTP_200_OK)
async def destroy_custom_attributes(
    contact_id: Annotated[int, Path()],
    payload: DestroyCustomAttributesRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /contacts/:id/destroy_custom_attributes``.

    Chatwoot: ``@contact.custom_attributes = @contact.custom_attributes
    .excluding(params[:custom_attributes])`` — i.e. remove those keys.
    Response is ``{"payload": <contact>}`` (``destroy_custom_attributes.json.jbuilder``).
    """
    contact = await _find_contact_in_account(session, ctx, contact_id)
    remaining = {
        k: v
        for k, v in (contact.custom_attributes or {}).items()
        if k not in set(payload.custom_attributes)
    }
    contact.custom_attributes = remaining
    session.add(contact)
    await session.flush()
    return {"payload": present_contact(contact, with_contact_inboxes=True)}


# ============================================================================
# Notes (nested under contacts)
# ============================================================================
@router.get("/{contact_id}/notes")
async def index_notes(
    contact_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    """``GET /contacts/:contact_id/notes`` — latest-first.

    Chatwoot: ``@contact.notes.latest.includes(:user)``. The
    presenter returns a top-level JSON array — no envelope.
    """
    contact = await _find_contact_in_account(session, ctx, contact_id)
    stmt = (
        select(Note)
        .where(Note.contact_id == contact.id)
        .order_by(Note.created_at.desc(), Note.id.desc())  # type: ignore[attr-defined]
    )
    notes = list((await session.exec(stmt)).all())
    lookup = await _load_account_users_for_notes(session, ctx.account.id, notes)  # type: ignore[arg-type]
    return present_notes_index(notes, account_users_by_user_id=lookup)


@router.post("/{contact_id}/notes", status_code=status.HTTP_200_OK)
async def create_note(
    contact_id: Annotated[int, Path()],
    payload: NoteEnvelope,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /contacts/:contact_id/notes``.

    ``user_id`` is set from the authenticated caller — matches
    ``note_params.merge(user_id: Current.user.id)``.
    """
    contact = await _find_contact_in_account(session, ctx, contact_id)
    note = Note(
        account_id=ctx.account.id,  # type: ignore[arg-type]
        contact_id=contact.id,  # type: ignore[arg-type]
        user_id=ctx.user.id,
        content=payload.note.content,
    )
    session.add(note)
    await session.flush()
    # Load the ``user`` relationship for the presenter, and refresh the
    # row itself so the server-default timestamps are populated.
    await session.refresh(note)
    await session.refresh(note, attribute_names=["user"])
    account_user = await _find_account_user(session, ctx.account.id, ctx.user.id)  # type: ignore[arg-type]
    return present_note(note, account_user=account_user)


@router.get("/{contact_id}/notes/{note_id}")
async def show_note(
    contact_id: Annotated[int, Path()],
    note_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``GET /contacts/:contact_id/notes/:id``."""
    note = await _find_note(session, ctx, contact_id, note_id)
    account_user = (
        await _find_account_user(session, ctx.account.id, note.user_id)  # type: ignore[arg-type]
        if note.user_id is not None
        else None
    )
    return present_note(note, account_user=account_user)


@router.patch("/{contact_id}/notes/{note_id}")
async def update_note(
    contact_id: Annotated[int, Path()],
    note_id: Annotated[int, Path()],
    payload: NoteEnvelope,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``PATCH /contacts/:contact_id/notes/:id``."""
    note = await _find_note(session, ctx, contact_id, note_id)
    note.content = payload.note.content
    session.add(note)
    await session.flush()
    # ``onupdate=func.now()`` expires ``updated_at``; refresh so the
    # presenter doesn't trip a lazy load inside sync code.
    await session.refresh(note)
    account_user = (
        await _find_account_user(session, ctx.account.id, note.user_id)  # type: ignore[arg-type]
        if note.user_id is not None
        else None
    )
    return present_note(note, account_user=account_user)


@router.delete("/{contact_id}/notes/{note_id}", status_code=status.HTTP_200_OK)
async def destroy_note(
    contact_id: Annotated[int, Path()],
    note_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``DELETE /contacts/:contact_id/notes/:id`` → ``head :ok``."""
    note = await _find_note(session, ctx, contact_id, note_id)
    await session.delete(note)
    await session.flush()
    return {}


# ============================================================================
# ContactInbox create (nested under contacts)
# ============================================================================
@router.post("/{contact_id}/contact_inboxes", status_code=status.HTTP_200_OK)
async def create_contact_inbox(
    contact_id: Annotated[int, Path()],
    payload: ContactInboxCreateRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /contacts/:contact_id/contact_inboxes``.

    Chatwoot delegates to ``ContactInboxBuilder`` and the response is
    a plain ``_contact_inbox.json.jbuilder`` row (no wrapping). HMAC
    verification is a WebWidget-only concern — left at default False
    here because Phase 3 only exposes the API channel.
    """
    contact = await _find_contact_in_account(session, ctx, contact_id)
    inbox = await _find_inbox_in_account(session, ctx, payload.inbox_id)
    row = await ContactInboxBuilder(
        session=session,
        contact=contact,
        inbox=inbox,
        source_id=payload.source_id,
    ).perform()
    # The nested-view body is `{"contact_inbox": <partial>}` in Chatwoot's
    # ``contact_inboxes/create.json.jbuilder`` — mirror exactly.
    return {
        "contact_inbox": {
            "source_id": row.source_id,
            "inbox": _present_inbox_slim(inbox),
        }
    }


# ============================================================================
# Actions: contact_merge
# ============================================================================
@actions_router.post("/contact_merge", status_code=status.HTTP_200_OK)
async def contact_merge(
    payload: ContactMergeRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /actions/contact_merge`` — fold mergee into base.

    Phase 4 deps (Conversation / Message sender reassignment) are TODOs
    in :class:`ContactMergeAction` — contact_inboxes + notes + JSONB
    deep-merge are Phase 3.

    Response shape (``contact_merges/create.json.jbuilder``):
    ``{"id": ..., "name": ..., "email": ..., ...}`` — the base contact
    rendered via ``_contact.json.jbuilder``, no envelope.
    """
    assert ctx.account.id is not None
    base = await _find_contact_in_account(session, ctx, payload.base_contact_id)
    mergee = await _find_contact_in_account(session, ctx, payload.mergee_contact_id)

    merged = await ContactMergeAction(
        session=session,
        account_id=ctx.account.id,
        base=base,
        mergee=mergee,
    ).perform()
    return present_contact(merged, with_contact_inboxes=True)


# ============================================================================
# Helpers
# ============================================================================
def _count_scalar(value: Any) -> int:
    """Unwrap the single-cell result of a ``select(func.count())``."""
    if isinstance(value, tuple):
        value = value[0]
    return int(value)


async def _find_contact_in_account(
    session: AsyncSession, ctx: AccountContext, contact_id: int
) -> Contact:
    """Scope by account, 404 otherwise — mirrors ``Current.account.contacts.find``."""
    stmt = select(Contact).where(
        Contact.id == contact_id, Contact.account_id == ctx.account.id
    )
    contact = (await session.exec(stmt)).first()
    if contact is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return contact


async def _find_inbox_in_account(
    session: AsyncSession, ctx: AccountContext, inbox_id: int
) -> Inbox:
    stmt = select(Inbox).where(
        Inbox.id == inbox_id, Inbox.account_id == ctx.account.id
    )
    inbox = (await session.exec(stmt)).first()
    if inbox is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return inbox


async def _find_note(
    session: AsyncSession,
    ctx: AccountContext,
    contact_id: int,
    note_id: int,
) -> Note:
    # Matches ``@contact.notes.find(params[:id])`` — a missing contact
    # or a note that doesn't belong to this contact both surface as 404.
    contact = await _find_contact_in_account(session, ctx, contact_id)
    stmt = select(Note).where(
        Note.id == note_id,
        Note.contact_id == contact.id,
        Note.account_id == ctx.account.id,
    )
    note = (await session.exec(stmt)).first()
    if note is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return note


async def _visible_inboxes(
    session: AsyncSession, ctx: AccountContext
) -> list[Inbox]:
    """Account inboxes filtered through ``InboxPolicy#show?``."""
    from app.domains.inboxes.models import InboxMember

    assert ctx.account.id is not None
    if ctx.is_administrator:
        stmt = select(Inbox).where(Inbox.account_id == ctx.account.id)
    else:
        stmt = (
            select(Inbox)
            .join(InboxMember, InboxMember.inbox_id == Inbox.id)  # type: ignore[arg-type]
            .where(
                Inbox.account_id == ctx.account.id,
                InboxMember.user_id == ctx.user.id,
            )
        )
    return list((await session.exec(stmt)).all())


async def _latest_contact_inboxes(
    session: AsyncSession,
    contact_id: int | None,
    inboxes: list[Inbox],
) -> dict[int, ContactInbox]:
    """Per-inbox latest ContactInbox row for one contact.

    Ruby ``inbox.contact_inboxes.where(contact: @contact).last`` —
    ``.last`` defaults to primary-key order. We match with ``id DESC``.
    """
    if contact_id is None or not inboxes:
        return {}
    ids = [ix.id for ix in inboxes if ix.id is not None]
    if not ids:
        return {}
    stmt = (
        select(ContactInbox)
        .where(
            ContactInbox.contact_id == contact_id,
            ContactInbox.inbox_id.in_(ids),  # type: ignore[attr-defined]
        )
        .order_by(ContactInbox.id.desc())  # type: ignore[attr-defined]
    )
    out: dict[int, ContactInbox] = {}
    for row in (await session.exec(stmt)).all():
        out.setdefault(row.inbox_id, row)
    return out


async def _find_account_user(
    session: AsyncSession, account_id: int, user_id: int | None
) -> AccountUser | None:
    if user_id is None:
        return None
    stmt = select(AccountUser).where(
        AccountUser.account_id == account_id, AccountUser.user_id == user_id
    )
    return (await session.exec(stmt)).first()


async def _load_account_users_for_notes(
    session: AsyncSession,
    account_id: int,
    notes: list[Note],
) -> dict[int, AccountUser]:
    """Batch-load AccountUser rows for the (account_id, user_id) pairs in notes."""
    user_ids = {n.user_id for n in notes if n.user_id is not None}
    if not user_ids:
        return {}
    stmt = select(AccountUser).where(
        AccountUser.account_id == account_id,
        AccountUser.user_id.in_(user_ids),  # type: ignore[attr-defined]
    )
    rows = (await session.exec(stmt)).all()
    return {au.user_id: au for au in rows if au.user_id is not None}
