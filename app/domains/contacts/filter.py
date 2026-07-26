"""Contact filter-DSL backend.

Ported from:
  reference/chatwoot/app/services/contacts/filter_service.rb
  reference/chatwoot/app/services/filter_service.rb
  reference/chatwoot/lib/filters/filter_keys.yml (contact section)

Powers ``POST /contacts/filter`` and, through it, contact *segments*
(a saved contact filter = a ``CustomView`` with ``filter_type: contact``).
Same condition shape as the conversation filter — a list of
``{attribute_key, filter_operator, values, query_operator}`` dicts — but
over contact columns.

Attributes + operators:
  * Text (``name`` / ``email`` / ``phone_number`` / ``identifier`` /
    ``company_name``): equal_to, not_equal_to, contains, does_not_contain,
    starts_with, is_present, is_not_present. Matching is case-insensitive
    (mirrors Chatwoot's ``filter_values`` downcasing).
  * ``company_name`` reads ``additional_attributes->>'company_name'``.
  * ``blocked`` (bool): equal_to (``"true"``/``"false"``).
  * ``created_at`` (date): is_greater_than, is_less_than, equal_to.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, func, or_
from sqlalchemy.sql import ColumnElement
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.contacts.models import Contact

RESULTS_PER_PAGE = 15

_TEXT_ATTRS = {"name", "email", "phone_number", "identifier", "company_name"}
_BOOL_ATTRS = {"blocked"}
_DATE_ATTRS = {"created_at"}

_TEXT_OPS = {
    "equal_to",
    "not_equal_to",
    "contains",
    "does_not_contain",
    "starts_with",
    "is_present",
    "is_not_present",
}
_BOOL_OPS = {"equal_to"}
_DATE_OPS = {"is_greater_than", "is_less_than", "equal_to"}

_VALUE_REQUIRED_OPS = {
    "equal_to",
    "not_equal_to",
    "contains",
    "does_not_contain",
    "starts_with",
    "is_greater_than",
    "is_less_than",
}


def _err(status: int, message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=status, detail={"message": message})


def _column_for(attr: str) -> ColumnElement[Any]:
    if attr == "company_name":
        return Contact.additional_attributes["company_name"].astext
    return getattr(Contact, attr)


def _text_clause(
    col: ColumnElement[Any], operator: str, value: str
) -> ColumnElement[Any]:
    v = value.strip()
    if operator == "equal_to":
        return func.lower(col) == v.lower()
    if operator == "not_equal_to":
        # NULLs count as "not equal" — an unset field isn't the value.
        return or_(col.is_(None), func.lower(col) != v.lower())
    if operator == "contains":
        return col.ilike(f"%{v}%")
    if operator == "does_not_contain":
        return or_(col.is_(None), col.not_ilike(f"%{v}%"))
    if operator == "starts_with":
        return col.ilike(f"{v}%")
    raise _err(400, f"unsupported text operator: {operator}")


def _parse_date(value: Any, *, attr: str) -> date:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise _err(400, f"{attr}: invalid date {value!r}") from exc


def _build_clause(condition: dict[str, Any]) -> ColumnElement[Any]:
    attr = condition.get("attribute_key")
    operator = condition.get("filter_operator")
    values = condition.get("values") or []

    if not isinstance(attr, str) or not attr:
        raise _err(400, "attribute_key is required")
    if not isinstance(operator, str) or not operator:
        raise _err(400, "filter_operator is required")

    if attr in _TEXT_ATTRS:
        allowed = _TEXT_OPS
    elif attr in _BOOL_ATTRS:
        allowed = _BOOL_OPS
    elif attr in _DATE_ATTRS:
        allowed = _DATE_OPS
    else:
        raise _err(400, f"unknown attribute_key: {attr!r}")

    if operator not in allowed:
        raise _err(400, f"operator {operator!r} not allowed for {attr}")

    if operator in _VALUE_REQUIRED_OPS and (
        not isinstance(values, list) or not values
    ):
        raise _err(400, f"values is required for {attr} {operator}")

    col = _column_for(attr)

    # Presence operators need no value + apply to text attributes.
    if operator == "is_present":
        return and_(col.isnot(None), col != "")
    if operator == "is_not_present":
        return or_(col.is_(None), col == "")

    if attr in _BOOL_ATTRS:
        return col.is_(str(values[0]).strip().lower() == "true")

    if attr in _DATE_ATTRS:
        d = _parse_date(values[0], attr=attr)
        if operator == "is_greater_than":
            return col > d
        if operator == "is_less_than":
            return col < d
        return func.date(col) == d  # equal_to

    return _text_clause(col, operator, str(values[0]))


def _validate_query_operator(value: Any) -> None:
    if value is None:
        return
    if value not in ("AND", "OR"):
        raise _err(400, f"Invalid query_operator: {value!r} (allowed: AND, OR)")


def _combine(
    clauses: list[ColumnElement[Any]], ops: list[str]
) -> ColumnElement[Any]:
    """Left-fold clauses joining each with the operator that followed it.

    Mirrors the conversation filter: each condition carries a
    ``query_operator`` joining it with the *next* condition; a single
    trailing operator is ignored.
    """
    expr = clauses[0]
    for clause, op in zip(clauses[1:], ops, strict=False):
        expr = or_(expr, clause) if op == "OR" else and_(expr, clause)
    return expr


async def contact_filter(
    session: AsyncSession,
    *,
    account_id: int,
    payload: list[dict[str, Any]],
    page: int = 1,
    per_page: int = RESULTS_PER_PAGE,
) -> tuple[list[Contact], int]:
    """Run a contact filter-DSL request → ``(contacts, total_count)``."""
    if not isinstance(payload, list) or not payload:
        raise _err(400, "payload must be a non-empty array of conditions")

    clauses: list[ColumnElement[Any]] = []
    join_ops: list[str] = []
    for cond in payload:
        if not isinstance(cond, dict):
            raise _err(400, "every condition must be a JSON object")
        _validate_query_operator(cond.get("query_operator"))
        clauses.append(_build_clause(cond))
        join_ops.append(str(cond.get("query_operator") or "AND"))

    where_expr = _combine(clauses, join_ops[:-1])

    count = int(
        (
            await session.exec(
                select(func.count())
                .select_from(Contact)
                .where(Contact.account_id == account_id)
                .where(where_expr)
            )
        ).one()
        or 0
    )
    rows = list(
        (
            await session.exec(
                select(Contact)
                .where(Contact.account_id == account_id)
                .where(where_expr)
                .order_by(Contact.id.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        ).all()
    )
    return rows, count


__all__ = ["contact_filter"]
