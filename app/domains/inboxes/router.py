"""Inbox + inbox_members HTTP endpoints.

Ports ``Api::V1::Accounts::InboxesController`` +
``Api::V1::Accounts::InboxMembersController``.

Route map (Chatwoot):

  * ``GET    /api/v1/accounts/:account_id/inboxes``
  * ``POST   /api/v1/accounts/:account_id/inboxes``
  * ``GET    /api/v1/accounts/:account_id/inboxes/:id``
  * ``PATCH  /api/v1/accounts/:account_id/inboxes/:id``
  * ``DELETE /api/v1/accounts/:account_id/inboxes/:id``
  * ``POST   /api/v1/accounts/:account_id/inboxes/:id/reset_secret``
  * ``GET    /api/v1/accounts/:account_id/inbox_members/:inbox_id``
  * ``POST   /api/v1/accounts/:account_id/inbox_members``
  * ``PATCH  /api/v1/accounts/:account_id/inbox_members``
  * ``DELETE /api/v1/accounts/:account_id/inbox_members``

``inbox_members`` is NOT nested under ``/inboxes/:inbox_id`` — Chatwoot
declares it as a top-level resource under the account with
``param: :inbox_id``. That makes ``show`` the only verb that carries
``inbox_id`` in the path; create/update/destroy read it from the JSON
body. Parity with that exact surface matters because the dashboard
client hits these URLs directly.

Authorisation per Chatwoot's :class:`InboxPolicy`:

  * ``index?`` / ``show?`` → any member of the account
  * ``create?`` / ``update?`` / ``destroy?`` / ``reset_secret?`` → administrator
  * ``inbox_members`` actions share the inbox's policy (the controller
    authorises the underlying inbox, not the join)

Delete behaviour: Chatwoot queues ``DeleteObjectJob`` (async) and returns
``{"message": "The inbox is scheduled for deletion"}`` with status 200.
We do a synchronous cascade delete in-process and return the same body —
there are no background jobs wired in Phase 2, and the inbox-membership
cascade at the DB level handles the polymorphic channel_api/inbox_members
removal via ON DELETE CASCADE.

Phase 2 also leaves ``AuthorizationService.check_limit`` (seat/inbox
enterprise limits) unimplemented — the ``before_action :validate_limit``
guard in Ruby is a no-op for OSS installs.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import (
    AccountContext,
    account_context,
    require_admin,
)
from app.core.errors import ChatwootHTTPException
from app.domains.inboxes.models import (
    CHANNEL_TYPE_API,
    CHANNEL_TYPE_EMAIL,
    CHANNEL_TYPE_FACEBOOK,
    CHANNEL_TYPE_INSTAGRAM,
    CHANNEL_TYPE_SMS,
    CHANNEL_TYPE_TELEGRAM,
    CHANNEL_TYPE_TWILIO_SMS,
    CHANNEL_TYPE_WEB_WIDGET,
    CHANNEL_TYPE_WHATSAPP,
    ApiChannel,
    EmailChannel,
    FacebookPage,
    Inbox,
    InboxMember,
    InstagramChannel,
    SmsChannel,
    TelegramChannel,
    TwilioSmsChannel,
    WebWidget,
    WhatsappChannel,
)
from app.domains.inboxes.presenters import (
    present_agent,
    present_inbox,
    present_inboxes_index,
)
from app.domains.inboxes.schemas import (
    InboxCreateRequest,
    InboxMembersBody,
    InboxUpdateRequest,
)
from app.domains.inboxes.service import (
    InboxBuilder,
    InboxBuilderParams,
    add_members,
    list_member_ids,
    remove_members,
    reset_api_channel_secret,
    update_inbox,
)
from app.domains.users.models import AccountUser, User

router = APIRouter(prefix="/api/v1/accounts/{account_id}/inboxes", tags=["inboxes"])

# inbox_members is a sibling router — declared as a top-level account
# resource in Chatwoot (``resources :inbox_members, param: :inbox_id``).
# Only ``show`` puts inbox_id in the path; the other verbs read it from
# the JSON body.
inbox_members_router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/inbox_members",
    tags=["inboxes"],
)


# ============================================================================
# Inbox CRUD
# ============================================================================
@router.get("")
async def list_inboxes(
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``GET /api/v1/accounts/:account_id/inboxes`` — list inboxes.

    Chatwoot's policy_scope for :class:`InboxPolicy` returns
    ``user.assigned_inboxes`` — i.e. agents only see inboxes they're
    members of. Admins see all (via ``account.inboxes``). We mirror that
    split: admins get the full account set; agents get the join-filtered
    set.
    """
    assert ctx.account.id is not None
    if ctx.is_administrator:
        inbox_stmt = (
            select(Inbox)
            .where(Inbox.account_id == ctx.account.id)
            .order_by(Inbox.name, Inbox.id)  # type: ignore[arg-type]
        )
    else:
        # Agents: only inboxes where the agent has an InboxMember row.
        inbox_stmt = (
            select(Inbox)
            .join(InboxMember, InboxMember.inbox_id == Inbox.id)  # type: ignore[arg-type]
            .where(Inbox.account_id == ctx.account.id, InboxMember.user_id == ctx.user.id)
            .order_by(Inbox.name, Inbox.id)  # type: ignore[arg-type]
        )
    inboxes = list((await session.exec(inbox_stmt)).all())
    channels = await _load_channels_for(session, inboxes)
    rows = [(ix, channels.get(ix.id)) for ix in inboxes]
    return present_inboxes_index(rows, is_administrator=ctx.is_administrator)


@router.post("", status_code=status.HTTP_200_OK)
async def create_inbox(
    payload: InboxCreateRequest,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``POST /api/v1/accounts/:account_id/inboxes`` — admin-only.

    Chatwoot returns 200 (not 201) on create — we match exactly.
    """
    result = await InboxBuilder(
        session,
        InboxBuilderParams(
            account=ctx.account,
            name=payload.name,
            channel_type=payload.channel.type,
            # Forward every channel field (not just the Api trio) so the
            # builder's per-type paths (telegram bot_token, whatsapp
            # provider_config, twilio account_sid, …) receive their params.
            channel_params=payload.channel.model_dump(exclude={"type"}),
            greeting_enabled=payload.greeting_enabled,
            greeting_message=payload.greeting_message,
            enable_email_collect=payload.enable_email_collect,
            csat_survey_enabled=payload.csat_survey_enabled,
            enable_auto_assignment=payload.enable_auto_assignment,
            working_hours_enabled=payload.working_hours_enabled,
            out_of_office_message=payload.out_of_office_message,
            timezone=payload.timezone,
            allow_messages_after_resolved=payload.allow_messages_after_resolved,
            lock_to_single_conversation=payload.lock_to_single_conversation,
            portal_id=payload.portal_id,
            sender_name_type=payload.sender_name_type,
            business_name=payload.business_name,
            csat_config=payload.csat_config,
        ),
    ).perform()
    # The presenter handles every channel type (Api detail, plus the callback
    # webhook URL + WhatsApp verify token for the messaging channels).
    return present_inbox(result.inbox, channel=result.channel, is_administrator=True)


@router.get("/{inbox_id}")
async def show_inbox(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``GET /api/v1/accounts/:account_id/inboxes/:id`` — show.

    Policy ``show?`` allows any assigned agent or any admin. 404 if the
    inbox isn't in this account; 401 if the agent isn't a member.
    """
    inbox = await _find_inbox_in_account(session, ctx, inbox_id)
    await _authorize_inbox_show(session, ctx, inbox)
    channel = await _load_channel_row(session, inbox)
    return present_inbox(inbox, channel=channel, is_administrator=ctx.is_administrator)


@router.patch("/{inbox_id}")
async def update_inbox_endpoint(
    inbox_id: Annotated[int, Path()],
    payload: InboxUpdateRequest,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``PATCH /api/v1/accounts/:account_id/inboxes/:id`` — admin-only."""
    inbox = await _find_inbox_in_account(session, ctx, inbox_id)
    # The concrete row, not the Api-only helper: an email inbox has
    # editable fields too and would otherwise silently ignore them.
    channel = await _load_channel_row(session, inbox)
    channel_updates = payload.channel.model_dump(exclude_none=True) if payload.channel else {}

    updated = await update_inbox(
        session,
        inbox=inbox,
        channel=channel,
        inbox_updates=payload.model_dump(
            exclude={"channel", "sender_name_type", "csat_config"},
            exclude_none=True,
        ),
        channel_updates=channel_updates,
        sender_name_type=payload.sender_name_type,
        csat_config=payload.csat_config,
    )
    return present_inbox(updated, channel=channel, is_administrator=True)


@router.delete("/{inbox_id}", status_code=status.HTTP_200_OK)
async def destroy_inbox(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``DELETE /api/v1/accounts/:account_id/inboxes/:id`` — admin-only.

    Chatwoot queues ``DeleteObjectJob.perform_later`` and returns the
    message synchronously. We delete in-process (no background job yet)
    but match the response body — clients hitting this endpoint don't
    see the difference.
    """
    inbox = await _find_inbox_in_account(session, ctx, inbox_id)
    channel = await _load_channel_row(session, inbox)

    # Cascade: FK ondelete='CASCADE' on inbox_members clears the join
    # rows. The polymorphic channel_api row has no FK to inbox_id so we
    # remove it explicitly — mirrors Rails' ``belongs_to :channel,
    # dependent: :destroy_async``.
    await session.delete(inbox)
    if channel is not None:
        await session.delete(channel)
    await session.flush()
    return {"message": "The inbox is scheduled for deletion"}


@router.post("/{inbox_id}/reset_secret", status_code=status.HTTP_200_OK)
async def reset_secret_endpoint(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``POST /api/v1/accounts/:account_id/inboxes/:id/reset_secret``.

    Chatwoot: ``return head :not_found unless @inbox.api?`` — a
    non-Channel::Api inbox returns a bare 404. We match.
    """
    inbox = await _find_inbox_in_account(session, ctx, inbox_id)
    if inbox.channel_type != CHANNEL_TYPE_API:
        raise ChatwootHTTPException(status_code=404, detail={})
    channel = await _load_channel(session, inbox)
    if channel is None:
        # Dangling inbox — shouldn't happen because the schema is
        # append-only for channel_api rows. Defensive 404 mirrors the
        # ``head :not_found`` shape.
        raise ChatwootHTTPException(status_code=404, detail={})
    await reset_api_channel_secret(session, channel)
    return present_inbox(inbox, channel=channel, is_administrator=True)


# ============================================================================
# InboxMembers
# ============================================================================
@inbox_members_router.get("/{inbox_id}")
async def show_inbox_members(
    inbox_id: Annotated[int, Path()],
    ctx: Annotated[AccountContext, Depends(account_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``GET /inbox_members/:inbox_id`` — list member agents.

    This is the only inbox_members verb that carries ``inbox_id`` in the
    path — Chatwoot's ``resources :inbox_members, param: :inbox_id``
    makes the ``show`` action use ``/inbox_members/:inbox_id``. The
    other verbs read ``inbox_id`` from the JSON body.
    """
    inbox = await _find_inbox_in_account(session, ctx, inbox_id)
    await _authorize_inbox_show(session, ctx, inbox)
    return await _present_members_payload(session, ctx, inbox)


@inbox_members_router.post("", status_code=status.HTTP_200_OK)
async def create_inbox_members(
    payload: InboxMembersBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``POST /inbox_members`` — add agents.

    ``inbox_id`` comes from the body. Chatwoot's behaviour:
    ``add_members(params[:user_ids] - current)`` — only new ones are
    inserted. Our service-layer :func:`add_members` does the same filter.
    """
    inbox_id = _require_inbox_id(payload)
    inbox = await _find_inbox_in_account(session, ctx, inbox_id)
    await add_members(session, inbox=inbox, user_ids=payload.user_ids)
    return await _present_members_payload(session, ctx, inbox)


@inbox_members_router.patch("", status_code=status.HTTP_200_OK)
async def update_inbox_members(
    payload: InboxMembersBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``PATCH /inbox_members`` — replace the agent set.

    Chatwoot's controller does an add-then-remove inside a transaction.
    We mirror: compute diff, add the new, remove the dropped.
    """
    inbox_id = _require_inbox_id(payload)
    inbox = await _find_inbox_in_account(session, ctx, inbox_id)
    assert inbox.id is not None
    current = set(await list_member_ids(session, inbox.id))
    desired = set(payload.user_ids)
    to_add = sorted(desired - current)
    to_remove = sorted(current - desired)
    await add_members(session, inbox=inbox, user_ids=to_add)
    await remove_members(session, inbox=inbox, user_ids=to_remove)
    return await _present_members_payload(session, ctx, inbox)


@inbox_members_router.delete("", status_code=status.HTTP_200_OK)
async def destroy_inbox_members(
    payload: InboxMembersBody,
    ctx: Annotated[AccountContext, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """``DELETE /inbox_members`` — remove listed agents."""
    inbox_id = _require_inbox_id(payload)
    inbox = await _find_inbox_in_account(session, ctx, inbox_id)
    await remove_members(session, inbox=inbox, user_ids=payload.user_ids)
    # Chatwoot: ``head :ok`` — empty body, 200 status.
    return {}


def _require_inbox_id(payload: InboxMembersBody) -> int:
    """Body-param extraction for create/update/destroy.

    Chatwoot expects ``inbox_id`` in the JSON body for these three verbs
    (the show action reads it from the path). Missing → 404 parity with
    ``Current.account.inboxes.find(nil)``.
    """
    if payload.inbox_id is None:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    return payload.inbox_id


# ============================================================================
# helpers
# ============================================================================
async def _find_inbox_in_account(
    session: AsyncSession, ctx: AccountContext, inbox_id: int
) -> Inbox:
    """Scope by account. 404 if not found — matches
    ``Current.account.inboxes.find(id)``.
    """
    stmt = select(Inbox).where(Inbox.id == inbox_id, Inbox.account_id == ctx.account.id)
    inbox = (await session.exec(stmt)).first()
    if inbox is None:
        raise ChatwootHTTPException(
            status_code=404,
            detail={"error": "Resource could not be found"},
        )
    return inbox


async def _authorize_inbox_show(
    session: AsyncSession, ctx: AccountContext, inbox: Inbox
) -> None:
    """``InboxPolicy#show?`` — admins always, agents only if member."""
    if ctx.is_administrator:
        return
    assert inbox.id is not None
    stmt = select(InboxMember).where(
        InboxMember.inbox_id == inbox.id, InboxMember.user_id == ctx.user.id
    )
    member = (await session.exec(stmt)).first()
    if member is None:
        raise ChatwootHTTPException(
            status_code=401,
            detail={"error": "You are not authorized to do this action"},
        )


async def _load_channel(session: AsyncSession, inbox: Inbox) -> ApiChannel | None:
    """Resolve the polymorphic channel row for one inbox (Channel::Api only)."""
    if inbox.channel_type != CHANNEL_TYPE_API:
        return None
    stmt = select(ApiChannel).where(ApiChannel.id == inbox.channel_id)
    return (await session.exec(stmt)).first()


# Channel-type → concrete model, for resolving the polymorphic channel row of
# ANY type. Used by delete so a non-Api inbox doesn't orphan its channel row.
_CHANNEL_MODEL_BY_TYPE: dict[str, type] = {
    CHANNEL_TYPE_API: ApiChannel,
    CHANNEL_TYPE_WEB_WIDGET: WebWidget,
    CHANNEL_TYPE_EMAIL: EmailChannel,
    CHANNEL_TYPE_WHATSAPP: WhatsappChannel,
    CHANNEL_TYPE_FACEBOOK: FacebookPage,
    CHANNEL_TYPE_INSTAGRAM: InstagramChannel,
    CHANNEL_TYPE_TWILIO_SMS: TwilioSmsChannel,
    CHANNEL_TYPE_SMS: SmsChannel,
    CHANNEL_TYPE_TELEGRAM: TelegramChannel,
}


async def _load_channel_row(session: AsyncSession, inbox: Inbox) -> Any | None:
    """Resolve the concrete channel row for an inbox of *any* channel type.

    ``_load_channel`` is Channel::Api-only (the presenter needs that exact
    type). This sibling resolves whichever per-type table the inbox points at
    — used by ``destroy_inbox`` so deleting a non-Api inbox also removes its
    channel row (Rails' ``dependent: :destroy_async``).
    """
    model = _CHANNEL_MODEL_BY_TYPE.get(inbox.channel_type or "")
    if model is None:
        return None
    stmt = select(model).where(model.id == inbox.channel_id)  # type: ignore[attr-defined]
    return (await session.exec(stmt)).first()


async def _load_channels_for(
    session: AsyncSession, inboxes: list[Inbox]
) -> dict[int, ApiChannel]:
    """Batch-resolve Channel::Api rows for a list of inboxes (index endpoint).

    Keyed by ``inbox.id`` so presenters can look up in O(1). Inboxes with
    non-Api channels are simply missing from the dict.
    """
    api_ids = [ix.channel_id for ix in inboxes if ix.channel_type == CHANNEL_TYPE_API]
    if not api_ids:
        return {}
    stmt = select(ApiChannel).where(ApiChannel.id.in_(api_ids))
    channels = {c.id: c for c in (await session.exec(stmt)).all()}
    by_inbox: dict[int, ApiChannel] = {}
    for ix in inboxes:
        if ix.channel_type == CHANNEL_TYPE_API and ix.id is not None:
            c = channels.get(ix.channel_id)
            if c is not None:
                by_inbox[ix.id] = c
    return by_inbox


async def _present_members_payload(
    session: AsyncSession, ctx: AccountContext, inbox: Inbox
) -> dict:
    """``{"payload": [agent, ...]}`` — Chatwoot's inbox_members response."""
    assert inbox.id is not None and ctx.account.id is not None
    # Pull (User, AccountUser) pairs for the inbox's members.
    stmt = (
        select(User, AccountUser)
        .join(InboxMember, InboxMember.user_id == User.id)  # type: ignore[arg-type]
        .join(
            AccountUser,
            (AccountUser.user_id == User.id) & (AccountUser.account_id == ctx.account.id),  # type: ignore[arg-type]
        )
        .where(InboxMember.inbox_id == inbox.id)
        .order_by(User.name, User.id)  # type: ignore[arg-type]
    )
    rows = (await session.exec(stmt)).all()
    agents = [
        present_agent(
            account_id=ctx.account.id,
            account_user_availability=au.availability,
            account_user_auto_offline=au.auto_offline,
            user=u,
        )
        for (u, au) in rows
    ]
    return {"payload": agents}
