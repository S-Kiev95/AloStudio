"""Pydantic request schemas for Account endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class AccountCreateRequest(BaseModel):
    """Body accepted by ``POST /api/v1/accounts``.

    Mirrors ``account_params.permit(:account_name, :email, :name, :password,
    :locale, :domain, :support_email, :user_full_name)`` from
    ``accounts_controller.rb``. Chatwoot validates ``account_name OR
    user_full_name`` must be present — we accept either and coalesce at
    the service boundary.

    Password is optional at the request shape level — the builder rejects
    missing password in ``_create_user`` with UserErrors.
    """

    account_name: str | None = Field(default=None, max_length=255)
    user_full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr
    password: str | None = Field(default=None, min_length=8, max_length=72)
    locale: str | None = None
    domain: str | None = None
    support_email: str | None = None
    # h_captcha_client_response: Chatwoot's captcha — accepted but not
    # validated in Phase 1 (no captcha service in local dev). Field kept
    # so the request schema matches the one Chatwoot exposes, avoiding
    # breaking frontend clients.
    h_captcha_client_response: str | None = None
