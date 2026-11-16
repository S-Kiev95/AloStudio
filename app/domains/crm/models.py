"""Sales pipeline (F11): pipelines, their stages, and opportunities.

Modelled after Krayin's leads (``lead_pipelines``, ``lead_pipeline_stages``,
``leads``), written for AloStudio rather than ported: an opportunity is a
possible sale to a contact, moving through the stages of a pipeline until it
is won or lost.

Stages carry a ``kind``: ``open`` while the deal is alive, ``won`` / ``lost``
when it closes. Moving an opportunity into a closing stage stamps
``closed_at``; moving it back out clears it.

Default stages are seeded with a ``code`` and no ``name``: the dashboard
shows them in the reader's language. A stage someone renames gets a
``name`` and shows it as typed.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin

STAGE_OPEN = "open"
STAGE_WON = "won"
STAGE_LOST = "lost"
STAGE_KINDS = (STAGE_OPEN, STAGE_WON, STAGE_LOST)


class CrmPipeline(TimestampMixin, table=True):
    """A sales pipeline: an ordered set of stages."""

    __tablename__ = "crm_pipelines"
    __table_args__ = (Index("index_crm_pipelines_on_account_id", "account_id"),)

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    # Null on the seeded pipeline: the dashboard names it in each language.
    name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    is_default: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )
    # An open opportunity untouched for this many days is flagged as stale.
    rotten_days: int = Field(
        default=30, sa_column=Column(Integer, nullable=False, server_default="30")
    )


class CrmStage(TimestampMixin, table=True):
    """One stage of a pipeline."""

    __tablename__ = "crm_stages"
    __table_args__ = (Index("index_crm_stages_on_pipeline_id", "pipeline_id"),)

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    pipeline_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("crm_pipelines.id", ondelete="CASCADE"), nullable=False
        )
    )
    # ``new`` / ``qualified`` / ``proposal`` / ``negotiation`` / ``won`` /
    # ``lost`` on the seeded stages; null on the ones people add.
    code: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))
    name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    kind: str = Field(
        default=STAGE_OPEN,
        sa_column=Column(String(8), nullable=False, server_default=STAGE_OPEN),
    )
    probability: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )
    position: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default="0")
    )


class CrmOpportunity(TimestampMixin, table=True):
    """A possible sale moving through a pipeline."""

    __tablename__ = "crm_opportunities"
    __table_args__ = (
        Index("index_crm_opportunities_on_account_id", "account_id"),
        Index("index_crm_opportunities_on_stage_id", "stage_id"),
        Index("index_crm_opportunities_on_contact_id", "contact_id"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    pipeline_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("crm_pipelines.id", ondelete="CASCADE"), nullable=False
        )
    )
    stage_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("crm_stages.id", ondelete="CASCADE"), nullable=False
        )
    )
    title: str = Field(sa_column=Column(String, nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    value: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(14, 2), nullable=True)
    )
    currency: str | None = Field(default=None, sa_column=Column(String(8), nullable=True))
    contact_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
        ),
    )
    product_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("products.id", ondelete="SET NULL"), nullable=True
        ),
    )
    # Who works it.
    owner_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
    )
    # The conversation it came from, when it was opened from the inbox.
    conversation_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
        ),
    )
    expected_close_on: date | None = Field(
        default=None, sa_column=Column(Date, nullable=True)
    )
    closed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    lost_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    # Order inside its stage's column on the board (lower first).
    position: float = Field(
        default=0.0, sa_column=Column(Float, nullable=False, server_default="0")
    )
    # Last time it moved stage or was edited: drives the "stale" flag.
    stage_changed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


ACTIVITY_KINDS = ("task", "call", "meeting", "email")


class CrmActivity(TimestampMixin, table=True):
    """Something to do (or done) with a contact or an opportunity: a task,
    a call, a meeting, an email. Krayin's ``activities``, trimmed to what
    the team uses. When ``due_at`` passes and it isn't done, its owner gets
    one notification (``reminded_at`` records it; changing the due date
    re-arms it)."""

    __tablename__ = "crm_activities"
    __table_args__ = (
        Index("index_crm_activities_on_account_id", "account_id"),
        Index("index_crm_activities_on_owner_id", "owner_id"),
        Index("index_crm_activities_on_contact_id", "contact_id"),
        Index("index_crm_activities_on_opportunity_id", "opportunity_id"),
        Index("index_crm_activities_pending_due", "due_at", "done_at", "reminded_at"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    kind: str = Field(
        default="task", sa_column=Column(String(16), nullable=False, server_default="task")
    )
    title: str = Field(sa_column=Column(String, nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    due_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    done_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    owner_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
    )
    created_by_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
    )
    contact_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
        ),
    )
    opportunity_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("crm_opportunities.id", ondelete="SET NULL"), nullable=True
        ),
    )
    reminded_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


class CrmCompany(TimestampMixin, table=True):
    """An organization the account sells to; its people are contacts whose
    ``contacts.company_id`` points here (Krayin's ``organizations``). That
    column predates this table and carries no foreign key, so deleting a
    company clears it by hand (``companies.delete_company``)."""

    __tablename__ = "crm_companies"
    __table_args__ = (Index("index_crm_companies_on_account_id", "account_id"),)

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    website: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    email: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    phone: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    address: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    tax_id: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


__all__ = [
    "ACTIVITY_KINDS",
    "STAGE_KINDS",
    "STAGE_LOST",
    "STAGE_OPEN",
    "STAGE_WON",
    "CrmActivity",
    "CrmCompany",
    "CrmOpportunity",
    "CrmPipeline",
    "CrmStage",
]
