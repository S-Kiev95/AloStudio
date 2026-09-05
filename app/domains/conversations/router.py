"""Conversations + Messages HTTP endpoints.

Ports the Phase 4a subset of:
  reference/chatwoot/app/controllers/api/v1/accounts/conversations_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/conversations/messages_controller.rb

Route map (Phase 4a):

  * ``GET    /api/v1/accounts/:account_id/conversations``
  * ``GET    /api/v1/accounts/:account_id/conversations/meta``
  * ``POST   /api/v1/accounts/:account_id/conversations``
  * ``GET    /api/v1/accounts/:account_id/conversations/:id``
  * ``PATCH  /api/v1/accounts/:account_id/conversations/:id``
  * ``POST   /api/v1/accounts/:account_id/conversations/:id/toggle_status``
  * ``POST   /api/v1/accounts/:account_id/conversations/:id/toggle_priority``
  * ``POST   /api/v1/accounts/:account_id/conversations/:id/mute``
  * ``POST   /api/v1/accounts/:account_id/conversations/:id/unmute``
  * ``POST   /api/v1/accounts/:account_id/conversations/:id/custom_attributes``
  * ``POST   /api/v1/accounts/:account_id/conversations/:id/update_last_seen``
  * ``POST   /api/v1/accounts/:account_id/conversations/:id/unread``

  * ``GET    /api/v1/accounts/:account_id/conversations/:conv_id/messages``
  * ``POST   /api/v1/accounts/:account_id/conversations/:conv_id/messages``
  * ``DELETE /api/v1/accounts/:account_id/conversations/:conv_id/messages/:id``

Deferred to later sub-phases:
  * ``search`` / ``filter`` — conversation-filter DSL (Phase 4b).
  * ``attachments`` index   — paging over attachments (Phase 4b).
  * ``transcript`` email    — ConversationReplyMailer (Phase 5b).
  * ``toggle_typing_status`` — realtime (Phase 4b).
  * ``assignments`` (reassign) — AutoAssignment round-robin (Phase 4c).
  * ``messages#update`` / ``retry`` / ``translate`` — SendReplyJob + Google
    Translate integration (4b / 5b).
  * Account-scope filtering DSL — arrives with FilterService port (4b).

Route IDs: Chatwoot's URL ``:id`` for a conversation is **display_id**
(per-account sequence), not the database PK. We preserve that —
``/conversations/17`` means "display_id=17 inside this account".
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy import and_, func
from sqlalchemy.orm import lazyload, selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import AccountContext, account_context
from app.core.errors import ChatwootHTTPException
from app.domains.contacts.models import Contact, ContactInbox
from app.domains.contacts.service import ContactInboxBuilder
from app.domains.conversations.filter import conversation_filter
from app.domains.conversations.finder import conversation_finder
from app.domains.conversations.models import (
    CONVERSATION_STATUS_OPEN,
    MESSAGE_TYPE_INCOMING,
    Conversation,
    Message,
)
from app.domains.conversations.participants import (
    add_participants,
    list_participant_users,
    remove_participants,
    set_participants,
)
from app.domains.conversations.presenters import (
    present_conversation_create,
    present_conversation_show,
    present_conversation_toggle_status,
    present_conversations_index,
    present_conversations_meta,
    present_message_create,
    present_messages_index,
)
from app.domains.conversations.schemas import (
    ConversationCreateRequest,
    ConversationCustomAttributesRequest,
    ConversationTogglePriorityRequest,
    ConversationToggleStatusRequest,
    ConversationUpdateRequest,
    MessageCreateRequest,
    ParticipantsRequest,
)
from app.domains.conversations.service import (
    ConversationBuilderParams,
    MessageBuilderParams,
    _AttachmentSpec,
    _parse_label_csv,
    create_conversation,
    create_message,
    mute_conversation_with_activity,
    toggle_priority,
    toggle_status,
    unmute_conversation_with_activity,
    update_assignee,
    update_custom_attributes,
    update_labels,
    update_team,
)
from app.domains.inboxes.models import CHANNEL_TYPE_API, Inbox
from app.domains.inboxes.presenters import present_agent
from app.domains.users.models import AccountUser, User

RESULTS_PER_PAGE = 25
# Rails constant — same name, same value (``Message::ATTACHMENT_RESULTS_PER_PAGE``).
ATTACHMENT_RESULTS_PER_PAGE = 100

router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/conversations",
    tags=["conversations"],
)

messages_router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages",
    tags=["messages"],
)

participants_router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/conversations/{conversation_id}/participants",
    tags=["participants"],
)


# =========================================================================
# Helpers
# =========================================================================
def _parse_iso(value: str | None, *, field: str) -> datetime | None:
    """Parse ISO-8601 → datetime, 422 on malformed input.

    Accepts ``Z`` suffix (normalises to ``+00:00``), matching Rails'
    ``DateTime.parse`` behaviour on ``snoozed_until`` / ``external_created_at``.
    """
    if value is None or value == "":
        return None
    try:
        normalised = value.replace("Z", "+00:00") if value.endswith("Z") else value
        return datetime.fromisoformat(normalised)
    except ValueError as e:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": f"{field}: invalid datetime {value!r}"},
        ) from e


async def _load_conversation_by_display_id(
    session: AsyncSession,
    *,
    account_id: int,
    display_id: int,
    options: tuple[Any, ...] = (),
) -> Conversation:
    """Mirror of Rails ``Current.account.conversations.find_by!(display_id: id)``.

    ``options`` lets one caller narrow what gets loaded without changing
    it for the rest. Every relationship is ``lazy="selectin"``, so the
    default load pulls the conversation's whole graph — fine for an
    endpoint that presents all of it, expensive for one that needs two
    fields. Passing nothing keeps the previous behaviour exactly.
    """
    stmt = select(Conversation).where(
        Conversation.account_id == account_id,
        Conversation.display_id == display_id,
    )
    if options:
        stmt = stmt.options(*options)
    conv = (await session.exec(stmt)).first()
    if conv is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return conv


async def _load_inbox_in_account(
    session: AsyncSession, *, account_id: int, inbox_id: int
) -> Inbox:
    stmt = select(Inbox).where(
        Inbox.account_id == account_id,
        Inbox.id == inbox_id,
    )
    inbox = (await session.exec(stmt)).first()
    if inbox is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return inbox


async def _load_contact_in_account(
    session: AsyncSession, *, account_id: int, contact_id: int
) -> Contact:
    stmt = select(Contact).where(
        Contact.account_id == account_id,
        Contact.id == contact_id,
    )
    contact = (await session.exec(stmt)).first()
    if contact is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return contact


async def _find_contact_inbox(
    session: AsyncSession,
    *,
    inbox_id: int | None,
    source_id: str | None,
) -> ContactInbox | None:
    """Fallback lookup when the caller passes a ``source_id`` without
    ``(contact_id, inbox_id)`` — Rails still allows this as a legacy path.
    """
    if not source_id:
        return None
    stmt = select(ContactInbox).where(ContactInbox.source_id == source_id)
    if inbox_id is not None:
        stmt = stmt.where(ContactInbox.inbox_id == inbox_id)
    return (await session.exec(stmt)).first()


async def _count_conversations(
    session: AsyncSession,
    *,
    account_id: int,
    user_id: int,
    assignee_type: str | None,
    status_str: str | None,
) -> dict[str, int]:
    """Phase 4a minimal counts — mirrors the Rails ``ConversationFinder`` output.

    ``mine_count`` / ``assigned_count`` / ``unassigned_count`` / ``all_count``
    over ``status=open`` (Chatwoot's default status filter). Advanced
    filters (date ranges, labels, teams) land with the filter DSL in 4b.
    """
    open_filter = Conversation.status == CONVERSATION_STATUS_OPEN
    base = (
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.account_id == account_id, open_filter)
    )
    all_count = int((await session.exec(base)).one() or 0)
    mine_count = int(
        (
            await session.exec(
                base.where(Conversation.assignee_id == user_id)
            )
        ).one()
        or 0
    )
    assigned_count = int(
        (
            await session.exec(base.where(Conversation.assignee_id.is_not(None)))
        ).one()
        or 0
    )
    unassigned_count = int(
        (
            await session.exec(base.where(Conversation.assignee_id.is_(None)))
        ).one()
        or 0
    )
    return {
        "mine_count": mine_count,
        "assigned_count": assigned_count,
        "unassigned_count": unassigned_count,
        "all_count": all_count,
    }


def _attachment_specs_from(
    attachments: list[dict[str, Any]] | None,
) -> list[_AttachmentSpec] | None:
    if not attachments:
        return None
    out: list[_AttachmentSpec] = []
    for a in attachments:
        out.append(
            _AttachmentSpec(
                file_type=a.get("file_type", "file") or "file",
                external_url=a.get("external_url"),
                fallback_title=a.get("fallback_title"),
                coordinates_lat=a.get("coordinates_lat"),
                coordinates_long=a.get("coordinates_long"),
                meta=a.get("meta"),
                extension=a.get("extension"),
            )
        )
    return out


# =========================================================================
# Conversations CRUD
# =========================================================================
@router.get("")
async def index_conversations(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    assignee_type: str | None = Query(None, description="'me' | 'assigned' | 'unassigned'"),
    status_filter: str | None = Query(None, alias="status"),
    inbox_id: int | None = Query(None),
    team_id: int | None = Query(None),
    labels: list[str] | None = Query(None),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
) -> dict[str, Any]:
    """``GET /conversations`` — delegates to :func:`conversation_finder`.

    Phase 4b: full ConversationFinder subset (status / assignee_type /
    inbox_id / team_id / labels / q). Conversation_type, source_id and
    updated_within remain deferred — see ``finder.py`` docstring.
    """
    assert ctx.account.id is not None
    result = await conversation_finder(
        session,
        account_id=ctx.account.id,
        current_user_id=ctx.user.id,  # type: ignore[arg-type]
        params={
            "assignee_type": assignee_type,
            "status": status_filter,
            "inbox_id": inbox_id,
            "team_id": team_id,
            "labels": labels,
            "q": q,
        },
        page=page,
        per_page=RESULTS_PER_PAGE,
    )
    return present_conversations_index(
        result["conversations"], **result["count"]
    )


@router.get("/search")
async def search_conversations(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str = Query(..., description="Free-text search on message content"),
    assignee_type: str | None = Query(None),
    page: int = Query(1, ge=1),
) -> dict[str, Any]:
    """``GET /conversations/search`` — text search across message content.

    Mirrors ``ConversationsController#search``. Same finder, same wire
    shape as ``GET /conversations`` — Rails uses identical jbuilders for
    both. The only behavioural difference is that ``q`` removes the
    default ``status=open`` filter (search must span every status), which
    the finder handles internally.
    """
    assert ctx.account.id is not None
    result = await conversation_finder(
        session,
        account_id=ctx.account.id,
        current_user_id=ctx.user.id,  # type: ignore[arg-type]
        params={"q": q, "assignee_type": assignee_type},
        page=page,
        per_page=RESULTS_PER_PAGE,
    )
    return _present_filter_or_search(result)


@router.post("/filter")
async def filter_conversations(
    payload: dict[str, Any],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
) -> dict[str, Any]:
    """``POST /conversations/filter`` — custom filter-DSL endpoint.

    Body shape (mirrors ``params[:payload]`` in
    ``ConversationsController#filter``)::

        {"payload": [
            {"attribute_key": "status",
             "filter_operator": "equal_to",
             "values": ["open"],
             "query_operator": "AND"},
            {"attribute_key": "labels",
             "filter_operator": "equal_to",
             "values": ["urgent"]}
        ]}

    The last condition's ``query_operator`` is ignored (no successor to
    join with). Operator validation lives in
    :mod:`app.domains.conversations.filter`; bad payloads return 400 with
    the message envelope ``{"message": "..."}``.
    """
    assert ctx.account.id is not None
    body_payload = payload.get("payload")
    if not isinstance(body_payload, list):
        raise ChatwootHTTPException(
            status_code=400,
            detail={"message": "payload key required and must be an array"},
        )
    result = await conversation_filter(
        session,
        account_id=ctx.account.id,
        current_user_id=ctx.user.id,  # type: ignore[arg-type]
        payload=body_payload,
        page=page,
        per_page=RESULTS_PER_PAGE,
    )
    return _present_filter_or_search(result)


def _present_filter_or_search(result: dict[str, Any]) -> dict[str, Any]:
    """Mirror ``filter.json.jbuilder`` / ``search.json.jbuilder``.

    Both endpoints emit ``{meta: {mine, unassigned, all}, payload: [...]}``
    (one envelope level less than the index endpoint, no ``data`` wrap,
    no ``assigned_count``). We keep the shape identical to Chatwoot's
    rendered output.
    """
    from app.domains.conversations.presenters import present_conversation

    counts = result["count"]
    return {
        "meta": {
            "mine_count": counts["mine_count"],
            "unassigned_count": counts["unassigned_count"],
            "all_count": counts["all_count"],
        },
        "payload": [
            present_conversation(c) for c in result["conversations"]
        ],
    }


@router.get("/ads")
async def known_ads(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    """``GET /conversations/ads`` — the ads this account has heard from.

    There is no local table of ads: Meta owns them, and we only learn one
    exists when a conversation arrives attributed to it. So the list is the
    distinct set seen so far, newest first, which is what the inbox filter
    offers as options.
    """
    assert ctx.account.id is not None
    rows = (
        await session.exec(
            select(
                Conversation.ad_id,
                func.max(Conversation.ad_headline).label("headline"),
                func.max(Conversation.id).label("last_seen"),
            )
            .where(
                Conversation.account_id == ctx.account.id,
                Conversation.ad_id.is_not(None),
            )
            .group_by(Conversation.ad_id)
            .order_by(func.max(Conversation.id).desc())
            .limit(100)
        )
    ).all()
    return [
        {"ad_id": ad_id, "headline": headline or ad_id}
        for ad_id, headline, _last in rows
    ]


@router.get("/meta")
async def meta_conversations(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    assignee_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
) -> dict[str, Any]:
    """``GET /conversations/meta`` — counts only, no payload."""
    assert ctx.account.id is not None
    counts = await _count_conversations(
        session,
        account_id=ctx.account.id,
        user_id=ctx.user.id,  # type: ignore[arg-type]
        assignee_type=assignee_type,
        status_str=status_filter,
    )
    return present_conversations_meta(**counts)


@router.post("", status_code=status.HTTP_200_OK)
async def create_conversation_endpoint(
    payload: ConversationCreateRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /conversations``.

    Rails resolves the ``contact_inbox`` via three paths (in order):
      1. ``inbox_id`` + ``contact_id`` → build-or-find a ContactInbox.
      2. ``source_id`` alone (legacy) → find by source_id.
      3. Missing → 422.

    The optional ``message`` block gets created in the same transaction.
    """
    assert ctx.account.id is not None

    contact_inbox: ContactInbox | None = None
    if payload.inbox_id is not None and payload.contact_id is not None:
        inbox = await _load_inbox_in_account(
            session, account_id=ctx.account.id, inbox_id=payload.inbox_id
        )
        contact = await _load_contact_in_account(
            session, account_id=ctx.account.id, contact_id=payload.contact_id
        )
        contact_inbox = await ContactInboxBuilder(
            session=session,
            contact=contact,
            inbox=inbox,
            source_id=payload.source_id,
        ).perform()
    else:
        contact_inbox = await _find_contact_inbox(
            session,
            inbox_id=payload.inbox_id,
            source_id=payload.source_id,
        )

    if contact_inbox is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "Contact inbox could not be resolved"},
        )

    params = ConversationBuilderParams(
        additional_attributes=payload.additional_attributes,
        custom_attributes=payload.custom_attributes,
        status=payload.status,
        snoozed_until=_parse_iso(payload.snoozed_until, field="snoozed_until"),
        assignee_id=payload.assignee_id,
        team_id=payload.team_id,
    )
    conv = await create_conversation(
        session, contact_inbox=contact_inbox, params=params
    )

    if payload.message is not None:
        msg_params = MessageBuilderParams(
            content=payload.message.content,
            message_type=payload.message.message_type,
            content_type=payload.message.content_type,
            content_attributes=payload.message.content_attributes,
            additional_attributes=payload.message.additional_attributes,
            private=payload.message.private,
            source_id=payload.message.source_id,
            echo_id=payload.message.echo_id,
            attachments=_attachment_specs_from(payload.message.attachments),
            cc_emails=payload.message.cc_emails,
            bcc_emails=payload.message.bcc_emails,
            to_emails=payload.message.to_emails,
        )
        await create_message(
            session,
            conversation=conv,
            params=msg_params,
            user_id=ctx.user.id,
        )
        # ``create_conversation`` was committed; reload the conversation
        # so ``present_conversation_create`` sees the new message in its
        # eager-loaded ``messages`` collection.
        await session.refresh(conv)

    return present_conversation_create(conv)


@router.get("/{display_id}")
async def show_conversation(
    display_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=display_id
    )
    return present_conversation_show(conv)


@router.patch("/{display_id}")
async def update_conversation(
    display_id: Annotated[int, Path()],
    payload: ConversationUpdateRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``PATCH /conversations/:id``.

    Chatwoot's ``permitted_update_params`` only allows ``priority``.
    Honour that — any other field is silently ignored (``permit`` drops
    unknown keys in Rails).
    """
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=display_id
    )
    if payload.priority is not None:
        await toggle_priority(session, conversation=conv, priority=payload.priority)
    return present_conversation_show(conv)


@router.post("/{display_id}/toggle_status")
async def toggle_status_endpoint(
    display_id: Annotated[int, Path()],
    payload: ConversationToggleStatusRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /conversations/:id/toggle_status``.

    Phase 4a omits the ``pending_to_open_by_bot?`` branch (requires
    AgentBot — Phase 8) and the ``should_assign_conversation?`` branch
    (requires AutoAssignment — Phase 4c).
    """
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=display_id
    )
    snoozed_until = _parse_iso(payload.snoozed_until, field="snoozed_until")
    await toggle_status(
        session,
        conversation=conv,
        status=payload.status,
        snoozed_until=snoozed_until,
    )
    return present_conversation_toggle_status(conv, success=True)


@router.post("/{display_id}/toggle_priority")
async def toggle_priority_endpoint(
    display_id: Annotated[int, Path()],
    payload: ConversationTogglePriorityRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """``POST /conversations/:id/toggle_priority`` — Rails returns ``head :ok``."""
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=display_id
    )
    await toggle_priority(session, conversation=conv, priority=payload.priority)
    return Response(status_code=status.HTTP_200_OK)


@router.post("/{display_id}/mute")
async def mute_conversation(
    display_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """``POST /conversations/:id/mute`` — Rails returns ``head :ok``.

    Mirrors ``ConversationMuteHelpers#mute!``:
      * resolve the conversation (status activity row from
        ``toggle_status``);
      * block the contact;
      * insert the ``muted`` activity row.
    """
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=display_id
    )
    await mute_conversation_with_activity(session, conversation=conv)
    return Response(status_code=status.HTTP_200_OK)


@router.post("/{display_id}/unmute")
async def unmute_conversation(
    display_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """``POST /conversations/:id/unmute`` — Rails returns ``head :ok``."""
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=display_id
    )
    await unmute_conversation_with_activity(session, conversation=conv)
    return Response(status_code=status.HTTP_200_OK)


@router.post("/{display_id}/custom_attributes")
async def set_custom_attributes(
    display_id: Annotated[int, Path()],
    payload: ConversationCustomAttributesRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /conversations/:id/custom_attributes`` — replace the JSONB
    blob. Rails returns the show partial after save.
    """
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=display_id
    )
    await update_custom_attributes(
        session,
        conversation=conv,
        custom_attributes=payload.custom_attributes or {},
    )
    return present_conversation_show(conv)


@router.post("/{display_id}/assignments")
async def create_assignment(
    display_id: Annotated[int, Path()],
    payload: dict[str, Any],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Any:
    """``POST /conversations/:id/assignments`` — assign agent or team.

    Mirrors ``Api::V1::Accounts::Conversations::AssignmentsController#create``:
      * ``assignee_id`` key present  -> set agent (User), render agent partial.
      * ``team_id``     key present  -> set team, render team JSON.
      * neither                       -> ``null``.

    AgentBot assignments (``assignee_type == 'AgentBot'``) are deferred
    to Phase 8.
    """
    from app.domains.inboxes.presenters import present_agent
    from app.domains.users.models import AccountUser as _AccountUser

    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=display_id
    )

    if "assignee_id" in payload:
        assignee_id_raw = payload.get("assignee_id")
        assignee_id = (
            int(assignee_id_raw) if assignee_id_raw is not None else None
        )
        user = await update_assignee(
            session, conversation=conv, assignee_id=assignee_id
        )
        if user is None:
            return None
        # Look up the account_user row so we can render availability /
        # auto_offline. Mirrors ``current_account_user`` on the Rails side.
        au = (
            await session.exec(
                select(_AccountUser).where(
                    _AccountUser.user_id == user.id,
                    _AccountUser.account_id == ctx.account.id,
                )
            )
        ).first()
        return present_agent(
            account_id=ctx.account.id,
            account_user_availability=au.availability if au is not None else None,
            account_user_auto_offline=au.auto_offline if au is not None else None,
            user=user,
        )

    if "team_id" in payload:
        team_id_raw = payload.get("team_id")
        team_id = int(team_id_raw) if team_id_raw is not None else None
        team = await update_team(
            session, conversation=conv, team_id=team_id
        )
        if team is None:
            return None
        return {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "allow_auto_assign": team.allow_auto_assign,
            "account_id": team.account_id,
            "is_member": False,
        }

    return None


@router.post("/{display_id}/toggle_typing_status")
async def toggle_typing_status(
    display_id: Annotated[int, Path()],
    payload: dict[str, Any],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """``POST /conversations/:id/toggle_typing_status``.

    Mirrors ``Conversations::TypingStatusManager#toggle_typing_status``
    + ``ConversationsController#toggle_typing_status``: dispatches
    ``CONVERSATION_TYPING_ON`` or ``CONVERSATION_TYPING_OFF`` and
    returns ``head :ok``. Anything other than ``"on"`` / ``"off"`` is
    a silent no-op (Rails' case statement falls through).
    """
    from app.domains.conversations.events import (
        CONVERSATION_TYPING_OFF,
        CONVERSATION_TYPING_ON,
        dispatcher,
    )

    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=display_id
    )
    typing_status = payload.get("typing_status")
    is_private = bool(payload.get("is_private", False))
    if typing_status == "on":
        await dispatcher.dispatch(
            session,
            CONVERSATION_TYPING_ON,
            conversation=conv,
            user=ctx.user,
            is_private=is_private,
        )
    elif typing_status == "off":
        await dispatcher.dispatch(
            session,
            CONVERSATION_TYPING_OFF,
            conversation=conv,
            user=ctx.user,
            is_private=is_private,
        )
    return Response(status_code=status.HTTP_200_OK)


@router.get("/{display_id}/attachments")
async def list_attachments(
    display_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(1, ge=1),
) -> dict[str, Any]:
    """``GET /conversations/:id/attachments``.

    Mirrors ``ConversationsController#attachments`` +
    ``attachments.json.jbuilder``. Returns the conversation's
    attachments paginated at 100/page (Rails
    ``ATTACHMENT_RESULTS_PER_PAGE``), newest first, each shaped via
    ``Attachment#push_event_data`` plus ``message.created_at`` (unix)
    + ``message.sender.push_event_data``.
    """
    from app.domains.conversations.models import Attachment
    from app.domains.conversations.presenters import (
        present_attachment_push_event,
    )

    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=display_id
    )

    count_stmt = (
        select(func.count())
        .select_from(Attachment)
        .join(Message, Message.id == Attachment.message_id)  # type: ignore[arg-type]
        .where(Message.conversation_id == conv.id)
    )
    total_count = int((await session.exec(count_stmt)).one() or 0)

    offset = (page - 1) * ATTACHMENT_RESULTS_PER_PAGE
    list_stmt = (
        select(Attachment, Message)
        .join(Message, Message.id == Attachment.message_id)  # type: ignore[arg-type]
        .where(Message.conversation_id == conv.id)
        .order_by(Attachment.created_at.desc())  # type: ignore[attr-defined]
        .offset(offset)
        .limit(ATTACHMENT_RESULTS_PER_PAGE)
    )
    rows = list((await session.exec(list_stmt)).all())

    payload: list[dict[str, Any]] = []
    for att, msg in rows:
        push = present_attachment_push_event(att)
        payload.append(
            {
                "message_id": push.get("message_id"),
                "thumb_url": push.get("thumb_url", ""),
                "data_url": push.get("data_url"),
                "file_size": push.get("file_size"),
                "file_type": push.get("file_type"),
                "extension": push.get("extension"),
                "width": push.get("width"),
                "height": push.get("height"),
                # ``created_at`` here is the MESSAGE's created_at as a
                # unix integer — mirrors the jbuilder.
                "created_at": int(msg.created_at.timestamp()) if msg.created_at else 0,
                # ``sender`` is dropped when the message has no sender
                # (activity rows). The jbuilder uses ``if sender`` so
                # we only include the key when it resolves.
                **(
                    {"sender": _attachment_sender_payload(msg)}
                    if msg.sender_id is not None
                    else {}
                ),
            }
        )

    return {
        "meta": {"total_count": total_count},
        "payload": payload,
    }


def _attachment_sender_payload(message: Message) -> dict[str, Any] | None:
    """Best-effort sender stub for the attachments index.

    The jbuilder calls ``sender.push_event_data`` — for User senders
    that's the user push-event shape, for Contact senders it's the
    contact one. Resolving the polymorphic sender here would require
    another query; instead we emit ``{id, type}`` so the UI can render
    a placeholder. The full presenter lives at
    :func:`app.domains.conversations.presenters.present_message`'s
    ``sender`` block — Phase 4c will hoist a shared helper.
    """
    if message.sender_id is None or message.sender_type is None:
        return None
    return {
        "id": message.sender_id,
        "type": message.sender_type,
    }


@router.get("/{display_id}/labels")
async def list_labels(
    display_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``GET /conversations/:id/labels`` — current label list.

    Mirrors ``LabelsController#index`` + ``LabelConcern#index``: returns
    ``{"payload": [...]}`` driven off ``model.label_list``.
    """
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=display_id
    )
    return {"payload": _parse_label_csv(conv.cached_label_list)}


@router.post("/{display_id}/labels")
async def set_labels(
    display_id: Annotated[int, Path()],
    payload: dict[str, Any],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /conversations/:id/labels`` — replace the label set.

    Mirrors ``LabelsController#create`` + ``LabelConcern#create``:
    ``model.update_labels(params[:labels])`` then render
    ``{"payload": @labels}``. Permitted params: ``labels: []``.
    """
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=display_id
    )
    raw = payload.get("labels") or []
    if not isinstance(raw, list):
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "labels: expected an array of strings"},
        )
    titles = [str(t) for t in raw if isinstance(t, (str, int, float))]
    new_titles = await update_labels(
        session, conversation=conv, titles=titles
    )
    return {"payload": new_titles}


@router.post("/{display_id}/update_last_seen")
async def update_last_seen_endpoint(
    display_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """``POST /conversations/:id/update_last_seen``.

    Phase 4a ships the write-now branch only — the hourly-throttle
    optimisation in the Rails controller is a micro-tuning step and
    arrives alongside the full Notification::MarkConversationReadService
    (Phase 4b).
    """
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=display_id
    )
    now = datetime.now(tz=None)
    conv.agent_last_seen_at = now
    if conv.assignee_id == ctx.user.id:
        conv.assignee_last_seen_at = now
    session.add(conv)
    await session.flush()
    return Response(status_code=status.HTTP_200_OK)


@router.post("/{display_id}/unread")
async def mark_unread(
    display_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    """``POST /conversations/:id/unread``.

    Rewind ``agent_last_seen_at`` / ``assignee_last_seen_at`` to one
    second before the last incoming message so the conversation surfaces
    as unread again. Mirrors Rails exactly.
    """
    from datetime import timedelta

    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=display_id
    )
    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conv.id,
            Message.message_type == MESSAGE_TYPE_INCOMING,
        )
        .order_by(Message.created_at.desc())  # type: ignore[attr-defined]
        .limit(1)
    )
    last_incoming = (await session.exec(stmt)).first()
    if last_incoming is None or last_incoming.created_at is None:
        return Response(status_code=status.HTTP_200_OK)

    rewind = last_incoming.created_at - timedelta(seconds=1)
    conv.agent_last_seen_at = rewind
    conv.assignee_last_seen_at = rewind
    session.add(conv)
    await session.flush()
    return Response(status_code=status.HTTP_200_OK)


# =========================================================================
# Messages
# =========================================================================
@messages_router.get("")
async def index_messages(
    conversation_id: Annotated[int, Path(description="display_id")],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
    before: int | None = Query(None, description="Message.id cursor (returns older messages)"),
    after: int | None = Query(None, description="Message.id cursor (returns newer messages)"),
) -> dict[str, Any]:
    """``GET /conversations/:conv_id/messages``.

    Rails' ``MessageFinder`` returns the 20 most-recent messages by
    default with ``before`` / ``after`` cursors. We port the same shape;
    advanced filters (``filter_internal_messages`` for agent-bot users)
    arrive in Phase 8.
    """
    assert ctx.account.id is not None
    # ``present_messages_index`` reads two things off the conversation —
    # its contact and its assignee — and the endpoint's cost was
    # dominated by loading everything else: 62 queries for 20 messages,
    # most of them before a single message was read.
    conv = await _load_conversation_by_display_id(
        session,
        account_id=ctx.account.id,
        display_id=conversation_id,
        options=(
            lazyload("*"),
            selectinload(Conversation.contact),
            selectinload(Conversation.assignee),
        ),
    )
    filters = [Message.conversation_id == conv.id]
    if before is not None:
        filters.append(Message.id < before)  # type: ignore[operator]
    if after is not None:
        filters.append(Message.id > after)  # type: ignore[operator]
    stmt = (
        select(Message)
        .where(and_(*filters))
        .order_by(Message.created_at.desc())  # type: ignore[attr-defined]
        .limit(20)
        # Load what ``present_message`` reads, and nothing else. Every
        # relationship is declared ``lazy="selectin"``, so the plain
        # select pulled each message's account and inbox — the same rows
        # over and over — plus the conversation back-reference and its
        # own graph: 98 queries for 17 messages, measured on staging.
        #
        # ``message.conversation`` is not listed on purpose: it is a
        # many-to-one to the row ``_load_conversation_by_display_id``
        # already put in the identity map, which SQLAlchemy resolves
        # without a query. ``_resolved_sender`` is a plain attribute the
        # service attaches, not a relationship.
        .options(lazyload("*"), selectinload(Message.attachments))
    )
    rows = list((await session.exec(stmt)).all())
    rows.reverse()  # Rails returns oldest-first in the payload.
    return present_messages_index(rows, conversation=conv)


@messages_router.post("", status_code=status.HTTP_200_OK)
async def create_message_endpoint(
    conversation_id: Annotated[int, Path(description="display_id")],
    payload: MessageCreateRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``POST /conversations/:conv_id/messages``.

    Rails wraps the call in a ``rescue StandardError`` and renders 422 —
    we do the same via :class:`ChatwootHTTPException` raised inside the
    service.
    """
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=conversation_id
    )
    msg_params = MessageBuilderParams(
        content=payload.content,
        message_type=payload.message_type,
        content_type=payload.content_type,
        content_attributes=payload.content_attributes,
        additional_attributes=payload.additional_attributes,
        private=payload.private,
        source_id=payload.source_id,
        echo_id=payload.echo_id,
        attachments=_attachment_specs_from(payload.attachments),
        campaign_id=payload.campaign_id,
        template_params=payload.template_params,
        external_created_at=_parse_iso(payload.external_created_at, field="external_created_at"),
        cc_emails=payload.cc_emails,
        bcc_emails=payload.bcc_emails,
        to_emails=payload.to_emails,
    )
    msg = await create_message(
        session,
        conversation=conv,
        params=msg_params,
        user_id=ctx.user.id,
    )
    return present_message_create(msg, echo_id=payload.echo_id)


@messages_router.delete("/{message_id}")
async def destroy_message(
    conversation_id: Annotated[int, Path(description="display_id")],
    message_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``DELETE /conversations/:conv_id/messages/:id``.

    Rails semantics: soft-delete by replacing content with the
    i18n-localised deletion string + setting
    ``content_attributes[deleted] = true``, then destroying all
    attachments. The message row stays.
    """
    from sqlalchemy import delete

    from app.domains.conversations.models import (
        CONTENT_TYPE_TEXT,
        Attachment,
    )

    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=conversation_id
    )
    stmt = select(Message).where(
        Message.id == message_id, Message.conversation_id == conv.id
    )
    msg = (await session.exec(stmt)).first()
    if msg is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )

    # ``I18n.t('conversations.messages.deleted')`` → "This message was deleted"
    # in en.yml. Hard-code the English string; i18n lands with Phase 11.
    msg.content = "This message was deleted"
    msg.content_type = CONTENT_TYPE_TEXT
    msg.content_attributes = {"deleted": True}
    session.add(msg)
    await session.exec(
        delete(Attachment).where(Attachment.message_id == msg.id)
    )
    await session.flush()
    await session.refresh(msg)
    return present_message_create(msg)


@messages_router.patch("/{message_id}")
async def update_message(
    conversation_id: Annotated[int, Path(description="display_id")],
    message_id: Annotated[int, Path()],
    payload: dict[str, Any],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``PATCH /conversations/:conv_id/messages/:id`` — API inbox only.

    Permitted params: ``status``, ``external_error`` (mirrors Rails'
    ``params.permit(:id, :target_language, :status, :external_error)``
    minus ``target_language`` — translation lands Phase 5b).

    The ``ensure_api_inbox`` before-action returns 403 with the Rails
    message envelope ``{"error": "..."}`` for non-API conversations.
    Status guard (read -> delivered is a silent no-op) lives in
    :func:`update_message_status`.
    """
    from app.domains.conversations.models import Attachment  # noqa: F401  (registers mapper)
    from app.domains.conversations.presenters import present_message
    from app.domains.conversations.service import update_message_status

    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=conversation_id
    )
    if conv.inbox is None or conv.inbox.channel_type != CHANNEL_TYPE_API:
        raise ChatwootHTTPException(
            status_code=403,
            detail={
                "error": "Message status update is only allowed for API inboxes"
            },
        )

    stmt = select(Message).where(
        Message.id == message_id, Message.conversation_id == conv.id
    )
    msg = (await session.exec(stmt)).first()
    if msg is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )

    new_status = payload.get("status")
    if new_status is None:
        raise ChatwootHTTPException(
            status_code=422,
            detail={"message": "status: parameter required"},
        )
    msg = await update_message_status(
        session,
        message=msg,
        status=str(new_status),
        external_error=payload.get("external_error"),
    )
    # Resolve sender so the presenter emits the ``sender`` block.
    from app.domains.conversations.service import _attach_resolved_sender

    await _attach_resolved_sender(session, message=msg, conversation=conv)
    return present_message(msg)


# =========================================================================
# Participants — agents "watching" a conversation (notifications only)
# =========================================================================
async def _present_participants(
    session: AsyncSession, *, account_id: int, users: list[User]
) -> list[dict[str, Any]]:
    """Render each participant user as an ``_agent`` partial.

    Fetches the participants' AccountUser rows in one query to fill the
    availability / auto_offline fields without an N+1.
    """
    if not users:
        return []
    user_ids = [u.id for u in users]
    au_rows = (
        await session.exec(
            select(AccountUser).where(
                AccountUser.account_id == account_id,
                AccountUser.user_id.in_(user_ids),  # type: ignore[union-attr]
            )
        )
    ).all()
    au_by_user = {au.user_id: au for au in au_rows}
    out: list[dict[str, Any]] = []
    for u in users:
        au = au_by_user.get(u.id)
        out.append(
            present_agent(
                account_id=account_id,
                account_user_availability=au.availability if au else None,
                account_user_auto_offline=au.auto_offline if au else None,
                user=u,
            )
        )
    return out


async def _participants_payload(
    session: AsyncSession, *, account_id: int, conversation_id: int
) -> list[dict[str, Any]]:
    users = await list_participant_users(
        session, conversation_id=conversation_id
    )
    return await _present_participants(
        session, account_id=account_id, users=users
    )


@participants_router.get("")
async def show_participants(
    conversation_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    """``GET .../participants`` — the conversation's watcher list."""
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=conversation_id
    )
    assert conv.id is not None
    return await _participants_payload(
        session, account_id=ctx.account.id, conversation_id=conv.id
    )


@participants_router.post("", status_code=status.HTTP_200_OK)
async def create_participants(
    conversation_id: Annotated[int, Path()],
    payload: ParticipantsRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    """``POST .../participants`` — add ``user_ids``; renders the full list."""
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=conversation_id
    )
    assert conv.id is not None
    await add_participants(
        session, conversation=conv, user_ids=payload.user_ids
    )
    return await _participants_payload(
        session, account_id=ctx.account.id, conversation_id=conv.id
    )


@participants_router.patch("")
async def update_participants(
    conversation_id: Annotated[int, Path()],
    payload: ParticipantsRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, Any]]:
    """``PATCH .../participants`` — reconcile the set to exactly ``user_ids``."""
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=conversation_id
    )
    assert conv.id is not None
    await set_participants(
        session, conversation=conv, user_ids=payload.user_ids
    )
    return await _participants_payload(
        session, account_id=ctx.account.id, conversation_id=conv.id
    )


@participants_router.delete("", status_code=status.HTTP_200_OK)
async def destroy_participants(
    conversation_id: Annotated[int, Path()],
    payload: ParticipantsRequest,
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """``DELETE .../participants`` — remove ``user_ids`` → Rails ``head :ok``."""
    assert ctx.account.id is not None
    conv = await _load_conversation_by_display_id(
        session, account_id=ctx.account.id, display_id=conversation_id
    )
    assert conv.id is not None
    await remove_participants(
        session, conversation=conv, user_ids=payload.user_ids
    )
    return {}


__all__ = ["messages_router", "participants_router", "router"]
