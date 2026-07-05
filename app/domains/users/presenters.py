"""Build API response dicts from User + AccountUser + Account rows.

Ported from:
  reference/chatwoot/app/views/api/v1/models/_user.json.jbuilder
  reference/chatwoot/app/views/api/v1/accounts/create.json.jbuilder

Chatwoot's Rails views reach directly into ActiveRecord to render. We
mirror that shape here with plain dicts so FastAPI can serialise with
whatever JSON encoder it likes (the parity harness compares dicts, not
byte-for-byte strings).

Why dicts rather than Pydantic model instances: the signup view emits
``account_id`` which isn't a User column — it's ``@account.id`` from the
controller. Doing assembly here keeps the call sites (router.py) simple.
"""

from __future__ import annotations

from app.domains.accounts.models import Account
from app.domains.users.models import (
    ACCOUNT_USER_ROLE_ADMINISTRATOR,
    AccessToken,
    AccountUser,
    User,
)


def _avatar_url(user: User) -> str:
    """Port of Rails ``Avatarable#avatar_url``.

    Returns the user's uploaded avatar URL (our MinIO/S3 pipeline) when set.
    Chatwoot additionally falls back to a Gravatar URL built from the email;
    we don't (no Gravatar dependency) — an unset avatar returns ``""``.
    """
    return user.avatar_url or ""


def _available_name(user: User) -> str:
    return user.display_name or user.name


def _permissions_for(account_user: AccountUser) -> list[str]:
    return (
        ["administrator"]
        if account_user.role == ACCOUNT_USER_ROLE_ADMINISTRATOR
        else ["agent"]
    )


def _availability_status(availability: int) -> str:
    return {0: "online", 1: "offline", 2: "busy"}.get(availability, "offline")


def present_signup_response(
    user: User,
    account: Account,
    access_token: AccessToken,
    account_users: list[AccountUser],
) -> dict:
    """Shape of ``POST /api/v1/accounts`` — ``accounts/create.json.jbuilder``.

    ``account_users`` must include every AccountUser row the user belongs
    to, preloaded with their Account, so we can render the ``accounts: []``
    array without extra queries.
    """
    return {
        "data": {
            "id": user.id,
            "provider": user.provider,
            "uid": user.uid,
            "name": user.name,
            "display_name": user.display_name,
            "email": user.email,
            "account_id": account.id,
            "created_at": user.created_at,
            "pubsub_token": user.pubsub_token,
            "role": _resolve_active_role(user.id, account.id, account_users),
            "inviter_id": _resolve_active_inviter(user.id, account.id, account_users),
            "confirmed": user.confirmed_at is not None,
            "avatar_url": _avatar_url(user),
            "access_token": access_token.token,
            "accounts": [
                {
                    "id": au.account_id,
                    "name": au.account.name,
                    "active_at": au.active_at,
                    "role": au.role,
                    "locale": au.account.locale,
                }
                for au in account_users
            ],
        }
    }


def present_auth_response(
    user: User,
    access_token: AccessToken,
    account_users: list[AccountUser],
    active_account_id: int | None = None,
) -> dict:
    """Shape of ``POST /auth/sign_in`` + ``GET /api/v1/profile``.

    Mirrors ``_user.json.jbuilder``. ``active_account_id`` picks which
    AccountUser row supplies the top-level ``role`` / ``account_id`` /
    ``inviter_id`` fields; defaults to the first membership (matches
    Chatwoot's ``active_account_user`` helper which returns the first
    account_user by id).
    """
    active_au = _pick_active(account_users, active_account_id)

    data = {
        "access_token": access_token.token,
        "account_id": active_au.account_id if active_au else None,
        "available_name": _available_name(user),
        "avatar_url": _avatar_url(user),
        "confirmed": user.confirmed_at is not None,
        "display_name": user.display_name,
        "message_signature": user.message_signature,
        "email": user.email,
        "id": user.id,
        "inviter_id": active_au.inviter_id if active_au else None,
        "name": user.name,
        "provider": user.provider,
        "pubsub_token": user.pubsub_token,
        "role": active_au.role if active_au else None,
        "ui_settings": user.ui_settings or {},
        "uid": user.uid,
        "type": user.type,
        "accounts": [
            {
                "id": au.account_id,
                "name": au.account.name,
                "status": au.account.status,
                "active_at": au.active_at,
                "role": au.role,
                "permissions": _permissions_for(au),
                "availability": au.availability,
                "availability_status": _availability_status(au.availability),
                "auto_offline": au.auto_offline,
            }
            for au in account_users
        ],
    }
    # jbuilder: `json.custom_attributes resource.custom_attributes if ...present?`
    if user.custom_attributes:
        data["custom_attributes"] = user.custom_attributes

    return {"data": data}


# ---------------------------------------------------------------- helpers


def _pick_active(
    account_users: list[AccountUser], active_account_id: int | None
) -> AccountUser | None:
    if not account_users:
        return None
    if active_account_id is not None:
        for au in account_users:
            if au.account_id == active_account_id:
                return au
    # ``active_account_user`` in Ruby is the first membership ordered by id.
    return sorted(account_users, key=lambda a: a.id or 0)[0]


def _resolve_active_role(
    user_id: int | None, account_id: int | None, account_users: list[AccountUser]
) -> int:
    for au in account_users:
        if au.user_id == user_id and au.account_id == account_id:
            return au.role
    return ACCOUNT_USER_ROLE_ADMINISTRATOR


def _resolve_active_inviter(
    user_id: int | None, account_id: int | None, account_users: list[AccountUser]
) -> int | None:
    for au in account_users:
        if au.user_id == user_id and au.account_id == account_id:
            return au.inviter_id
    return None
