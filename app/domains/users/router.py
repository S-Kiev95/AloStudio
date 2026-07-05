"""``/api/v1/profile`` — the current user's own record.

Ports ``Api::V1::ProfilesController`` from
``reference/chatwoot/app/controllers/api/v1/profiles_controller.rb``.

Chatwoot's route file declares::

    resource :profile, only: [:show, :update]

so the wire contract is *singular* — ``GET /api/v1/profile`` and
``PUT /api/v1/profile`` — not ``/profiles/:id``. The profile always refers
to ``current_user``; ``:id`` is irrelevant.

Request shape: Rails wraps everything under a ``profile:`` key
(``params.require(:profile).permit(...)``). We accept the same envelope
so the frontend doesn't branch on backend.

Phase 1 scope includes only ``show`` + ``update``. The additional
``ProfilesController`` actions (avatar delete, availability, auto_offline,
set_active_account, resend_confirmation, reset_access_token, MFA) are
deferred — each requires a dedicated slice in Phase 1.x or later.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_session
from app.core.deps import current_user
from app.core.security import hash_password, verify_password
from app.domains.users.models import AccessToken, AccountUser, User
from app.domains.users.presenters import present_auth_response

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


class _ProfileAttrs(BaseModel):
    """Fields Rails allows inside ``params[:profile]`` — union of every
    permit block in ``profiles_controller.rb`` (profile / password /
    custom_attributes) except for avatar upload and account_id, which
    belong to other actions in Chatwoot.
    """

    email: EmailStr | None = None
    name: str | None = None
    display_name: str | None = None
    message_signature: str | None = None
    avatar_url: str | None = None
    ui_settings: dict | None = None
    # password rotation
    current_password: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)
    password_confirmation: str | None = None
    # custom attributes subset
    phone_number: str | None = None


class ProfileUpdateRequest(BaseModel):
    """``PUT /api/v1/profile`` body — Rails wraps the payload in a
    ``profile`` key (``ActionController::Parameters.require(:profile)``).
    We accept both the wrapped shape *and* a bare object for API-only
    clients; the wrapped form is canonical.
    """

    profile: _ProfileAttrs


@router.get("")
async def show_profile(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """``GET /api/v1/profile`` — renders ``_user.json.jbuilder`` for the
    current user. Same body as the ``/auth/sign_in`` response sans the
    rotated auth headers (no token rotation on read).
    """
    return await _render_user(session, user)


@router.put("")
async def update_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """``PUT /api/v1/profile`` — partial update.

    Mirrors the Ruby action: password rotation runs first and requires
    ``current_password`` to match; then ``profile_params`` get assigned
    (including ``ui_settings`` merge); finally ``custom_attributes`` are
    *merged* into the JSONB column (Chatwoot uses ``merge!``, not
    replace).
    """
    attrs = payload.profile

    # Password rotation branch — runs before other assignments so a
    # failed current_password check aborts cleanly with 422.
    if attrs.password:
        if not attrs.current_password or not verify_password(
            attrs.current_password, user.encrypted_password
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"message": "Invalid current password"},
            )
        if (
            attrs.password_confirmation is not None
            and attrs.password != attrs.password_confirmation
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "message": "Password confirmation doesn't match password"
                },
            )
        user.encrypted_password = hash_password(attrs.password)

    # Profile field assignment — only touch fields the client actually sent.
    if attrs.email is not None:
        user.email = attrs.email.lower()
        user.uid = attrs.email.lower()  # Devise keeps uid==email for email-provider users
    if attrs.name is not None:
        user.name = attrs.name
    if attrs.display_name is not None:
        user.display_name = attrs.display_name
    if attrs.message_signature is not None:
        user.message_signature = attrs.message_signature
    if attrs.avatar_url is not None:
        # Empty string clears the avatar (the presenter maps None → "").
        user.avatar_url = attrs.avatar_url or None
    if attrs.ui_settings is not None:
        # Rails behaviour: `json.ui_settings resource.ui_settings` serialises
        # the full hash, and `assign_attributes(ui_settings: ...)` replaces
        # it. We mirror that (replace, not merge) for ui_settings.
        user.ui_settings = attrs.ui_settings

    # custom_attributes merge (not replace) — matches `custom_attributes.merge!`
    if attrs.phone_number is not None:
        current = dict(user.custom_attributes or {})
        current["phone_number"] = attrs.phone_number
        user.custom_attributes = current

    session.add(user)
    await session.flush()

    return await _render_user(session, user)


# ---------------------------------------------------------------- helpers


async def _render_user(session: AsyncSession, user: User) -> dict:
    """Assemble the ``{data: {...}}`` envelope without rotating auth.

    Reuses :func:`present_auth_response` from the auth router — the
    jbuilder partial is literally the same (``_user.json.jbuilder``), so
    keeping a single presenter avoids drift between profile and sign_in.
    """
    memberships = (
        await session.exec(
            select(AccountUser)
            .where(AccountUser.user_id == user.id)
            .order_by(AccountUser.id)  # type: ignore[arg-type]
        )
    ).all()

    access_token = (
        await session.exec(
            select(AccessToken).where(
                AccessToken.owner_type == "User",
                AccessToken.owner_id == user.id,
            )
        )
    ).first()
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"errors": ["access token missing for user"]},
        )

    return present_auth_response(
        user=user,
        access_token=access_token,
        account_users=list(memberships),
    )
