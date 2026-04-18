"""Signup / account errors.

Ported from reference/chatwoot/lib/custom_exceptions/account.rb. We keep the
HTTP shape identical to Chatwoot's render_error_response so parity tests on
error paths don't diverge.
"""

from __future__ import annotations

from typing import Any


class AccountSignupError(Exception):
    """Base class — carries both an HTTP status and a JSON payload."""

    status_code: int = 422
    default_message: str = "Signup failed"

    def __init__(self, message: str | None = None, *, payload: dict[str, Any] | None = None):
        super().__init__(message or self.default_message)
        self.message = message or self.default_message
        self.payload = payload or {}


class InvalidEmail(AccountSignupError):
    status_code = 422
    default_message = "Email is invalid"


class UserExists(AccountSignupError):
    status_code = 422
    default_message = "User already exists with the given email"


class UserErrors(AccountSignupError):
    status_code = 422
    default_message = "User could not be created"


class InvalidParams(AccountSignupError):
    status_code = 422
    default_message = "Invalid params"


class SignupFailed(AccountSignupError):
    status_code = 422
    default_message = "Signup failed"
