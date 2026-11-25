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
    UniqueConstraint,
)
from sqlmodel import Field

from app.core.base_model import TimestampMixin

STAGE_OPEN = "open"
STAGE_WON = "won"
STAGE_LOST = "lost"
STAGE_KINDS = (STAGE_OPEN, STAGE_WON, STAGE_LOST)

PAYMENT_TERM_CASH = "cash"
PAYMENT_TERM_CREDIT = "credit"
PAYMENT_TERM_INSTALLMENTS = "installments"
PAYMENT_TERMS = (PAYMENT_TERM_CASH, PAYMENT_TERM_CREDIT, PAYMENT_TERM_INSTALLMENTS)

PAYMENT_METHOD_CASH = "cash"
PAYMENT_METHOD_TRANSFER = "transfer"
PAYMENT_METHOD_CARD = "card"
PAYMENT_METHOD_OTHER = "other"
PAYMENT_METHODS = (
    PAYMENT_METHOD_CASH,
    PAYMENT_METHOD_TRANSFER,
    PAYMENT_METHOD_CARD,
    PAYMENT_METHOD_OTHER,
)


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
    # Billing terms once won: cash | credit | installments (null while not won / unset).
    payment_terms: str | None = Field(default=None, sa_column=Column(String(16), nullable=True))
    # Due date for credit ("fiado") sales.
    due_on: date | None = Field(default=None, sa_column=Column(Date, nullable=True))


class CrmInstallment(TimestampMixin, table=True):
    """One installment of a won opportunity billed in parts."""

    __tablename__ = "crm_installments"
    __table_args__ = (
        UniqueConstraint(
            "opportunity_id", "number", name="uq_crm_installments_opportunity_number"
        ),
        Index("index_crm_installments_on_account_id", "account_id"),
        Index("index_crm_installments_on_opportunity_id", "opportunity_id"),
        Index("index_crm_installments_on_account_due_on", "account_id", "due_on"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    opportunity_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("crm_opportunities.id", ondelete="CASCADE"), nullable=False
        )
    )
    number: int = Field(sa_column=Column(Integer, nullable=False))
    due_on: date = Field(sa_column=Column(Date, nullable=False))
    amount: Decimal = Field(sa_column=Column(Numeric(14, 2), nullable=False))


class CrmPayment(TimestampMixin, table=True):
    """A payment made by a client (contact), allocatable across one or more sales."""

    __tablename__ = "crm_payments"
    __table_args__ = (
        Index("index_crm_payments_on_account_id", "account_id"),
        Index("index_crm_payments_on_account_contact", "account_id", "contact_id"),
        Index("index_crm_payments_on_account_paid_on", "account_id", "paid_on"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    contact_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
        )
    )
    amount: Decimal = Field(sa_column=Column(Numeric(14, 2), nullable=False))
    currency: str | None = Field(default=None, sa_column=Column(String(8), nullable=True))
    paid_on: date = Field(sa_column=Column(Date, nullable=False))
    method: str = Field(
        default=PAYMENT_METHOD_CASH,
        sa_column=Column(String(16), nullable=False, server_default=PAYMENT_METHOD_CASH),
    )
    note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_by_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
    )


class CrmPaymentAllocation(TimestampMixin, table=True):
    """Portion of a client payment applied to a won opportunity (and optionally an installment)."""

    __tablename__ = "crm_payment_allocations"
    __table_args__ = (
        Index("index_crm_payment_allocations_on_account_id", "account_id"),
        Index("index_crm_payment_allocations_on_payment_id", "payment_id"),
        Index("index_crm_payment_allocations_on_opportunity_id", "opportunity_id"),
        Index("index_crm_payment_allocations_on_installment_id", "installment_id"),
    )

    id: int | None = Field(
        default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True)
    )
    account_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        )
    )
    payment_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("crm_payments.id", ondelete="CASCADE"), nullable=False
        )
    )
    opportunity_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("crm_opportunities.id", ondelete="CASCADE"), nullable=False
        )
    )
    installment_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger, ForeignKey("crm_installments.id", ondelete="SET NULL"), nullable=True
        ),
    )
    amount: Decimal = Field(sa_column=Column(Numeric(14, 2), nullable=False))


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
    "PAYMENT_METHODS",
    "PAYMENT_METHOD_CARD",
    "PAYMENT_METHOD_CASH",
    "PAYMENT_METHOD_OTHER",
    "PAYMENT_METHOD_TRANSFER",
    "PAYMENT_TERMS",
    "PAYMENT_TERM_CASH",
    "PAYMENT_TERM_CREDIT",
    "PAYMENT_TERM_INSTALLMENTS",
    "STAGE_KINDS",
    "STAGE_LOST",
    "STAGE_OPEN",
    "STAGE_WON",
    "CrmActivity",
    "CrmCompany",
    "CrmInstallment",
    "CrmOpportunity",
    "CrmPayment",
    "CrmPaymentAllocation",
    "CrmPipeline",
    "CrmStage",
]
