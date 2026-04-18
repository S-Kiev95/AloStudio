"""Pydantic schemas for User & AccountUser responses.

These mirror the jbuilder templates in
``reference/chatwoot/app/views/api/v1/models/_user.json.jbuilder`` and
``.../accounts/create.json.jbuilder`` so that parity tests comparing
AloStudio responses against the reference instance only diverge on
volatile fields (timestamps, ids, tokens) which the parity harness
already ignores.

Shapes explicitly preserved:

  * ``role`` is the *integer* (0=agent, 1=administrator) — the Rails enum
    is an integer column and jbuilder emits the raw value.
  * ``availability`` and ``status`` are integers for the same reason.
  * ``availability_status`` is the string form (helper).
  * ``permissions`` is an array — currently ``["administrator"]`` or
    ``["agent"]``; enterprise custom_role permissions plug in later.
  * ``custom_attributes`` is omitted when empty (jbuilder does
    ``if resource.custom_attributes.present?``) — modelled with
    ``exclude_none``/``exclude_defaults`` at the caller.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AccountNested(BaseModel):
    """The per-account object rendered inside ``user.accounts``.

    Mirrors the block in _user.json.jbuilder lines 20-34.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: int  # 0=active, 1=suspended
    active_at: datetime | None
    role: int  # 0=agent, 1=administrator
    permissions: list[str]
    availability: int  # AccountUser.availability (0/1/2)
    availability_status: str  # "online"/"offline"/"busy"
    auto_offline: bool


class AccountNestedSignup(BaseModel):
    """The simpler per-account object emitted by /api/v1/accounts/create.

    The signup view omits status/permissions/availability — see
    accounts/create.json.jbuilder lines 16-24.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    active_at: datetime | None
    role: int
    locale: int


class UserResponseBase(BaseModel):
    """Common fields across /auth/sign_in and /api/v1/profile."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    uid: str
    email: str | None
    name: str
    display_name: str | None
    available_name: str
    avatar_url: str
    provider: str
    pubsub_token: str | None
    confirmed: bool
    type: str | None
    access_token: str  # polymorphic AccessToken.token, NOT the header
    account_id: int | None
    inviter_id: int | None
    role: int | None
    ui_settings: dict[str, Any]


class UserAuthResponse(UserResponseBase):
    """Response body for /auth/sign_in — _user.json.jbuilder."""

    message_signature: str | None
    # custom_attributes only serialised when non-empty; keep optional
    custom_attributes: dict[str, Any] | None = None
    accounts: list[AccountNested]


class UserSignupResponse(BaseModel):
    """Response body for /api/v1/accounts/create — create.json.jbuilder.

    Shape is intentionally different from UserAuthResponse — Chatwoot emits
    a slimmer payload for signup (no message_signature, slim accounts).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    uid: str
    name: str
    display_name: str | None
    email: str | None
    account_id: int
    created_at: datetime
    pubsub_token: str | None
    role: int
    inviter_id: int | None
    confirmed: bool
    avatar_url: str
    access_token: str
    accounts: list[AccountNestedSignup]
