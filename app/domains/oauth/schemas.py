"""Pydantic schemas for the OAuth apps and consent endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OAuthAppCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    redirect_uris: list[str] = Field(default_factory=list)
    # A confidential app has a server that keeps its secret; a public one
    # (desktop, mobile, script) has no secret and uses PKCE.
    confidential: bool = True


class OAuthAppUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    redirect_uris: list[str] | None = None


class OAuthConsentIn(BaseModel):
    """The authorization request's parameters as the app sent them, plus
    the user's answer."""

    model_config = ConfigDict(extra="ignore")

    response_type: str | None = None
    client_id: str | None = None
    redirect_uri: str | None = None
    scope: str | None = None
    state: str | None = None
    code_challenge: str | None = None
    code_challenge_method: str | None = None
    account_id: int | None = None
    approve: bool = False
