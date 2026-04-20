"""Team + TeamMember.

Ported from:
  reference/chatwoot/app/models/team.rb
  reference/chatwoot/app/models/team_member.rb
  reference/chatwoot/db/schema.rb (v4.13.0)

Teams are account-scoped agent groups used for conversation routing. The
``name`` column is lowercased by Chatwoot in a ``before_validation`` hook
so "Support" and "support" collapse to the same row — we mirror that in
the service layer rather than at the ORM level (see
:mod:`app.domains.teams.service`) because SQLModel has no pre-validate
hook equivalent and we want the lowering to be visible in the service
read/write path.

Scope note — ``conversations`` / ``messages`` / ``reporting_events``
helpers from the Rails model aren't ported here: they rely on tables
that land in later phases. Team routing itself is Phase 5.
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, Relationship

from app.core.base_model import TimestampMixin

if TYPE_CHECKING:
    from app.domains.accounts.models import Account
    from app.domains.users.models import User


# =========================================================================
# Team
# =========================================================================
class Team(TimestampMixin, table=True):
    __tablename__ = "teams"
    __table_args__ = (
        Index("index_teams_on_account_id", "account_id"),
        UniqueConstraint(
            "name", "account_id", name="index_teams_on_name_and_account_id"
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    allow_auto_assign: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=True, server_default="true"),
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # Relationships
    account: "Account" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})
    team_members: list["TeamMember"] = Relationship(
        back_populates="team",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
        },
    )


# =========================================================================
# TeamMember
# =========================================================================
class TeamMember(TimestampMixin, table=True):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint(
            "team_id", "user_id", name="index_team_members_on_team_id_and_user_id"
        ),
        Index("index_team_members_on_team_id", "team_id"),
        Index("index_team_members_on_user_id", "user_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    team_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("teams.id", ondelete="CASCADE"),
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

    # Relationships
    team: "Team" = Relationship(
        back_populates="team_members",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    user: "User" = Relationship(sa_relationship_kwargs={"lazy": "selectin"})


__all__ = ["Team", "TeamMember"]
