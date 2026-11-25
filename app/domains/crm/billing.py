"""CRM collections (cobranzas): payment terms, installments, payments,
allocations, contact statements, and accounts receivable.

All monetary calculations use :class:`decimal.Decimal` quantized to two
decimal places. Currencies are never converted: balances and summaries are
always grouped by currency (normalized uppercase, or ``None`` when unset).
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import lazyload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.contacts.models import Contact
from app.domains.conversations.models import Conversation
from app.domains.crm.models import (
    PAYMENT_METHOD_CASH,
    PAYMENT_METHODS,
    PAYMENT_TERM_CASH,
    PAYMENT_TERM_CREDIT,
    PAYMENT_TERM_INSTALLMENTS,
    PAYMENT_TERMS,
    STAGE_WON,
    CrmInstallment,
    CrmOpportunity,
    CrmPayment,
    CrmPaymentAllocation,
    CrmStage,
)
from app.domains.inboxes.models import CHANNEL_TYPE_WHATSAPP, Inbox
from app.domains.users.models import User

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _unprocessable(message: str, *, code: str | None = None) -> ChatwootHTTPException:
    detail: dict[str, Any] = {"message": message}
    if code:
        detail["code"] = code
    return ChatwootHTTPException(status_code=422, detail=detail)


def _conflict(detail: dict[str, Any]) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=409, detail=detail)


def normalize_currency(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().upper()
    return cleaned or None


def to_decimal(value: Any, field: str, *, allow_zero: bool = False) -> Decimal:
    if value is None or isinstance(value, bool):
        raise _unprocessable(f"{field} is invalid")
    try:
        dec = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise _unprocessable(f"{field} is invalid") from exc
    if not dec.is_finite():
        raise _unprocessable(f"{field} is invalid")
    dec = dec.quantize(CENT, rounding=ROUND_HALF_UP)
    if allow_zero:
        if dec < ZERO:
            raise _unprocessable(f"{field} must be >= 0")
    else:
        if dec <= ZERO:
            raise _unprocessable(f"{field} must be > 0")
    return dec


def parse_date(value: Any, field: str, *, required: bool = False) -> date | None:
    if value in (None, ""):
        if required:
            raise _unprocessable(f"{field} is required")
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise _unprocessable(f"{field} is invalid") from exc


def _add_months(start: date, months: int) -> date:
    total = (start.year * 12 + (start.month - 1)) + months
    year = total // 12
    month = (total % 12) + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def build_installment_schedule(
    total: Decimal,
    *,
    count: int,
    first_due_on: date,
    frequency: str = "monthly",
    interval_days: int | None = None,
) -> list[tuple[int, date, Decimal]]:
    """Split ``total`` into ``count`` installments; the last absorbs rounding cents."""
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 120:
        raise _unprocessable("count must be between 1 and 120")
    total = total.quantize(CENT, rounding=ROUND_HALF_UP)
    if total <= ZERO:
        raise _unprocessable("value must be greater than 0 to generate installments")
    if frequency not in ("monthly", "every_n_days"):
        raise _unprocessable("frequency must be 'monthly' or 'every_n_days'")
    if frequency == "every_n_days":
        if (
            not isinstance(interval_days, int)
            or isinstance(interval_days, bool)
            or not 1 <= interval_days <= 365
        ):
            raise _unprocessable("interval_days must be between 1 and 365")

    base = (total / Decimal(count)).quantize(CENT, rounding=ROUND_DOWN)
    if base < CENT:
        raise _unprocessable(
            "value is too small to split into that many installments",
            code="installment_amount_too_small",
        )
    last_amount = (total - base * (count - 1)).quantize(CENT, rounding=ROUND_HALF_UP)

    schedule: list[tuple[int, date, Decimal]] = []
    for idx in range(count):
        if frequency == "monthly":
            due = _add_months(first_due_on, idx)
        else:
            assert interval_days is not None
            due = first_due_on + timedelta(days=interval_days * idx)
        amt = last_amount if idx == count - 1 else base
        schedule.append((idx + 1, due, amt))
    return schedule


# ---------------------------------------------------------------------------
# Pure billing computations (Decimal)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class InstallmentSummary:
    installment: CrmInstallment
    paid_amount: Decimal
    direct_paid_amount: Decimal
    remaining_amount: Decimal
    days_overdue: int
    status: str  # paid | partial | pending | overdue


@dataclass(frozen=True)
class OpportunityBillingSummary:
    opportunity: CrmOpportunity
    is_won: bool
    value: Decimal
    paid_amount: Decimal
    owed_amount: Decimal
    overdue_amount: Decimal
    days_overdue: int
    next_due_on: date | None
    installments: list[InstallmentSummary]


def compute_opportunity_billing(
    opp: CrmOpportunity,
    *,
    is_won: bool,
    installments: Sequence[CrmInstallment],
    allocations: Sequence[CrmPaymentAllocation],
    as_of: date,
) -> OpportunityBillingSummary:
    value = (
        Decimal(opp.value).quantize(CENT, rounding=ROUND_HALF_UP) if opp.value is not None else ZERO
    )
    paid_amount = sum((Decimal(a.amount) for a in allocations), ZERO).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    owed_amount = max(ZERO, value - paid_amount) if is_won else ZERO

    sorted_insts = sorted(installments, key=lambda i: (i.number, i.id or 0))
    direct_by_inst: dict[int, Decimal] = defaultdict(lambda: ZERO)
    unlinked_paid = ZERO
    for alloc in allocations:
        amt = Decimal(alloc.amount)
        if alloc.installment_id is not None:
            direct_by_inst[alloc.installment_id] += amt
        else:
            unlinked_paid += amt

    inst_summaries: list[InstallmentSummary] = []
    if sorted_insts:
        carry = unlinked_paid
        overdue_amount = ZERO
        max_days_overdue = 0
        next_due: date | None = None
        for inst in sorted_insts:
            inst_amt = Decimal(inst.amount).quantize(CENT, rounding=ROUND_HALF_UP)
            direct = direct_by_inst.get(inst.id or -1, ZERO).quantize(CENT, rounding=ROUND_HALF_UP)
            extra = min(max(ZERO, inst_amt - direct), carry)
            carry -= extra
            eff_paid = (direct + extra).quantize(CENT, rounding=ROUND_HALF_UP)
            remaining = max(ZERO, inst_amt - eff_paid)
            is_overdue = is_won and remaining > ZERO and inst.due_on < as_of
            days_ov = (as_of - inst.due_on).days if is_overdue else 0
            if remaining == ZERO:
                status = "paid"
            elif is_overdue:
                status = "overdue"
            elif eff_paid > ZERO:
                status = "partial"
            else:
                status = "pending"
            if is_overdue:
                overdue_amount += remaining
                if days_ov > max_days_overdue:
                    max_days_overdue = days_ov
            if is_won and remaining > ZERO and (next_due is None or inst.due_on < next_due):
                next_due = inst.due_on
            inst_summaries.append(
                InstallmentSummary(
                    installment=inst,
                    paid_amount=eff_paid,
                    direct_paid_amount=direct,
                    remaining_amount=remaining,
                    days_overdue=days_ov,
                    status=status,
                )
            )
        return OpportunityBillingSummary(
            opportunity=opp,
            is_won=is_won,
            value=value,
            paid_amount=paid_amount,
            owed_amount=owed_amount,
            overdue_amount=overdue_amount.quantize(CENT, rounding=ROUND_HALF_UP),
            days_overdue=max_days_overdue,
            next_due_on=next_due,
            installments=inst_summaries,
        )

    # No installments: check credit sale due date.
    overdue_amount = ZERO
    days_overdue = 0
    next_due = None
    if is_won and owed_amount > ZERO:
        if opp.payment_terms == PAYMENT_TERM_CREDIT and opp.due_on is not None:
            next_due = opp.due_on
            if opp.due_on < as_of:
                overdue_amount = owed_amount
                days_overdue = (as_of - opp.due_on).days
        elif opp.due_on is not None:
            next_due = opp.due_on

    return OpportunityBillingSummary(
        opportunity=opp,
        is_won=is_won,
        value=value,
        paid_amount=paid_amount,
        owed_amount=owed_amount,
        overdue_amount=overdue_amount,
        days_overdue=days_overdue,
        next_due_on=next_due,
        installments=[],
    )


# ---------------------------------------------------------------------------
# Batch loaders (no N+1)
# ---------------------------------------------------------------------------
async def _stages_by_id(session: AsyncSession, stage_ids: set[int]) -> dict[int, CrmStage]:
    if not stage_ids:
        return {}
    rows = (
        await session.exec(
            select(CrmStage).where(col(CrmStage.id).in_(stage_ids)).options(lazyload("*"))
        )
    ).all()
    return {r.id: r for r in rows if r.id is not None}


async def _installments_by_opp(
    session: AsyncSession, opp_ids: Sequence[int]
) -> dict[int, list[CrmInstallment]]:
    if not opp_ids:
        return {}
    rows = (
        await session.exec(
            select(CrmInstallment)
            .where(col(CrmInstallment.opportunity_id).in_(opp_ids))
            .order_by(col(CrmInstallment.opportunity_id), col(CrmInstallment.number))
        )
    ).all()
    out: dict[int, list[CrmInstallment]] = defaultdict(list)
    for r in rows:
        out[r.opportunity_id].append(r)
    return out


async def _allocations_by_opp(
    session: AsyncSession, opp_ids: Sequence[int], *, exclude_payment_id: int | None = None
) -> dict[int, list[CrmPaymentAllocation]]:
    if not opp_ids:
        return {}
    stmt = select(CrmPaymentAllocation).where(col(CrmPaymentAllocation.opportunity_id).in_(opp_ids))
    if exclude_payment_id is not None:
        stmt = stmt.where(CrmPaymentAllocation.payment_id != exclude_payment_id)
    rows = (await session.exec(stmt)).all()
    out: dict[int, list[CrmPaymentAllocation]] = defaultdict(list)
    for r in rows:
        out[r.opportunity_id].append(r)
    return out


async def _allocations_by_payment(
    session: AsyncSession, payment_ids: Sequence[int]
) -> dict[int, list[CrmPaymentAllocation]]:
    if not payment_ids:
        return {}
    rows = (
        await session.exec(
            select(CrmPaymentAllocation)
            .where(col(CrmPaymentAllocation.payment_id).in_(payment_ids))
            .order_by(col(CrmPaymentAllocation.id))
        )
    ).all()
    out: dict[int, list[CrmPaymentAllocation]] = defaultdict(list)
    for r in rows:
        out[r.payment_id].append(r)
    return out


async def summarize_opportunities(
    session: AsyncSession,
    rows: Sequence[CrmOpportunity],
    *,
    as_of: date | None = None,
) -> dict[int, OpportunityBillingSummary]:
    """Batch-compute billing summaries for a sequence of opportunities."""
    if not rows:
        return {}
    today = as_of or date.today()
    opp_ids = [r.id for r in rows if r.id is not None]
    stages = await _stages_by_id(session, {r.stage_id for r in rows})
    insts = await _installments_by_opp(session, opp_ids)
    allocs = await _allocations_by_opp(session, opp_ids)
    out: dict[int, OpportunityBillingSummary] = {}
    for opp in rows:
        assert opp.id is not None
        st = stages.get(opp.stage_id)
        is_won = st is not None and st.kind == STAGE_WON
        out[opp.id] = compute_opportunity_billing(
            opp,
            is_won=is_won,
            installments=insts.get(opp.id, []),
            allocations=allocs.get(opp.id, []),
            as_of=today,
        )
    return out


async def whatsapp_conversations_for_contacts(
    session: AsyncSession, *, account_id: int, contact_ids: Sequence[int]
) -> dict[int, dict[str, Any]]:
    """Return the latest WhatsApp conversation metadata per contact_id."""
    if not contact_ids:
        return {}
    rows = (
        await session.exec(
            select(Conversation.contact_id, Conversation.display_id, Conversation.inbox_id)
            .join(Inbox, col(Inbox.id) == Conversation.inbox_id)
            .where(
                Conversation.account_id == account_id,
                col(Conversation.contact_id).in_(contact_ids),
                Inbox.channel_type == CHANNEL_TYPE_WHATSAPP,
            )
            .order_by(
                col(Conversation.last_activity_at).desc().nullslast(),
                col(Conversation.id).desc(),
            )
        )
    ).all()
    out: dict[int, dict[str, Any]] = {}
    for contact_id, display_id, inbox_id in rows:
        if contact_id is not None and contact_id not in out:
            out[contact_id] = {
                "display_id": display_id,
                "inbox_id": inbox_id,
            }
    return out


# ---------------------------------------------------------------------------
# Guards on opportunity edits / deletes when payments are allocated
# ---------------------------------------------------------------------------
async def _opportunity_allocations(
    session: AsyncSession, opportunity_id: int
) -> list[CrmPaymentAllocation]:
    return list(
        (
            await session.exec(
                select(CrmPaymentAllocation).where(
                    CrmPaymentAllocation.opportunity_id == opportunity_id
                )
            )
        ).all()
    )


async def _delete_opportunity_installments(session: AsyncSession, opportunity_id: int) -> None:
    insts = (
        await session.exec(
            select(CrmInstallment).where(CrmInstallment.opportunity_id == opportunity_id)
        )
    ).all()
    for inst in insts:
        await session.delete(inst)


async def guard_opportunity_change(
    session: AsyncSession,
    *,
    opportunity: CrmOpportunity,
    old_stage: CrmStage,
    new_stage: CrmStage,
    new_value: Decimal | None,
    value_changed: bool,
    new_currency: str | None,
    currency_changed: bool,
    new_contact_id: int | None,
    contact_changed: bool,
    release_allocations: bool = False,
    keep_allocations: bool = False,
) -> None:
    """Protect allocated payments when a won sale is reopened, lost, or repriced.

    Never drops allocations silently: raises HTTP 409 asking the caller to
    decide (typically leaving the payments as client credit balance via
    ``release_allocations=True``).
    """
    assert opportunity.id is not None
    leaving_won = old_stage.kind == STAGE_WON and new_stage.kind != STAGE_WON
    allocs = await _opportunity_allocations(session, opportunity.id)
    allocated_total = sum((Decimal(a.amount) for a in allocs), ZERO).quantize(
        CENT, rounding=ROUND_HALF_UP
    )

    if allocated_total == ZERO:
        if leaving_won:
            opportunity.payment_terms = None
            opportunity.due_on = None
            await _delete_opportunity_installments(session, opportunity.id)
        elif value_changed and opportunity.payment_terms == PAYMENT_TERM_INSTALLMENTS:
            # Clear stale installments that no longer match the new value.
            await _delete_opportunity_installments(session, opportunity.id)
            opportunity.payment_terms = None
        return

    reason: str | None = None
    if leaving_won:
        reason = "stage_change"
    elif contact_changed and new_contact_id != opportunity.contact_id:
        reason = "contact_change"
    elif currency_changed and normalize_currency(new_currency) != normalize_currency(
        opportunity.currency
    ):
        reason = "currency_change"
    elif value_changed:
        reason = "value_change"

    if reason is None:
        return

    existing_insts = (
        await session.exec(
            select(CrmInstallment.id).where(CrmInstallment.opportunity_id == opportunity.id)
        )
    ).first()
    has_installments = existing_insts is not None
    can_keep = (
        reason == "value_change"
        and not leaving_won
        and not contact_changed
        and not currency_changed
        and new_value is not None
        and new_value >= allocated_total
        and not has_installments
    )

    if release_allocations:
        for a in allocs:
            await session.delete(a)
        await session.flush()
        if leaving_won:
            opportunity.payment_terms = None
            opportunity.due_on = None
            await _delete_opportunity_installments(session, opportunity.id)
        elif value_changed and has_installments:
            await _delete_opportunity_installments(session, opportunity.id)
            opportunity.payment_terms = None
        return

    if keep_allocations and can_keep:
        return

    raise _conflict(
        {
            "code": "opportunity_has_payments",
            "message": (
                "Esta venta tiene pagos imputados. Confirmá si querés dejar esos pagos "
                "como saldo a favor del cliente."
            ),
            "reason": reason,
            "allocated_amount": float(allocated_total),
            "currency": opportunity.currency,
            "allocations_count": len(allocs),
            "can_keep": can_keep,
        }
    )


async def guard_opportunity_delete(
    session: AsyncSession,
    *,
    opportunity: CrmOpportunity,
    release_allocations: bool = False,
) -> None:
    """Prevent silent deletion of allocations when deleting a paid opportunity."""
    assert opportunity.id is not None
    allocs = await _opportunity_allocations(session, opportunity.id)
    if not allocs:
        return
    allocated_total = sum((Decimal(a.amount) for a in allocs), ZERO).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    if not release_allocations:
        raise _conflict(
            {
                "code": "opportunity_has_payments",
                "message": (
                    "Esta venta tiene pagos imputados. Confirmá si querés liberar esos pagos "
                    "como saldo a favor del cliente antes de eliminarla."
                ),
                "reason": "delete",
                "allocated_amount": float(allocated_total),
                "currency": opportunity.currency,
                "allocations_count": len(allocs),
                "can_keep": False,
            }
        )
    for a in allocs:
        await session.delete(a)
    await session.flush()


# ---------------------------------------------------------------------------
# Opportunity billing & installments endpoints logic
# ---------------------------------------------------------------------------
async def get_opportunity_billing(
    session: AsyncSession,
    *,
    opportunity: CrmOpportunity,
    as_of: date | None = None,
) -> dict[str, Any]:
    assert opportunity.id is not None
    today = as_of or date.today()
    stage = await session.get(CrmStage, opportunity.stage_id)
    is_won = stage is not None and stage.kind == STAGE_WON
    insts = (await _installments_by_opp(session, [opportunity.id])).get(opportunity.id, [])
    allocs = (await _allocations_by_opp(session, [opportunity.id])).get(opportunity.id, [])
    summary = compute_opportunity_billing(
        opportunity,
        is_won=is_won,
        installments=insts,
        allocations=allocs,
        as_of=today,
    )

    payment_ids = {a.payment_id for a in allocs}
    payments_map: dict[int, CrmPayment] = {}
    users_map: dict[int, User] = {}
    if payment_ids:
        p_rows = (
            await session.exec(select(CrmPayment).where(col(CrmPayment.id).in_(payment_ids)))
        ).all()
        payments_map = {p.id: p for p in p_rows if p.id is not None}
        user_ids = {p.created_by_id for p in p_rows if p.created_by_id is not None}
        if user_ids:
            u_rows = (
                await session.exec(
                    select(User).where(col(User.id).in_(user_ids)).options(lazyload("*"))
                )
            ).all()
            users_map = {u.id: u for u in u_rows if u.id is not None}

    inst_number_by_id = {i.id: i.number for i in insts if i.id is not None}
    presented_allocs = []
    for a in sorted(allocs, key=lambda x: x.id or 0):
        pay = payments_map.get(a.payment_id)
        creator = users_map.get(pay.created_by_id) if pay and pay.created_by_id else None
        presented_allocs.append(
            {
                "id": a.id,
                "payment_id": a.payment_id,
                "opportunity_id": a.opportunity_id,
                "installment_id": a.installment_id,
                "installment_number": (
                    inst_number_by_id.get(a.installment_id) if a.installment_id else None
                ),
                "amount": float(Decimal(a.amount).quantize(CENT, rounding=ROUND_HALF_UP)),
                "paid_on": pay.paid_on.isoformat() if pay else None,
                "method": pay.method if pay else None,
                "note": pay.note if pay else None,
                "payment_amount": (
                    float(Decimal(pay.amount).quantize(CENT, rounding=ROUND_HALF_UP))
                    if pay
                    else None
                ),
                "created_by": (
                    {"id": creator.id, "name": creator.display_name or creator.name}
                    if creator
                    else None
                ),
            }
        )

    return {
        "opportunity_id": opportunity.id,
        "is_won": is_won,
        "payment_terms": opportunity.payment_terms,
        "due_on": opportunity.due_on.isoformat() if opportunity.due_on else None,
        "value": float(summary.value) if opportunity.value is not None else None,
        "currency": opportunity.currency,
        "paid_amount": float(summary.paid_amount),
        "owed_amount": float(summary.owed_amount),
        "overdue_amount": float(summary.overdue_amount),
        "days_overdue": summary.days_overdue,
        "next_due_on": summary.next_due_on.isoformat() if summary.next_due_on else None,
        "installments": [
            {
                "id": item.installment.id,
                "number": item.installment.number,
                "due_on": item.installment.due_on.isoformat(),
                "amount": float(
                    Decimal(item.installment.amount).quantize(CENT, rounding=ROUND_HALF_UP)
                ),
                "paid_amount": float(item.paid_amount),
                "remaining_amount": float(item.remaining_amount),
                "days_overdue": item.days_overdue,
                "status": item.status,
                "locked": item.direct_paid_amount > ZERO,
            }
            for item in summary.installments
        ],
        "allocations": presented_allocs,
    }


async def set_opportunity_billing(
    session: AsyncSession,
    *,
    account_id: int,
    opportunity: CrmOpportunity,
    payload: dict[str, Any],
    user_id: int | None,
    as_of: date | None = None,
) -> tuple[dict[str, Any], CrmPayment | None]:
    """Configure payment terms and installments for a won opportunity."""
    assert opportunity.id is not None
    stage = await session.get(CrmStage, opportunity.stage_id)
    if stage is None or stage.kind != STAGE_WON:
        raise _unprocessable(
            "Solo las oportunidades ganadas pueden configurar forma de cobro",
            code="opportunity_not_won",
        )

    terms = payload.get("payment_terms")
    if terms is not None and terms not in PAYMENT_TERMS:
        raise _unprocessable("payment_terms is invalid")

    existing_insts = (await _installments_by_opp(session, [opportunity.id])).get(opportunity.id, [])
    existing_allocs = (await _allocations_by_opp(session, [opportunity.id])).get(opportunity.id, [])
    insts_with_payments = {
        a.installment_id for a in existing_allocs if a.installment_id is not None
    }

    created_payment: CrmPayment | None = None

    if terms is None:
        if insts_with_payments:
            raise _unprocessable(
                "No se puede quitar el plan de cuotas porque ya tiene pagos imputados",
                code="installments_locked",
            )
        for inst in existing_insts:
            await session.delete(inst)
        opportunity.payment_terms = None
        opportunity.due_on = None
        session.add(opportunity)
        await session.flush()
        return await get_opportunity_billing(session, opportunity=opportunity, as_of=as_of), None

    if terms == PAYMENT_TERM_CASH:
        if insts_with_payments:
            raise _unprocessable(
                "No se puede cambiar de cuotas a contado porque hay cuotas con pagos imputados",
                code="installments_locked",
            )
        for inst in existing_insts:
            await session.delete(inst)
        opportunity.payment_terms = PAYMENT_TERM_CASH
        opportunity.due_on = None
        session.add(opportunity)
        await session.flush()

        if payload.get("register_payment"):
            if opportunity.contact_id is None:
                raise _unprocessable(
                    "La venta necesita un contacto para registrar el pago",
                    code="contact_required",
                )
            if opportunity.value is None or Decimal(opportunity.value) <= ZERO:
                raise _unprocessable(
                    "La venta necesita un valor mayor a 0 para registrar el pago",
                    code="value_required",
                )
            paid_so_far = sum((Decimal(a.amount) for a in existing_allocs), ZERO)
            remaining = (Decimal(opportunity.value) - paid_so_far).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
            if remaining <= ZERO:
                raise _unprocessable("La venta ya está completamente pagada", code="already_paid")
            method = payload.get("payment_method") or PAYMENT_METHOD_CASH
            if method not in PAYMENT_METHODS:
                raise _unprocessable("payment_method is invalid")
            paid_on = parse_date(payload.get("paid_on"), "paid_on") or (as_of or date.today())
            note = payload.get("payment_note")
            if isinstance(note, str):
                note = note.strip() or None
            created_payment = CrmPayment(
                account_id=account_id,
                contact_id=opportunity.contact_id,
                amount=remaining,
                currency=normalize_currency(opportunity.currency),
                paid_on=paid_on,
                method=method,
                note=note,
                created_by_id=user_id,
            )
            session.add(created_payment)
            await session.flush()
            assert created_payment.id is not None
            session.add(
                CrmPaymentAllocation(
                    account_id=account_id,
                    payment_id=created_payment.id,
                    opportunity_id=opportunity.id,
                    installment_id=None,
                    amount=remaining,
                )
            )
            await session.flush()

    elif terms == PAYMENT_TERM_CREDIT:
        if insts_with_payments:
            raise _unprocessable(
                "No se puede cambiar de cuotas a fiado porque hay cuotas con pagos imputados",
                code="installments_locked",
            )
        for inst in existing_insts:
            await session.delete(inst)
        opportunity.payment_terms = PAYMENT_TERM_CREDIT
        opportunity.due_on = parse_date(payload.get("due_on"), "due_on")
        session.add(opportunity)
        await session.flush()

    elif terms == PAYMENT_TERM_INSTALLMENTS:
        if opportunity.value is None or Decimal(opportunity.value) <= ZERO:
            raise _unprocessable(
                "La venta necesita un valor mayor a 0 para armar cuotas",
                code="value_required",
            )
        opp_total = Decimal(opportunity.value).quantize(CENT, rounding=ROUND_HALF_UP)

        gen = payload.get("generate")
        manual_items = payload.get("installments")
        if gen is None and manual_items is None:
            if not existing_insts:
                raise _unprocessable(
                    "Indicá cómo generar las cuotas o enviá la lista de cuotas",
                    code="installments_required",
                )
            opportunity.payment_terms = PAYMENT_TERM_INSTALLMENTS
            opportunity.due_on = None
            session.add(opportunity)
            await session.flush()
            return (
                await get_opportunity_billing(session, opportunity=opportunity, as_of=as_of),
                None,
            )

        if insts_with_payments:
            raise _unprocessable(
                "No se pueden modificar cuotas que ya tienen pagos imputados",
                code="installments_locked",
            )

        new_rows: list[tuple[int, date, Decimal]] = []
        if gen is not None:
            first_due = parse_date(gen.get("first_due_on"), "first_due_on", required=True)
            assert first_due is not None
            new_rows = build_installment_schedule(
                opp_total,
                count=gen.get("count"),
                first_due_on=first_due,
                frequency=gen.get("frequency", "monthly"),
                interval_days=gen.get("interval_days"),
            )
        else:
            assert isinstance(manual_items, list)
            if not manual_items:
                raise _unprocessable("installments must be a non-empty list")
            running = ZERO
            for idx, raw in enumerate(manual_items, start=1):
                due = parse_date(raw.get("due_on"), "due_on", required=True)
                assert due is not None
                amt = to_decimal(raw.get("amount"), "amount")
                running += amt
                new_rows.append((idx, due, amt))
            if running.quantize(CENT, rounding=ROUND_HALF_UP) != opp_total:
                raise _unprocessable(
                    "La suma de las cuotas debe coincidir con el valor de la venta",
                    code="installments_sum_mismatch",
                )

        for inst in existing_insts:
            await session.delete(inst)
        await session.flush()

        for number, due, amt in new_rows:
            session.add(
                CrmInstallment(
                    account_id=account_id,
                    opportunity_id=opportunity.id,
                    number=number,
                    due_on=due,
                    amount=amt,
                )
            )
        opportunity.payment_terms = PAYMENT_TERM_INSTALLMENTS
        opportunity.due_on = None
        session.add(opportunity)
        await session.flush()

    return (
        await get_opportunity_billing(session, opportunity=opportunity, as_of=as_of),
        created_payment,
    )


async def update_installment(
    session: AsyncSession,
    *,
    account_id: int,
    opportunity: CrmOpportunity,
    installment_id: int,
    payload: dict[str, Any],
    as_of: date | None = None,
) -> dict[str, Any]:
    """Edit a single installment's due date or amount while it has no payments."""
    assert opportunity.id is not None
    inst = await session.get(CrmInstallment, installment_id)
    if inst is None or inst.account_id != account_id or inst.opportunity_id != opportunity.id:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )

    has_alloc = (
        await session.exec(
            select(CrmPaymentAllocation.id).where(
                CrmPaymentAllocation.installment_id == installment_id
            )
        )
    ).first()
    if has_alloc is not None:
        raise _unprocessable(
            "No se puede editar una cuota que ya tiene pagos imputados",
            code="installments_locked",
        )

    if "due_on" in payload and payload["due_on"] is not None:
        parsed = parse_date(payload["due_on"], "due_on", required=True)
        assert parsed is not None
        inst.due_on = parsed
    if "amount" in payload and payload["amount"] is not None:
        new_amt = to_decimal(payload["amount"], "amount")
        all_insts = (await _installments_by_opp(session, [opportunity.id])).get(opportunity.id, [])
        other_sum = sum((Decimal(i.amount) for i in all_insts if i.id != installment_id), ZERO)
        opp_total = (
            Decimal(opportunity.value).quantize(CENT, rounding=ROUND_HALF_UP)
            if opportunity.value is not None
            else ZERO
        )
        if (other_sum + new_amt).quantize(CENT, rounding=ROUND_HALF_UP) != opp_total:
            raise _unprocessable(
                "La suma de las cuotas debe coincidir con el valor de la venta",
                code="installments_sum_mismatch",
            )
        inst.amount = new_amt

    session.add(inst)
    await session.flush()
    return await get_opportunity_billing(session, opportunity=opportunity, as_of=as_of)


# ---------------------------------------------------------------------------
# Payment allocation planning (auto & manual)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PlannedAllocation:
    opportunity_id: int
    opportunity_title: str
    installment_id: int | None
    installment_number: int | None
    due_on: date | None
    amount: Decimal


async def _contact_won_opportunities_in_currency(
    session: AsyncSession,
    *,
    account_id: int,
    contact_id: int,
    currency: str | None,
) -> list[CrmOpportunity]:
    stmt = (
        select(CrmOpportunity)
        .join(CrmStage, col(CrmStage.id) == CrmOpportunity.stage_id)
        .where(
            CrmOpportunity.account_id == account_id,
            CrmOpportunity.contact_id == contact_id,
            CrmStage.kind == STAGE_WON,
            col(CrmOpportunity.value).is_not(None),
            col(CrmOpportunity.value) > 0,
        )
    )
    rows = list((await session.exec(stmt)).all())
    norm = normalize_currency(currency)
    return [r for r in rows if normalize_currency(r.currency) == norm]


async def _plan_auto_allocations(
    session: AsyncSession,
    *,
    account_id: int,
    contact_id: int,
    currency: str | None,
    amount: Decimal,
    exclude_payment_id: int | None = None,
) -> tuple[list[PlannedAllocation], Decimal]:
    opps = await _contact_won_opportunities_in_currency(
        session, account_id=account_id, contact_id=contact_id, currency=currency
    )
    if not opps:
        return [], amount

    opp_ids = [o.id for o in opps if o.id is not None]
    insts_by_opp = await _installments_by_opp(session, opp_ids)
    allocs_by_opp = await _allocations_by_opp(
        session, opp_ids, exclude_payment_id=exclude_payment_id
    )

    # Buckets sorted oldest due date first (installment or sale due_on), then
    # undated sales oldest closed_at first.
    buckets: list[
        tuple[tuple[int, date, datetime, int, int], CrmOpportunity, CrmInstallment | None, Decimal]
    ] = []
    for opp in opps:
        assert opp.id is not None
        summary = compute_opportunity_billing(
            opp,
            is_won=True,
            installments=insts_by_opp.get(opp.id, []),
            allocations=allocs_by_opp.get(opp.id, []),
            as_of=date.today(),
        )
        if summary.owed_amount <= ZERO:
            continue
        ts = opp.closed_at or opp.created_at or _EPOCH
        if summary.installments:
            for item in summary.installments:
                if item.remaining_amount <= ZERO:
                    continue
                sort_key = (0, item.installment.due_on, ts, opp.id, item.installment.number)
                buckets.append((sort_key, opp, item.installment, item.remaining_amount))
        else:
            has_due = opp.due_on is not None
            sort_key = (0 if has_due else 1, opp.due_on or date.max, ts, opp.id, 0)
            buckets.append((sort_key, opp, None, summary.owed_amount))

    buckets.sort(key=lambda b: b[0])

    left = amount
    planned: list[PlannedAllocation] = []
    for _, opp, inst, remaining in buckets:
        if left <= ZERO:
            break
        take = min(left, remaining).quantize(CENT, rounding=ROUND_HALF_UP)
        if take <= ZERO:
            continue
        assert opp.id is not None
        planned.append(
            PlannedAllocation(
                opportunity_id=opp.id,
                opportunity_title=opp.title,
                installment_id=inst.id if inst else None,
                installment_number=inst.number if inst else None,
                due_on=inst.due_on if inst else opp.due_on,
                amount=take,
            )
        )
        left = (left - take).quantize(CENT, rounding=ROUND_HALF_UP)

    return planned, left


async def _plan_manual_allocations(
    session: AsyncSession,
    *,
    account_id: int,
    contact_id: int,
    currency: str | None,
    amount: Decimal,
    raw_allocations: Sequence[dict[str, Any]],
    exclude_payment_id: int | None = None,
) -> tuple[list[PlannedAllocation], Decimal]:
    if not raw_allocations:
        return [], amount

    norm_currency = normalize_currency(currency)
    opp_ids = list({int(item["opportunity_id"]) for item in raw_allocations})
    opps_rows = (
        await session.exec(
            select(CrmOpportunity).where(
                CrmOpportunity.account_id == account_id,
                col(CrmOpportunity.id).in_(opp_ids),
            )
        )
    ).all()
    opps_by_id = {o.id: o for o in opps_rows if o.id is not None}
    stages_by_id = await _stages_by_id(session, {o.stage_id for o in opps_rows})
    insts_by_opp = await _installments_by_opp(session, opp_ids)
    allocs_by_opp = await _allocations_by_opp(
        session, opp_ids, exclude_payment_id=exclude_payment_id
    )

    # Track remaining capacity per opportunity and per installment.
    opp_remaining: dict[int, Decimal] = {}
    inst_remaining: dict[int, Decimal] = {}
    inst_by_id: dict[int, CrmInstallment] = {}
    for oid, opp in opps_by_id.items():
        st = stages_by_id.get(opp.stage_id)
        is_won = st is not None and st.kind == STAGE_WON
        summary = compute_opportunity_billing(
            opp,
            is_won=is_won,
            installments=insts_by_opp.get(oid, []),
            allocations=allocs_by_opp.get(oid, []),
            as_of=date.today(),
        )
        opp_remaining[oid] = summary.owed_amount
        for item in summary.installments:
            if item.installment.id is not None:
                inst_remaining[item.installment.id] = item.remaining_amount
                inst_by_id[item.installment.id] = item.installment

    planned: list[PlannedAllocation] = []
    total_allocated = ZERO

    for raw in raw_allocations:
        oid = raw.get("opportunity_id")
        if not isinstance(oid, int) or oid not in opps_by_id:
            raise _unprocessable("opportunity_id is invalid")
        opp = opps_by_id[oid]
        st = stages_by_id.get(opp.stage_id)
        if st is None or st.kind != STAGE_WON:
            raise _unprocessable(
                "Solo se puede imputar a ventas ganadas", code="opportunity_not_won"
            )
        if opp.contact_id != contact_id:
            raise _unprocessable("La venta no pertenece a este contacto", code="contact_mismatch")
        if normalize_currency(opp.currency) != norm_currency:
            raise _unprocessable(
                "La moneda del pago debe coincidir con la de la venta",
                code="currency_mismatch",
            )
        req_amt = to_decimal(raw.get("amount"), "allocations.amount")
        total_allocated = (total_allocated + req_amt).quantize(CENT, rounding=ROUND_HALF_UP)
        if total_allocated > amount:
            raise _unprocessable(
                "La suma imputada no puede superar el monto del pago",
                code="allocation_exceeds_payment",
            )
        if req_amt > opp_remaining[oid]:
            raise _unprocessable(
                "La imputación supera lo que debe la venta",
                code="allocation_exceeds_owed",
            )

        inst_id = raw.get("installment_id")
        opp_insts = insts_by_opp.get(oid, [])

        if inst_id is not None:
            inst = inst_by_id.get(inst_id)
            if inst is None or inst.opportunity_id != oid:
                raise _unprocessable("installment_id is invalid")
            if req_amt > inst_remaining[inst_id]:
                raise _unprocessable(
                    "La imputación supera lo que falta pagar de la cuota",
                    code="allocation_exceeds_installment",
                )
            inst_remaining[inst_id] = (inst_remaining[inst_id] - req_amt).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
            opp_remaining[oid] = (opp_remaining[oid] - req_amt).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
            planned.append(
                PlannedAllocation(
                    opportunity_id=oid,
                    opportunity_title=opp.title,
                    installment_id=inst_id,
                    installment_number=inst.number,
                    due_on=inst.due_on,
                    amount=req_amt,
                )
            )
        elif opp_insts:
            # Manual allocation to an installment sale without specifying a single
            # installment: distribute oldest due installment first so installment
            # statuses stay synchronized.
            rem_to_place = req_amt
            for inst in sorted(opp_insts, key=lambda i: (i.due_on, i.number)):
                assert inst.id is not None
                if rem_to_place <= ZERO:
                    break
                avail = inst_remaining.get(inst.id, ZERO)
                if avail <= ZERO:
                    continue
                take = min(rem_to_place, avail).quantize(CENT, rounding=ROUND_HALF_UP)
                inst_remaining[inst.id] = (avail - take).quantize(CENT, rounding=ROUND_HALF_UP)
                opp_remaining[oid] = (opp_remaining[oid] - take).quantize(
                    CENT, rounding=ROUND_HALF_UP
                )
                rem_to_place = (rem_to_place - take).quantize(CENT, rounding=ROUND_HALF_UP)
                planned.append(
                    PlannedAllocation(
                        opportunity_id=oid,
                        opportunity_title=opp.title,
                        installment_id=inst.id,
                        installment_number=inst.number,
                        due_on=inst.due_on,
                        amount=take,
                    )
                )
            if rem_to_place > ZERO:
                raise _unprocessable(
                    "La imputación supera el saldo de las cuotas",
                    code="allocation_exceeds_owed",
                )
        else:
            opp_remaining[oid] = (opp_remaining[oid] - req_amt).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
            planned.append(
                PlannedAllocation(
                    opportunity_id=oid,
                    opportunity_title=opp.title,
                    installment_id=None,
                    installment_number=None,
                    due_on=opp.due_on,
                    amount=req_amt,
                )
            )

    unallocated = (amount - total_allocated).quantize(CENT, rounding=ROUND_HALF_UP)
    return planned, unallocated


# ---------------------------------------------------------------------------
# Payments CRUD & preview
# ---------------------------------------------------------------------------
async def _check_contact(session: AsyncSession, *, account_id: int, contact_id: Any) -> Contact:
    if not isinstance(contact_id, int):
        raise _unprocessable("contact_id is required")
    contact = await session.get(Contact, contact_id)
    if contact is None or contact.account_id != account_id:
        raise _unprocessable("contact_id is invalid")
    return contact


async def _contact_currency_balance(
    session: AsyncSession,
    *,
    account_id: int,
    contact_id: int,
    currency: str | None,
    exclude_payment_id: int | None = None,
) -> dict[str, Decimal]:
    norm = normalize_currency(currency)
    opps = await _contact_won_opportunities_in_currency(
        session, account_id=account_id, contact_id=contact_id, currency=norm
    )
    opp_ids = [o.id for o in opps if o.id is not None]
    allocs_by_opp = await _allocations_by_opp(
        session, opp_ids, exclude_payment_id=exclude_payment_id
    )
    owed_total = ZERO
    for o in opps:
        assert o.id is not None
        val = Decimal(o.value or 0).quantize(CENT, rounding=ROUND_HALF_UP)
        paid = sum((Decimal(a.amount) for a in allocs_by_opp.get(o.id, [])), ZERO)
        owed_total += max(ZERO, val - paid)

    p_stmt = select(CrmPayment).where(
        CrmPayment.account_id == account_id, CrmPayment.contact_id == contact_id
    )
    if exclude_payment_id is not None:
        p_stmt = p_stmt.where(CrmPayment.id != exclude_payment_id)
    payments = [
        p for p in (await session.exec(p_stmt)).all() if normalize_currency(p.currency) == norm
    ]
    p_allocs = await _allocations_by_payment(session, [p.id for p in payments if p.id is not None])
    credit_balance = ZERO
    for p in payments:
        assert p.id is not None
        used = sum((Decimal(a.amount) for a in p_allocs.get(p.id, [])), ZERO)
        credit_balance += max(ZERO, Decimal(p.amount) - used)

    return {
        "owed_total": owed_total.quantize(CENT, rounding=ROUND_HALF_UP),
        "credit_balance": credit_balance.quantize(CENT, rounding=ROUND_HALF_UP),
        "net_balance": (owed_total - credit_balance).quantize(CENT, rounding=ROUND_HALF_UP),
    }


async def preview_payment(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    contact = await _check_contact(
        session, account_id=account_id, contact_id=payload.get("contact_id")
    )
    assert contact.id is not None
    amount = to_decimal(payload.get("amount"), "amount")
    currency = normalize_currency(payload.get("currency"))
    mode = payload.get("allocation_mode") or "auto"
    if mode not in ("auto", "manual"):
        raise _unprocessable("allocation_mode must be 'auto' or 'manual'")
    exclude_id = payload.get("exclude_payment_id")

    before = await _contact_currency_balance(
        session,
        account_id=account_id,
        contact_id=contact.id,
        currency=currency,
        exclude_payment_id=exclude_id,
    )

    if mode == "auto":
        planned, unallocated = await _plan_auto_allocations(
            session,
            account_id=account_id,
            contact_id=contact.id,
            currency=currency,
            amount=amount,
            exclude_payment_id=exclude_id,
        )
    else:
        planned, unallocated = await _plan_manual_allocations(
            session,
            account_id=account_id,
            contact_id=contact.id,
            currency=currency,
            amount=amount,
            raw_allocations=payload.get("allocations") or [],
            exclude_payment_id=exclude_id,
        )

    allocated_total = (amount - unallocated).quantize(CENT, rounding=ROUND_HALF_UP)
    after_owed = max(ZERO, before["owed_total"] - allocated_total).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    after_credit = (before["credit_balance"] + unallocated).quantize(CENT, rounding=ROUND_HALF_UP)
    after_net = (after_owed - after_credit).quantize(CENT, rounding=ROUND_HALF_UP)

    return {
        "currency": currency,
        "amount": float(amount),
        "allocated_total": float(allocated_total),
        "unallocated_amount": float(unallocated),
        "allocations": [
            {
                "opportunity_id": p.opportunity_id,
                "opportunity_title": p.opportunity_title,
                "installment_id": p.installment_id,
                "installment_number": p.installment_number,
                "due_on": p.due_on.isoformat() if p.due_on else None,
                "amount": float(p.amount),
            }
            for p in planned
        ],
        "balance_before": {k: float(v) for k, v in before.items()},
        "balance_after": {
            "owed_total": float(after_owed),
            "credit_balance": float(after_credit),
            "net_balance": float(after_net),
        },
    }


async def create_payment(
    session: AsyncSession,
    *,
    account_id: int,
    payload: dict[str, Any],
    user_id: int | None,
) -> CrmPayment:
    contact = await _check_contact(
        session, account_id=account_id, contact_id=payload.get("contact_id")
    )
    assert contact.id is not None
    amount = to_decimal(payload.get("amount"), "amount")
    currency = normalize_currency(payload.get("currency"))
    paid_on = parse_date(payload.get("paid_on"), "paid_on") or date.today()
    method = payload.get("method") or PAYMENT_METHOD_CASH
    if method not in PAYMENT_METHODS:
        raise _unprocessable("method is invalid")
    note = payload.get("note")
    if isinstance(note, str):
        note = note.strip() or None

    raw_allocs = payload.get("allocations")
    mode = payload.get("allocation_mode")
    if mode is None:
        mode = "manual" if raw_allocs is not None else "auto"
    if mode not in ("auto", "manual"):
        raise _unprocessable("allocation_mode must be 'auto' or 'manual'")

    if mode == "auto":
        planned, _ = await _plan_auto_allocations(
            session,
            account_id=account_id,
            contact_id=contact.id,
            currency=currency,
            amount=amount,
        )
    else:
        planned, _ = await _plan_manual_allocations(
            session,
            account_id=account_id,
            contact_id=contact.id,
            currency=currency,
            amount=amount,
            raw_allocations=raw_allocs or [],
        )

    payment = CrmPayment(
        account_id=account_id,
        contact_id=contact.id,
        amount=amount,
        currency=currency,
        paid_on=paid_on,
        method=method,
        note=note,
        created_by_id=user_id,
    )
    session.add(payment)
    await session.flush()
    assert payment.id is not None

    for item in planned:
        session.add(
            CrmPaymentAllocation(
                account_id=account_id,
                payment_id=payment.id,
                opportunity_id=item.opportunity_id,
                installment_id=item.installment_id,
                amount=item.amount,
            )
        )
    await session.flush()
    await session.refresh(payment)
    return payment


async def update_payment(
    session: AsyncSession,
    *,
    account_id: int,
    payment: CrmPayment,
    payload: dict[str, Any],
) -> CrmPayment:
    assert payment.id is not None
    if "paid_on" in payload and payload["paid_on"] is not None:
        parsed = parse_date(payload["paid_on"], "paid_on", required=True)
        assert parsed is not None
        payment.paid_on = parsed
    if "method" in payload and payload["method"] is not None:
        if payload["method"] not in PAYMENT_METHODS:
            raise _unprocessable("method is invalid")
        payment.method = payload["method"]
    if "note" in payload:
        note = payload["note"]
        payment.note = note.strip() or None if isinstance(note, str) else None

    new_amount = (
        to_decimal(payload["amount"], "amount")
        if "amount" in payload and payload["amount"] is not None
        else Decimal(payment.amount).quantize(CENT, rounding=ROUND_HALF_UP)
    )

    reallocate = "allocations" in payload or "allocation_mode" in payload
    existing_allocs = (await _allocations_by_payment(session, [payment.id])).get(payment.id, [])

    if reallocate:
        mode = payload.get("allocation_mode")
        if mode is None:
            mode = "manual" if payload.get("allocations") is not None else "auto"
        if mode not in ("auto", "manual"):
            raise _unprocessable("allocation_mode must be 'auto' or 'manual'")
        if mode == "auto":
            planned, _ = await _plan_auto_allocations(
                session,
                account_id=account_id,
                contact_id=payment.contact_id,
                currency=payment.currency,
                amount=new_amount,
                exclude_payment_id=payment.id,
            )
        else:
            planned, _ = await _plan_manual_allocations(
                session,
                account_id=account_id,
                contact_id=payment.contact_id,
                currency=payment.currency,
                amount=new_amount,
                raw_allocations=payload.get("allocations") or [],
                exclude_payment_id=payment.id,
            )
        for old in existing_allocs:
            await session.delete(old)
        await session.flush()
        for item in planned:
            session.add(
                CrmPaymentAllocation(
                    account_id=account_id,
                    payment_id=payment.id,
                    opportunity_id=item.opportunity_id,
                    installment_id=item.installment_id,
                    amount=item.amount,
                )
            )
    else:
        used = sum((Decimal(a.amount) for a in existing_allocs), ZERO).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        if new_amount < used:
            raise _unprocessable(
                "El monto del pago no puede ser menor a lo ya imputado",
                code="amount_below_allocated",
            )

    payment.amount = new_amount
    session.add(payment)
    await session.flush()
    await session.refresh(payment)
    return payment


async def delete_payment(session: AsyncSession, *, payment: CrmPayment) -> None:
    assert payment.id is not None
    allocs = (await _allocations_by_payment(session, [payment.id])).get(payment.id, [])
    for a in allocs:
        await session.delete(a)
    if allocs:
        await session.flush()
    await session.delete(payment)
    await session.flush()


async def get_payment(
    session: AsyncSession, *, account_id: int, payment_id: int
) -> CrmPayment | None:
    return (
        await session.exec(
            select(CrmPayment).where(
                CrmPayment.id == payment_id,
                CrmPayment.account_id == account_id,
            )
        )
    ).first()


async def list_payments(
    session: AsyncSession,
    *,
    account_id: int,
    contact_id: int | None = None,
    opportunity_id: int | None = None,
    method: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[CrmPayment]:
    stmt = select(CrmPayment).where(CrmPayment.account_id == account_id)
    if contact_id is not None:
        stmt = stmt.where(CrmPayment.contact_id == contact_id)
    if opportunity_id is not None:
        stmt = stmt.where(
            col(CrmPayment.id).in_(
                select(CrmPaymentAllocation.payment_id).where(
                    CrmPaymentAllocation.account_id == account_id,
                    CrmPaymentAllocation.opportunity_id == opportunity_id,
                )
            )
        )
    if method in PAYMENT_METHODS:
        stmt = stmt.where(CrmPayment.method == method)
    if from_date is not None:
        stmt = stmt.where(col(CrmPayment.paid_on) >= from_date)
    if to_date is not None:
        stmt = stmt.where(col(CrmPayment.paid_on) <= to_date)
    stmt = stmt.order_by(col(CrmPayment.paid_on).desc(), col(CrmPayment.id).desc())
    stmt = stmt.offset(max(0, offset)).limit(min(max(1, limit), 500))
    return list((await session.exec(stmt)).all())


async def present_payments(
    session: AsyncSession, rows: Sequence[CrmPayment]
) -> list[dict[str, Any]]:
    if not rows:
        return []
    payment_ids = [r.id for r in rows if r.id is not None]
    allocs_by_p = await _allocations_by_payment(session, payment_ids)

    contact_ids = {r.contact_id for r in rows}
    user_ids = {r.created_by_id for r in rows if r.created_by_id is not None}
    opp_ids = {a.opportunity_id for lst in allocs_by_p.values() for a in lst}
    inst_ids = {
        a.installment_id
        for lst in allocs_by_p.values()
        for a in lst
        if a.installment_id is not None
    }

    contacts = (
        {
            c.id: c
            for c in (
                await session.exec(
                    select(Contact).where(col(Contact.id).in_(contact_ids)).options(lazyload("*"))
                )
            ).all()
        }
        if contact_ids
        else {}
    )
    users = (
        {
            u.id: u
            for u in (
                await session.exec(
                    select(User).where(col(User.id).in_(user_ids)).options(lazyload("*"))
                )
            ).all()
        }
        if user_ids
        else {}
    )
    opps = (
        {
            o.id: o
            for o in (
                await session.exec(
                    select(CrmOpportunity)
                    .where(col(CrmOpportunity.id).in_(opp_ids))
                    .options(lazyload("*"))
                )
            ).all()
        }
        if opp_ids
        else {}
    )
    insts = (
        {
            i.id: i
            for i in (
                await session.exec(
                    select(CrmInstallment)
                    .where(col(CrmInstallment.id).in_(inst_ids))
                    .options(lazyload("*"))
                )
            ).all()
        }
        if inst_ids
        else {}
    )

    out: list[dict[str, Any]] = []
    for p in rows:
        assert p.id is not None
        p_allocs = allocs_by_p.get(p.id, [])
        p_amount = Decimal(p.amount).quantize(CENT, rounding=ROUND_HALF_UP)
        allocated = sum((Decimal(a.amount) for a in p_allocs), ZERO).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        unallocated = max(ZERO, p_amount - allocated)
        contact = contacts.get(p.contact_id)
        creator = users.get(p.created_by_id) if p.created_by_id else None
        out.append(
            {
                "id": p.id,
                "contact_id": p.contact_id,
                "amount": float(p_amount),
                "currency": p.currency,
                "paid_on": p.paid_on.isoformat(),
                "method": p.method,
                "note": p.note,
                "allocated_amount": float(allocated),
                "unallocated_amount": float(unallocated),
                "created_by_id": p.created_by_id,
                "created_by": (
                    {"id": creator.id, "name": creator.display_name or creator.name}
                    if creator
                    else None
                ),
                "contact": (
                    {
                        "id": contact.id,
                        "name": contact.name,
                        "avatar_url": getattr(contact, "avatar_url", None),
                    }
                    if contact
                    else None
                ),
                "created_at": int(p.created_at.timestamp()) if p.created_at else None,
                "allocations": [
                    {
                        "id": a.id,
                        "opportunity_id": a.opportunity_id,
                        "opportunity_title": (
                            opps[a.opportunity_id].title if a.opportunity_id in opps else None
                        ),
                        "installment_id": a.installment_id,
                        "installment_number": (
                            insts[a.installment_id].number
                            if a.installment_id and a.installment_id in insts
                            else None
                        ),
                        "amount": float(Decimal(a.amount).quantize(CENT, rounding=ROUND_HALF_UP)),
                    }
                    for a in p_allocs
                ],
            }
        )
    return out


# ---------------------------------------------------------------------------
# Contact Statement (Cuenta corriente)
# ---------------------------------------------------------------------------
async def get_contact_statement(
    session: AsyncSession,
    *,
    account_id: int,
    contact_id: int,
    as_of: date | None = None,
) -> dict[str, Any]:
    contact = await session.get(Contact, contact_id)
    if contact is None or contact.account_id != account_id:
        raise ChatwootHTTPException(
            status_code=404, detail={"error": "Resource could not be found"}
        )
    today = as_of or date.today()

    won_opps = list(
        (
            await session.exec(
                select(CrmOpportunity)
                .join(CrmStage, col(CrmStage.id) == CrmOpportunity.stage_id)
                .where(
                    CrmOpportunity.account_id == account_id,
                    CrmOpportunity.contact_id == contact_id,
                    CrmStage.kind == STAGE_WON,
                )
                .order_by(
                    col(CrmOpportunity.closed_at).desc().nullslast(), col(CrmOpportunity.id).desc()
                )
            )
        ).all()
    )
    opp_ids = [o.id for o in won_opps if o.id is not None]
    insts_by_opp = await _installments_by_opp(session, opp_ids)
    allocs_by_opp = await _allocations_by_opp(session, opp_ids)

    owner_ids = {o.owner_id for o in won_opps if o.owner_id is not None}
    owners = (
        {
            u.id: u
            for u in (
                await session.exec(
                    select(User).where(col(User.id).in_(owner_ids)).options(lazyload("*"))
                )
            ).all()
        }
        if owner_ids
        else {}
    )

    payments = await list_payments(session, account_id=account_id, contact_id=contact_id, limit=500)
    presented_payments = await present_payments(session, payments)
    allocs_by_pay = await _allocations_by_payment(
        session, [p.id for p in payments if p.id is not None]
    )

    # Aggregate balances by currency (never converting).
    class _CurAcc:
        def __init__(self) -> None:
            self.total_sales = ZERO
            self.paid_total = ZERO
            self.owed_total = ZERO
            self.credit_balance = ZERO
            self.overdue_total = ZERO
            self.days_overdue = 0
            self.next_due_on: date | None = None

    by_currency: dict[str | None, _CurAcc] = {}

    def _acc(cur: str | None) -> _CurAcc:
        key = normalize_currency(cur)
        if key not in by_currency:
            by_currency[key] = _CurAcc()
        return by_currency[key]

    presented_sales: list[dict[str, Any]] = []
    for opp in won_opps:
        assert opp.id is not None
        summary = compute_opportunity_billing(
            opp,
            is_won=True,
            installments=insts_by_opp.get(opp.id, []),
            allocations=allocs_by_opp.get(opp.id, []),
            as_of=today,
        )
        acc = _acc(opp.currency)
        acc.total_sales += summary.value
        acc.owed_total += summary.owed_amount
        acc.overdue_total += summary.overdue_amount
        if summary.days_overdue > acc.days_overdue:
            acc.days_overdue = summary.days_overdue
        if summary.next_due_on is not None and (
            acc.next_due_on is None or summary.next_due_on < acc.next_due_on
        ):
            acc.next_due_on = summary.next_due_on

        owner = owners.get(opp.owner_id) if opp.owner_id else None
        presented_sales.append(
            {
                "id": opp.id,
                "title": opp.title,
                "value": float(summary.value) if opp.value is not None else None,
                "currency": normalize_currency(opp.currency),
                "closed_at": int(opp.closed_at.timestamp()) if opp.closed_at else None,
                "payment_terms": opp.payment_terms,
                "due_on": opp.due_on.isoformat() if opp.due_on else None,
                "paid_amount": float(summary.paid_amount),
                "owed_amount": float(summary.owed_amount),
                "overdue_amount": float(summary.overdue_amount),
                "days_overdue": summary.days_overdue,
                "next_due_on": summary.next_due_on.isoformat() if summary.next_due_on else None,
                "owner": (
                    {"id": owner.id, "name": owner.display_name or owner.name} if owner else None
                ),
                "installments": [
                    {
                        "id": item.installment.id,
                        "number": item.installment.number,
                        "due_on": item.installment.due_on.isoformat(),
                        "amount": float(
                            Decimal(item.installment.amount).quantize(CENT, rounding=ROUND_HALF_UP)
                        ),
                        "paid_amount": float(item.paid_amount),
                        "remaining_amount": float(item.remaining_amount),
                        "days_overdue": item.days_overdue,
                        "status": item.status,
                        "locked": item.direct_paid_amount > ZERO,
                    }
                    for item in summary.installments
                ],
            }
        )

    for p in payments:
        assert p.id is not None
        acc = _acc(p.currency)
        p_amt = Decimal(p.amount).quantize(CENT, rounding=ROUND_HALF_UP)
        used = sum((Decimal(a.amount) for a in allocs_by_pay.get(p.id, [])), ZERO).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        acc.paid_total += p_amt
        acc.credit_balance += max(ZERO, p_amt - used)

    balances = [
        {
            "currency": cur,
            "total_sales": float(acc.total_sales.quantize(CENT, rounding=ROUND_HALF_UP)),
            "paid_total": float(acc.paid_total.quantize(CENT, rounding=ROUND_HALF_UP)),
            "owed_total": float(acc.owed_total.quantize(CENT, rounding=ROUND_HALF_UP)),
            "credit_balance": float(acc.credit_balance.quantize(CENT, rounding=ROUND_HALF_UP)),
            "net_balance": float(
                (acc.owed_total - acc.credit_balance).quantize(CENT, rounding=ROUND_HALF_UP)
            ),
            "overdue_total": float(acc.overdue_total.quantize(CENT, rounding=ROUND_HALF_UP)),
            "days_overdue": acc.days_overdue,
            "next_due_on": acc.next_due_on.isoformat() if acc.next_due_on else None,
        }
        for cur, acc in sorted(by_currency.items(), key=lambda kv: (kv[0] is None, kv[0] or ""))
    ]

    wa_map = await whatsapp_conversations_for_contacts(
        session, account_id=account_id, contact_ids=[contact_id]
    )

    return {
        "as_of": today.isoformat(),
        "contact": {
            "id": contact.id,
            "name": contact.name,
            "email": contact.email,
            "phone_number": contact.phone_number,
            "avatar_url": getattr(contact, "avatar_url", None),
        },
        "whatsapp_conversation": wa_map.get(contact_id),
        "balances": balances,
        "sales": presented_sales,
        "payments": presented_payments,
    }


# ---------------------------------------------------------------------------
# Accounts Receivable (Cuentas por cobrar) & Summary
# ---------------------------------------------------------------------------
async def _load_account_receivables_state(
    session: AsyncSession,
    *,
    account_id: int,
    owner_id: int | None = None,
    as_of: date | None = None,
) -> tuple[
    date,
    list[CrmOpportunity],
    dict[int, OpportunityBillingSummary],
    dict[int, list[CrmPayment]],
    dict[int, list[CrmPaymentAllocation]],
]:
    today = as_of or date.today()
    stmt = (
        select(CrmOpportunity)
        .join(CrmStage, col(CrmStage.id) == CrmOpportunity.stage_id)
        .where(
            CrmOpportunity.account_id == account_id,
            CrmStage.kind == STAGE_WON,
            col(CrmOpportunity.value).is_not(None),
            col(CrmOpportunity.value) > 0,
        )
    )
    if owner_id is not None:
        stmt = stmt.where(CrmOpportunity.owner_id == owner_id)
    won_opps = list((await session.exec(stmt)).all())
    opp_ids = [o.id for o in won_opps if o.id is not None]
    insts_by_opp = await _installments_by_opp(session, opp_ids)
    allocs_by_opp = await _allocations_by_opp(session, opp_ids)

    summaries: dict[int, OpportunityBillingSummary] = {}
    contact_ids: set[int] = set()
    for opp in won_opps:
        assert opp.id is not None
        summaries[opp.id] = compute_opportunity_billing(
            opp,
            is_won=True,
            installments=insts_by_opp.get(opp.id, []),
            allocations=allocs_by_opp.get(opp.id, []),
            as_of=today,
        )
        if opp.contact_id is not None:
            contact_ids.add(opp.contact_id)

    payments_by_contact: dict[int, list[CrmPayment]] = defaultdict(list)
    allocs_by_payment: dict[int, list[CrmPaymentAllocation]] = {}
    if contact_ids:
        p_rows = (
            await session.exec(
                select(CrmPayment).where(
                    CrmPayment.account_id == account_id,
                    col(CrmPayment.contact_id).in_(contact_ids),
                )
            )
        ).all()
        for p in p_rows:
            payments_by_contact[p.contact_id].append(p)
        allocs_by_payment = await _allocations_by_payment(
            session, [p.id for p in p_rows if p.id is not None]
        )

    return today, won_opps, summaries, payments_by_contact, allocs_by_payment


async def list_receivables(
    session: AsyncSession,
    *,
    account_id: int,
    status: str | None = None,
    owner_id: int | None = None,
    q: str | None = None,
    sort: str = "overdue",
    order: str = "desc",
    page: int = 1,
    per_page: int = 25,
    as_of: date | None = None,
) -> dict[str, Any]:
    """List contacts with outstanding balances, with filtering, sorting and pagination."""
    (
        today,
        won_opps,
        summaries,
        payments_by_contact,
        allocs_by_payment,
    ) = await _load_account_receivables_state(
        session, account_id=account_id, owner_id=owner_id, as_of=as_of
    )

    opps_by_contact: dict[int, list[CrmOpportunity]] = defaultdict(list)
    for opp in won_opps:
        if opp.contact_id is None or opp.id is None:
            continue
        if summaries[opp.id].owed_amount > ZERO:
            opps_by_contact[opp.contact_id].append(opp)

    if not opps_by_contact:
        return {
            "items": [],
            "meta": {"page": max(1, page), "per_page": per_page, "total": 0, "total_pages": 0},
        }

    contact_ids = list(opps_by_contact.keys())
    contacts_rows = (
        await session.exec(
            select(Contact).where(col(Contact.id).in_(contact_ids)).options(lazyload("*"))
        )
    ).all()
    contacts_by_id = {c.id: c for c in contacts_rows if c.id is not None}

    owner_ids = {
        o.owner_id for lst in opps_by_contact.values() for o in lst if o.owner_id is not None
    }
    owners_by_id = (
        {
            u.id: u
            for u in (
                await session.exec(
                    select(User).where(col(User.id).in_(owner_ids)).options(lazyload("*"))
                )
            ).all()
        }
        if owner_ids
        else {}
    )

    needle = q.strip().lower() if q and q.strip() else None

    rows: list[dict[str, Any]] = []
    for cid, c_opps in opps_by_contact.items():
        contact = contacts_by_id.get(cid)
        if contact is None:
            continue
        if needle:
            haystack = " ".join(
                filter(None, [contact.name, contact.email, contact.phone_number])
            ).lower()
            if needle not in haystack:
                continue

        cur_owed: dict[str | None, Decimal] = defaultdict(lambda: ZERO)
        cur_overdue: dict[str | None, Decimal] = defaultdict(lambda: ZERO)
        cur_credit: dict[str | None, Decimal] = defaultdict(lambda: ZERO)
        days_overdue = 0
        next_due: date | None = None
        overdue_count = 0
        primary_owner_id: int | None = None

        for opp in c_opps:
            assert opp.id is not None
            s = summaries[opp.id]
            cur = normalize_currency(opp.currency)
            cur_owed[cur] += s.owed_amount
            cur_overdue[cur] += s.overdue_amount
            if s.overdue_amount > ZERO:
                overdue_count += 1
            if s.days_overdue > days_overdue:
                days_overdue = s.days_overdue
            if s.next_due_on is not None and (next_due is None or s.next_due_on < next_due):
                next_due = s.next_due_on
            if primary_owner_id is None and opp.owner_id is not None:
                primary_owner_id = opp.owner_id

        for p in payments_by_contact.get(cid, []):
            assert p.id is not None
            cur = normalize_currency(p.currency)
            used = sum((Decimal(a.amount) for a in allocs_by_payment.get(p.id, [])), ZERO)
            unalloc = max(ZERO, Decimal(p.amount) - used)
            if unalloc > ZERO:
                cur_credit[cur] += unalloc

        has_overdue = any(v > ZERO for v in cur_overdue.values())
        if status == "overdue" and not has_overdue:
            continue
        if status == "upcoming" and (has_overdue or next_due is None):
            continue

        all_curs = sorted(
            set(cur_owed.keys()) | set(cur_credit.keys()),
            key=lambda c: (c is None, c or ""),
        )
        currencies_payload = [
            {
                "currency": cur,
                "owed_total": float(cur_owed[cur].quantize(CENT, rounding=ROUND_HALF_UP)),
                "overdue_total": float(cur_overdue[cur].quantize(CENT, rounding=ROUND_HALF_UP)),
                "credit_balance": float(cur_credit[cur].quantize(CENT, rounding=ROUND_HALF_UP)),
                "net_balance": float(
                    (cur_owed[cur] - cur_credit[cur]).quantize(CENT, rounding=ROUND_HALF_UP)
                ),
            }
            for cur in all_curs
            if cur_owed[cur] > ZERO or cur_credit[cur] > ZERO
        ]
        owner = owners_by_id.get(primary_owner_id) if primary_owner_id else None
        rows.append(
            {
                "contact": {
                    "id": contact.id,
                    "name": contact.name,
                    "email": contact.email,
                    "phone_number": contact.phone_number,
                    "avatar_url": getattr(contact, "avatar_url", None),
                },
                "owner": (
                    {"id": owner.id, "name": owner.display_name or owner.name} if owner else None
                ),
                "currencies": currencies_payload,
                "days_overdue": days_overdue,
                "next_due_on": next_due.isoformat() if next_due else None,
                "sales_count": len(c_opps),
                "overdue_count": overdue_count,
                "_sort_owed": sum(cur_owed.values(), ZERO),
                "_sort_overdue": sum(cur_overdue.values(), ZERO),
                "_sort_due": next_due or date.max,
                "_sort_name": (contact.name or contact.email or contact.phone_number or "").lower(),
            }
        )

    reverse = order != "asc"
    if sort == "amount":
        rows.sort(key=lambda r: (r["_sort_owed"], r["days_overdue"]), reverse=reverse)
    elif sort == "due_on":
        rows.sort(key=lambda r: r["_sort_due"], reverse=reverse)
    elif sort == "name":
        rows.sort(key=lambda r: r["_sort_name"], reverse=reverse)
    else:  # "overdue" default
        rows.sort(
            key=lambda r: (r["days_overdue"], r["_sort_overdue"], r["_sort_owed"]),
            reverse=reverse,
        )

    total = len(rows)
    safe_per_page = min(max(1, per_page), 100)
    safe_page = max(1, page)
    total_pages = (total + safe_per_page - 1) // safe_per_page if total > 0 else 0
    start = (safe_page - 1) * safe_per_page
    page_rows = rows[start : start + safe_per_page]

    wa_map = await whatsapp_conversations_for_contacts(
        session,
        account_id=account_id,
        contact_ids=[r["contact"]["id"] for r in page_rows],
    )
    items = []
    for r in page_rows:
        item = {k: v for k, v in r.items() if not k.startswith("_")}
        item["whatsapp_conversation"] = wa_map.get(r["contact"]["id"])
        items.append(item)

    return {
        "as_of": today.isoformat(),
        "items": items,
        "meta": {
            "page": safe_page,
            "per_page": safe_per_page,
            "total": total,
            "total_pages": total_pages,
        },
    }


async def get_receivables_summary(
    session: AsyncSession,
    *,
    account_id: int,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Summary of amounts to collect, overdue, and collected this month, by currency."""
    today = as_of or date.today()
    month_start = date(today.year, today.month, 1)
    next_month = _add_months(month_start, 1)

    won_opps = list(
        (
            await session.exec(
                select(CrmOpportunity)
                .join(CrmStage, col(CrmStage.id) == CrmOpportunity.stage_id)
                .where(
                    CrmOpportunity.account_id == account_id,
                    CrmStage.kind == STAGE_WON,
                    col(CrmOpportunity.value).is_not(None),
                    col(CrmOpportunity.value) > 0,
                )
            )
        ).all()
    )
    opp_ids = [o.id for o in won_opps if o.id is not None]
    insts_by_opp = await _installments_by_opp(session, opp_ids)
    allocs_by_opp = await _allocations_by_opp(session, opp_ids)

    to_collect: dict[str | None, Decimal] = defaultdict(lambda: ZERO)
    overdue: dict[str | None, Decimal] = defaultdict(lambda: ZERO)
    debtors: set[int] = set()
    overdue_debtors: set[int] = set()

    for opp in won_opps:
        assert opp.id is not None
        s = compute_opportunity_billing(
            opp,
            is_won=True,
            installments=insts_by_opp.get(opp.id, []),
            allocations=allocs_by_opp.get(opp.id, []),
            as_of=today,
        )
        cur = normalize_currency(opp.currency)
        if s.owed_amount > ZERO:
            to_collect[cur] += s.owed_amount
            if opp.contact_id is not None:
                debtors.add(opp.contact_id)
        if s.overdue_amount > ZERO:
            overdue[cur] += s.overdue_amount
            if opp.contact_id is not None:
                overdue_debtors.add(opp.contact_id)

    # Collected this month (by payment paid_on) & total credit balance per currency.
    month_payments = (
        await session.exec(
            select(CrmPayment.currency, func.coalesce(func.sum(CrmPayment.amount), 0))
            .where(
                CrmPayment.account_id == account_id,
                col(CrmPayment.paid_on) >= month_start,
                col(CrmPayment.paid_on) < next_month,
            )
            .group_by(CrmPayment.currency)
        )
    ).all()
    collected_this_month: dict[str | None, Decimal] = defaultdict(lambda: ZERO)
    for cur, amt in month_payments:
        collected_this_month[normalize_currency(cur)] += Decimal(amt or 0).quantize(
            CENT, rounding=ROUND_HALF_UP
        )

    all_payments = (
        await session.exec(select(CrmPayment).where(CrmPayment.account_id == account_id))
    ).all()
    allocs_by_pay = await _allocations_by_payment(
        session, [p.id for p in all_payments if p.id is not None]
    )
    credit_balance: dict[str | None, Decimal] = defaultdict(lambda: ZERO)
    for p in all_payments:
        assert p.id is not None
        used = sum((Decimal(a.amount) for a in allocs_by_pay.get(p.id, [])), ZERO)
        unalloc = max(ZERO, Decimal(p.amount) - used)
        if unalloc > ZERO:
            credit_balance[normalize_currency(p.currency)] += unalloc

    all_curs = sorted(
        set(to_collect.keys())
        | set(overdue.keys())
        | set(collected_this_month.keys())
        | set(credit_balance.keys()),
        key=lambda c: (c is None, c or ""),
    )

    return {
        "as_of": today.isoformat(),
        "month": f"{today.year:04d}-{today.month:02d}",
        "debtors_count": len(debtors),
        "overdue_debtors_count": len(overdue_debtors),
        "currencies": [
            {
                "currency": cur,
                "to_collect": float(to_collect[cur].quantize(CENT, rounding=ROUND_HALF_UP)),
                "overdue": float(overdue[cur].quantize(CENT, rounding=ROUND_HALF_UP)),
                "collected_this_month": float(
                    collected_this_month[cur].quantize(CENT, rounding=ROUND_HALF_UP)
                ),
                "credit_balance": float(credit_balance[cur].quantize(CENT, rounding=ROUND_HALF_UP)),
            }
            for cur in all_curs
        ],
    }


__all__ = [
    "CENT",
    "ZERO",
    "InstallmentSummary",
    "OpportunityBillingSummary",
    "build_installment_schedule",
    "compute_opportunity_billing",
    "create_payment",
    "delete_payment",
    "get_contact_statement",
    "get_opportunity_billing",
    "get_payment",
    "get_receivables_summary",
    "guard_opportunity_change",
    "guard_opportunity_delete",
    "list_payments",
    "list_receivables",
    "normalize_currency",
    "parse_date",
    "present_payments",
    "preview_payment",
    "set_opportunity_billing",
    "summarize_opportunities",
    "to_decimal",
    "update_installment",
    "update_payment",
    "whatsapp_conversations_for_contacts",
]
