"""``POST /api/v1/accounts`` — account + user signup.

Ports ``Api::V1::AccountsController#create`` from
``reference/chatwoot/app/controllers/api/v1/accounts_controller.rb``.

Chatwoot's controller does three things we mirror 1:1:

  1. Validates ``account_name`` OR ``user_full_name`` is present
     (``ensure_account_name`` before_action) — returns ``InvalidParams``.
  2. Validates the captcha (``validate_captcha``) — currently stubbed; the
     field is accepted for request-shape parity but never asserted in Phase 1
     because local dev has no captcha provider.
  3. Runs ``AccountBuilder`` in a transaction, then on success attaches the
     devise-token-auth headers and renders ``accounts/create.json.jbuilder``.

Chatwoot distinguishes unauthenticated-web-signup (returns only ``{email}``
until the user confirms via email link) from authenticated / api-only signup
(returns full payload with auth headers). In Phase 1 we're the API-only
backend — we always return the full payload.

Branding enrichment + Redis SET for the onboarding flag (lines 73-81 in the
Ruby controller) are queued background work; deferred until ARQ jobs land.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth.devise_token_auth import create_new_auth_token
from app.core.db import get_session
from app.core.deps import current_user
from app.domains.accounts.exceptions import (
    AccountSignupError,
    InvalidParams,
)
from app.domains.accounts.models import Account
from app.domains.accounts.presenters import present_account_show
from app.domains.accounts.schemas import AccountCreateRequest
from app.domains.accounts.service import AccountBuilder, AccountBuilderParams
from app.domains.users.models import AccountUser, User
from app.domains.users.presenters import (
    _availability_status,
    _available_name,
    _avatar_url,
    present_signup_response,
)

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


@router.post("", status_code=status.HTTP_200_OK)
async def create_account(
    payload: AccountCreateRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Chatwoot's ``POST /api/v1/accounts`` — signup.

    Returns the user+account payload plus devise-token-auth session headers.
    Errors map to HTTP 422 with the same JSON envelope Chatwoot emits
    (``{"message": "...", ...payload}``).
    """
    # ensure_account_name before_action
    if not (payload.account_name or payload.user_full_name):
        raise _to_http(InvalidParams())

    # h_captcha is accepted but not validated in Phase 1 — noop.

    try:
        result = await AccountBuilder(
            session,
            AccountBuilderParams(
                email=payload.email,
                account_name=payload.account_name,
                user_full_name=payload.user_full_name,
                user_password=payload.password,
                locale=payload.locale,
                # Web-signup flow in Chatwoot does NOT confirm the email until
                # the user clicks the link. Phase 1 is API-only so we behave
                # like ``api_only_signup?`` — set ``confirmed=True`` to skip
                # confirmable gating on subsequent /auth/sign_in.
                confirmed=True,
            ),
        ).perform()
    except AccountSignupError as e:
        raise _to_http(e) from e

    # send_auth_headers: mint new devise-token-auth session for this user.
    headers, new_tokens = create_new_auth_token(
        user_tokens=result.user.tokens,
        uid=result.user.uid,
    )
    result.user.tokens = new_tokens
    session.add(result.user)
    await session.flush()

    for k, v in headers.as_response_headers().items():
        response.headers[k] = v

    # Preload the user's account_users + account rows for the presenter.
    stmt = (
        select(AccountUser)
        .where(AccountUser.user_id == result.user.id)
        .order_by(AccountUser.id)  # type: ignore[arg-type]
    )
    rows = (await session.exec(stmt)).all()

    return present_signup_response(
        user=result.user,
        account=result.account,
        access_token=result.access_token,
        account_users=list(rows),
    )


class AccountUpdateRequest(BaseModel):
    """Body permitted by ``PATCH /api/v1/accounts/:id``.

    Corresponds to ``account_params.slice(:name, :locale, :domain, :support_email)``
    plus ``custom_attributes_params.permit(:industry, :company_size, :timezone)``
    and ``settings_params`` (auto-resolve knobs, audio transcriptions).

    Chatwoot merges ``custom_attributes`` and ``settings`` (not replace) and
    assigns the top-level scalars directly. We mirror that here.
    """

    name: str | None = None
    locale: int | None = None
    domain: str | None = None
    support_email: str | None = None
    # custom_attributes_params — only these three keys are permitted by Rails.
    industry: str | None = None
    company_size: str | None = None
    timezone: str | None = None
    # settings_params — auto-resolve bundle.
    auto_resolve_after: int | None = None
    auto_resolve_message: str | None = None
    auto_resolve_ignore_waiting: bool | None = None
    audio_transcriptions: bool | None = None
    auto_resolve_label: str | None = None


@router.get("/{account_id}")
async def show_account(
    account_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """``GET /api/v1/accounts/:id`` — account detail.

    Rails' ``fetch_account`` before_action scopes the lookup to the
    current user's accounts (``current_user.accounts.find(params[:id])``)
    so a 404 is the correct response for both "account doesn't exist" and
    "account exists but user is not a member". We preserve that behaviour
    — don't leak account existence to non-members.
    """
    account = await _find_authorised_account(session, user, account_id)
    # latest_chatwoot_version comes from Redis in Chatwoot (::Redis::Alfred).
    # Phase 1 has no Redis-backed release-check; return None so the key is
    # omitted from the response (matches "no value in cache" on reference).
    return present_account_show(account)


@router.patch("/{account_id}")
async def update_account(
    account_id: int,
    payload: AccountUpdateRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """``PATCH /api/v1/accounts/:id`` — partial update.

    Mirrors ``AccountsController#update``::

        @account.assign_attributes(account_params.slice(...))
        @account.custom_attributes.merge!(custom_attributes_params)
        @account.settings.merge!(settings_params)
        @account.custom_attributes['onboarding_step'] = 'invite_team' if
          @account.custom_attributes['onboarding_step'] == 'account_update'
        @account.save!

    That last line advances the onboarding_step state machine — any
    client update that leaves ``custom_attributes.onboarding_step`` at
    'account_update' implicitly transitions it to 'invite_team'. We
    preserve it verbatim.
    """
    account = await _find_authorised_account(session, user, account_id)

    # Scalars — only touch what the client sent.
    if payload.name is not None:
        account.name = payload.name
    if payload.locale is not None:
        account.locale = payload.locale
    if payload.domain is not None:
        account.domain = payload.domain
    if payload.support_email is not None:
        account.support_email = payload.support_email

    # custom_attributes merge
    custom_updates = {
        k: v
        for k, v in {
            "industry": payload.industry,
            "company_size": payload.company_size,
            "timezone": payload.timezone,
        }.items()
        if v is not None
    }
    if custom_updates:
        merged = dict(account.custom_attributes or {})
        merged.update(custom_updates)
        account.custom_attributes = merged

    # settings merge
    setting_updates = {
        k: v
        for k, v in {
            "auto_resolve_after": payload.auto_resolve_after,
            "auto_resolve_message": payload.auto_resolve_message,
            "auto_resolve_ignore_waiting": payload.auto_resolve_ignore_waiting,
            "audio_transcriptions": payload.audio_transcriptions,
            "auto_resolve_label": payload.auto_resolve_label,
        }.items()
        if v is not None
    }
    if setting_updates:
        merged_settings = dict(account.settings or {})
        merged_settings.update(setting_updates)
        account.settings = merged_settings

    # Onboarding step auto-advance — preserve the Rails line verbatim.
    if (account.custom_attributes or {}).get("onboarding_step") == "account_update":
        merged_ca = dict(account.custom_attributes or {})
        merged_ca["onboarding_step"] = "invite_team"
        account.custom_attributes = merged_ca

    session.add(account)
    await session.flush()

    return present_account_show(account)


@router.get("/{account_id}/agents")
async def list_agents(
    account_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """``GET /api/v1/accounts/:id/agents`` — list of users in the account.

    Ports ``Api::V1::Accounts::AgentsController#index`` + the partial
    ``_agent.json.jbuilder``. Chatwoot's scope is
    ``Current.account.users.order_by_full_name.includes(:account_users, ...)``
    — every User with an AccountUser row in this account, ordered by
    full name ascending.

    We emit the union of User + AccountUser fields for the specific
    ``(user, account)`` row (``role``, ``availability_status``,
    ``auto_offline`` come from ``AccountUser``).
    """
    # Authorise: current_user must be a member of this account.
    await _find_authorised_account(session, user, account_id)

    # Pull (AccountUser, User) pairs for this account.
    stmt = (
        select(AccountUser, User)
        .join(User, User.id == AccountUser.user_id)  # type: ignore[arg-type]
        .where(AccountUser.account_id == account_id)
        .order_by(User.name, User.id)  # type: ignore[arg-type]
    )
    rows = (await session.exec(stmt)).all()

    return [_agent_view(account_id, au, u) for (au, u) in rows]


def _agent_view(account_id: int, au: AccountUser, u: User) -> dict:
    """Shape of a single entry in the agents index response.

    Mirrors ``_agent.json.jbuilder``. ``custom_attributes`` is only emitted
    when non-empty (matches Rails ``if resource.custom_attributes.present?``);
    enterprise-only ``custom_role_id`` is omitted in Phase 1.
    """
    body = {
        "id": u.id,
        "account_id": account_id,
        "availability_status": _availability_status(au.availability),
        "auto_offline": au.auto_offline,
        "confirmed": u.confirmed_at is not None,
        "email": u.email,
        "provider": u.provider,
        "available_name": _available_name(u),
        "name": u.name,
        "role": au.role,
        "thumbnail": _avatar_url(u),
        # Permissions are not in the jbuilder partial but useful to match
        # frontend expectations — Chatwoot emits them from the User model
        # via the enterprise prepend. Keep out for strict parity.
    }
    if u.custom_attributes:
        body["custom_attributes"] = u.custom_attributes
    return body


async def _find_authorised_account(
    session: AsyncSession, user: User, account_id: int
) -> Account:
    """``current_user.accounts.find(id)`` equivalent.

    Joins through :class:`AccountUser`; 404s if the (user, account) pair
    doesn't exist, matching Rails' ``ActiveRecord::RecordNotFound`` →
    Chatwoot's global handler renders 404.
    """
    stmt = (
        select(Account)
        .join(AccountUser, AccountUser.account_id == Account.id)  # type: ignore[arg-type]
        .where(Account.id == account_id, AccountUser.user_id == user.id)
    )
    account = (await session.exec(stmt)).first()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "Resource not found"},
        )
    return account


def _to_http(exc: AccountSignupError) -> HTTPException:
    """Translate a domain exception to Chatwoot's error-body shape.

    Chatwoot's ``render_error_response`` emits::

        { "message": exc.message, **exc.data }

    with the exception's HTTP status. We replicate that envelope so parity
    tests don't diverge on error paths.
    """
    body = {"message": exc.message, **exc.payload}
    return HTTPException(status_code=exc.status_code, detail=body)
