"""OAuth 2.0 apps: AloStudio as an authorization server.

An account registers an :class:`OAuthApplication` (its integration, a
connector…). Any user can authorize it on one of their accounts: the
consent issues a short-lived :class:`OAuthAuthorizationCode`, which the app
exchanges for an :class:`OAuthToken` (an access token for the MCP server
plus a rotating refresh token).

Secrets, codes and tokens are stored as SHA-256 hashes: the database alone
never lets anyone act as the app or the user.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.base_model import TimestampMixin

OAUTH_SCOPE_READ = "read"
OAUTH_SCOPE_WRITE = "write"
OAUTH_SCOPES: tuple[str, ...] = (OAUTH_SCOPE_READ, OAUTH_SCOPE_WRITE)


class OAuthApplication(TimestampMixin, table=True):
    """A registered client. Public apps (desktop, mobile, scripts) have no
    secret and must use PKCE."""

    __tablename__ = "oauth_applications"
    __table_args__ = (
        UniqueConstraint("client_id", name="uniq_oauth_applications_client_id"),
        Index("ix_oauth_applications_account_id", "account_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    created_by_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    client_id: str = Field(sa_column=Column(String, nullable=False))
    client_secret_hash: str | None = Field(
        default=None, sa_column=Column(String, nullable=True)
    )
    redirect_uris: list[str] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False)
    )


class OAuthAuthorizationCode(TimestampMixin, table=True):
    """What the consent hands the app: single use, minutes long, bound to
    the redirect URI and (with PKCE) to the app's code challenge."""

    __tablename__ = "oauth_authorization_codes"
    __table_args__ = (
        UniqueConstraint("code_hash", name="uniq_oauth_authorization_codes_code_hash"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    application_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("oauth_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    user_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    code_hash: str = Field(sa_column=Column(String, nullable=False))
    redirect_uri: str = Field(sa_column=Column(String, nullable=False))
    scope: str = Field(sa_column=Column(String, nullable=False))
    code_challenge: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    used_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class OAuthToken(TimestampMixin, table=True):
    """An access token and its refresh token. A refresh issues a new row and
    revokes this one; presenting a revoked refresh token revokes them all
    (it means someone replayed a stolen one)."""

    __tablename__ = "oauth_tokens"
    __table_args__ = (
        UniqueConstraint("access_token_hash", name="uniq_oauth_tokens_access_token_hash"),
        UniqueConstraint("refresh_token_hash", name="uniq_oauth_tokens_refresh_token_hash"),
        Index("ix_oauth_tokens_grant", "application_id", "account_id", "user_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    application_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("oauth_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    user_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    scope: str = Field(sa_column=Column(String, nullable=False))
    access_token_hash: str = Field(sa_column=Column(String, nullable=False))
    access_expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    refresh_token_hash: str = Field(sa_column=Column(String, nullable=False))
    refresh_expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    revoked_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_used_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
