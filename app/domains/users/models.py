"""User + AccountUser + AccessToken.

Ported from:
  reference/chatwoot/app/models/user.rb
  reference/chatwoot/app/models/account_user.rb
  reference/chatwoot/app/models/access_token.rb
  reference/chatwoot/db/schema.rb (v4.13.0)

Notable omissions (deferred — will not break parity on Phase 1 endpoints):
  * OTP/2FA columns (otp_secret, otp_backup_codes, otp_required_for_login,
    consumed_timestep) — present in schema to keep future migrations aligned
    but not wired to any service.
  * Devise omniauth providers (:google_oauth2, :saml) — `provider` column
    remains but only the "email" value is exercised.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship

from app.core.base_model import TimestampMixin

if TYPE_CHECKING:
    from app.domains.accounts.models import Account


# ------------------------------------------------------------------ constants
USER_AVAILABILITY_ONLINE = 0
USER_AVAILABILITY_OFFLINE = 1
USER_AVAILABILITY_BUSY = 2

ACCOUNT_USER_ROLE_AGENT = 0
ACCOUNT_USER_ROLE_ADMINISTRATOR = 1
_ROLE_INT_TO_STR: dict[int, str] = {
    ACCOUNT_USER_ROLE_AGENT: "agent",
    ACCOUNT_USER_ROLE_ADMINISTRATOR: "administrator",
}
_ROLE_STR_TO_INT: dict[str, int] = {v: k for k, v in _ROLE_INT_TO_STR.items()}

_AVAIL_INT_TO_STR: dict[int, str] = {
    USER_AVAILABILITY_ONLINE: "online",
    USER_AVAILABILITY_OFFLINE: "offline",
    USER_AVAILABILITY_BUSY: "busy",
}


# -------------------------------------------------------------------- User
class User(TimestampMixin, table=True):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("uid", "provider", name="index_users_on_uid_and_provider"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )

    # Devise — identity
    provider: str = Field(
        default="email",
        sa_column=Column(String, nullable=False, server_default="email"),
    )
    uid: str = Field(
        default="", sa_column=Column(String, nullable=False, server_default="")
    )
    email: str | None = Field(default=None, sa_column=Column(String, nullable=True, index=True))

    # Devise — authentication
    encrypted_password: str = Field(
        default="", sa_column=Column(String, nullable=False, server_default="")
    )
    reset_password_token: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True, unique=True),
    )
    reset_password_sent_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=False), nullable=True)
    )
    remember_created_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=False), nullable=True)
    )

    # Devise — trackable
    sign_in_count: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    current_sign_in_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=False), nullable=True)
    )
    last_sign_in_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=False), nullable=True)
    )
    current_sign_in_ip: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    last_sign_in_ip: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    # Devise — confirmable
    confirmation_token: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    confirmed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=False), nullable=True)
    )
    confirmation_sent_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=False), nullable=True)
    )
    unconfirmed_email: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    # Profile
    name: str = Field(sa_column=Column(String, nullable=False))
    display_name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    message_signature: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # devise-token-auth persistent session tokens (JSON blob keyed by client id).
    # For Phase 1 we keep the column for schema parity but don't serialise into
    # it — JWT is the source of truth; the column remains '{}' unless legacy
    # data is imported.
    tokens: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=True)
    )

    # Chatwoot-specific
    pubsub_token: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True, unique=True),
    )
    availability: int = Field(
        default=USER_AVAILABILITY_ONLINE,
        sa_column=Column(Integer, nullable=True, server_default="0"),
    )
    ui_settings: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB, nullable=True, server_default="{}")
    )
    custom_attributes: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB, nullable=True, server_default="{}")
    )

    # STI discriminator (`AgentBot`, `SuperAdmin`). Plain String for now.
    type: str | None = Field(default=None, sa_column=Column(String, nullable=True))

    # ---------- DEFERRED (Phase 1.x / later): OTP/2FA -------------------
    otp_secret: str | None = Field(
        default=None, sa_column=Column(String, nullable=True, unique=True)
    )
    consumed_timestep: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    otp_required_for_login: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=True, server_default="false", index=True),
    )
    otp_backup_codes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # Relationships
    account_users: list["AccountUser"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
            "foreign_keys": "AccountUser.user_id",
        },
    )
    access_token: Optional["AccessToken"] = Relationship(
        back_populates="owner_user",
        sa_relationship_kwargs={
            "primaryjoin": (
                "and_(User.id==foreign(AccessToken.owner_id),"
                " AccessToken.owner_type=='User')"
            ),
            "uselist": False,
            "lazy": "selectin",
            "viewonly": False,
            "overlaps": "access_token",
        },
    )

    # ---- helpers (not persisted) ----
    @property
    def confirmed(self) -> bool:
        return self.confirmed_at is not None

    @property
    def available_name(self) -> str:
        return self.display_name or self.name

    @property
    def availability_status(self) -> str:
        return _AVAIL_INT_TO_STR.get(self.availability, "offline")


# --------------------------------------------------------------- AccountUser
class AccountUser(TimestampMixin, table=True):
    __tablename__ = "account_users"
    __table_args__ = (
        UniqueConstraint("account_id", "user_id", name="uniq_user_id_per_account_id"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True, index=True
        ),
    )
    user_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
        ),
    )
    role: int = Field(
        default=ACCOUNT_USER_ROLE_AGENT,
        sa_column=Column(Integer, nullable=True, server_default="0"),
    )
    inviter_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
    )
    active_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=False), nullable=True)
    )
    availability: int = Field(
        default=USER_AVAILABILITY_ONLINE,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    auto_offline: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )
    # custom_role_id / agent_capacity_policy_id FKs deferred to Phase 9;
    # keeping the column so the schema matches for future data migration.
    custom_role_id: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True, index=True))
    agent_capacity_policy_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True, index=True)
    )

    # Relationships
    account: "Account" = Relationship(
        back_populates="account_users",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    user: "User" = Relationship(
        back_populates="account_users",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "foreign_keys": "AccountUser.user_id",
        },
    )

    # Helpers
    @property
    def role_name(self) -> str:
        return _ROLE_INT_TO_STR.get(self.role, "agent")

    @property
    def availability_status(self) -> str:
        return _AVAIL_INT_TO_STR.get(self.availability, "offline")

    @property
    def permissions(self) -> list[str]:
        return ["administrator"] if self.role == ACCOUNT_USER_ROLE_ADMINISTRATOR else ["agent"]


def role_name_to_int(role: str) -> int:
    try:
        return _ROLE_STR_TO_INT[role]
    except KeyError as e:
        raise ValueError(f"unknown role: {role!r}") from e


# ---------------------------------------------------------------- AccessToken
class AccessToken(TimestampMixin, table=True):
    """Polymorphic long-lived API token (Chatwoot's `AccessToken` model).

    In Chatwoot it is created after a User (or AgentBot) is created via the
    `AccessTokenable` concern. We replicate that from `users.service.create_user`.
    """

    __tablename__ = "access_tokens"

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    owner_type: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    owner_id: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    token: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True, unique=True, index=True),
    )

    # Back-ref for User (polymorphic join)
    owner_user: Optional["User"] = Relationship(
        back_populates="access_token",
        sa_relationship_kwargs={
            "primaryjoin": (
                "and_(User.id==foreign(AccessToken.owner_id),"
                " AccessToken.owner_type=='User')"
            ),
            "uselist": False,
            "viewonly": False,
            "overlaps": "access_token",
        },
    )
