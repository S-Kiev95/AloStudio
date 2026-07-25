"""Conversation filter-DSL backend.

Ported from:
  reference/chatwoot/app/services/conversations/filter_service.rb
  reference/chatwoot/app/services/filter_service.rb
  reference/chatwoot/app/helpers/filters/filter_helper.rb
  reference/chatwoot/lib/filters/filter_keys.yml

Powers ``POST /conversations/filter``. The controller builds an
ActiveRecord ``where(@query_string, @filter_values)`` using a string
fragment per condition + a bind-value dict — we instead build SA
``BinaryExpression`` objects per condition and combine them into a
single ``and_/or_`` tree.

Phase 4b subset (PLAN.phase4b.md):
  * Operators: ``equal_to``, ``not_equal_to``, ``contains``,
    ``does_not_contain``, ``is_present``, ``is_not_present``.
  * Standard attributes: ``status``, ``priority``, ``assignee_id``,
    ``team_id``, ``inbox_id``, ``labels``, ``created_at``,
    ``last_activity_at``.

Deferred:
  * ``is_greater_than`` / ``is_less_than`` / ``days_before`` / ``starts_with``
    operators — Phase 6 (alongside Automation conditions).
  * ``additional_attributes`` JSONB lookups — Phase 6.
  * ``custom_attribute`` lookups — Phase 6 (needs the
    custom_attribute_definitions registry to grow up).
  * ``query_operator`` validation already accepts AND/OR; only those.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, func, or_
from sqlalchemy.sql import ColumnElement
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.conversations.finder import DEFAULT_PER_PAGE
from app.domains.conversations.models import (
    Conversation,
    ConversationLabel,
    conversation_priority_from_str,
    conversation_status_from_str,
)
from app.domains.conversations.permission import apply_permission_scope
from app.domains.labels.models import Label

# Mirror ``filter_keys.yml`` — operator allow-list per attribute. We
# enforce it the same way ``Filters::FilterHelper#build_condition_query``
# does: an operator outside the allow-list raises InvalidOperator.
_ALLOWED_OPERATORS: dict[str, set[str]] = {
    "status": {"equal_to", "not_equal_to"},
    "priority": {"equal_to", "not_equal_to", "is_present", "is_not_present"},
    "assignee_id": {"equal_to", "not_equal_to", "is_present", "is_not_present"},
    "inbox_id": {"equal_to", "not_equal_to", "is_present", "is_not_present"},
    "team_id": {"equal_to", "not_equal_to", "is_present", "is_not_present"},
    "labels": {"equal_to", "not_equal_to", "is_present", "is_not_present"},
    "created_at": {"equal_to", "not_equal_to"},
    "last_activity_at": {"equal_to", "not_equal_to"},
}

_VALUE_REQUIRED_OPS = {
    "equal_to",
    "not_equal_to",
    "contains",
    "does_not_contain",
}

_DATE_ATTRS = {"created_at", "last_activity_at"}


def _err(status: int, message: str) -> ChatwootHTTPException:
    """Mirror Rails' ``render_could_not_create_error(e.message)`` —
    422-equivalent envelope used by the filter controller."""
    return ChatwootHTTPException(status_code=status, detail={"message": message})


def _coerce_status_values(values: list[Any]) -> list[int]:
    out: list[int] = []
    for v in values:
        if v == "all":
            from app.domains.conversations.models import (
                CONVERSATION_STATUS_OPEN,
                CONVERSATION_STATUS_PENDING,
                CONVERSATION_STATUS_RESOLVED,
                CONVERSATION_STATUS_SNOOZED,
            )

            return [
                CONVERSATION_STATUS_OPEN,
                CONVERSATION_STATUS_RESOLVED,
                CONVERSATION_STATUS_PENDING,
                CONVERSATION_STATUS_SNOOZED,
            ]
        try:
            out.append(conversation_status_from_str(str(v)))
        except Exception as exc:
            raise _err(400, f"Invalid value for status: {v!r}") from exc
    return out


def _coerce_priority_values(values: list[Any]) -> list[int]:
    out: list[int] = []
    for v in values:
        coerced = conversation_priority_from_str(str(v))
        if coerced is None:
            raise _err(400, f"Invalid value for priority: {v!r}")
        out.append(coerced)
    return out


def _coerce_int_values(values: list[Any], *, attr: str) -> list[int]:
    out: list[int] = []
    for v in values:
        try:
            out.append(int(v))
        except (TypeError, ValueError) as exc:
            raise _err(400, f"Invalid value for {attr}: {v!r}") from exc
    return out


def _coerce_date_values(values: list[Any], *, attr: str) -> list[date]:
    out: list[date] = []
    for v in values:
        if isinstance(v, datetime):
            out.append(v.date())
            continue
        if isinstance(v, date):
            out.append(v)
            continue
        try:
            out.append(date.fromisoformat(str(v)))
        except ValueError as exc:
            raise _err(400, f"Invalid value for {attr}: {v!r}") from exc
    return out


def _column_for(attr: str) -> ColumnElement[Any]:
    return {
        "status": Conversation.status,
        "priority": Conversation.priority,
        "assignee_id": Conversation.assignee_id,
        "inbox_id": Conversation.inbox_id,
        "team_id": Conversation.team_id,
        "created_at": Conversation.created_at,
        "last_activity_at": Conversation.last_activity_at,
    }[attr]


def _build_label_clause(
    *, operator: str, values: list[str]
) -> ColumnElement[Any]:
    """Mirror ``tag_filter_query`` — EXISTS / NOT EXISTS subquery joining
    ``conversation_labels`` -> ``labels`` filtered by title."""
    sub = (
        select(ConversationLabel.id)
        .join(Label, Label.id == ConversationLabel.label_id)
        .where(ConversationLabel.conversation_id == Conversation.id)
    )
    if operator == "is_present":
        return Conversation.id.in_(  # type: ignore[attr-defined]
            select(ConversationLabel.conversation_id)
        )
    if operator == "is_not_present":
        return Conversation.id.not_in(  # type: ignore[attr-defined]
            select(ConversationLabel.conversation_id)
        )
    titles = [v.lower() for v in values]
    titled = sub.where(Label.title.in_(titles))  # type: ignore[attr-defined]
    if operator == "equal_to":
        return Conversation.id.in_(  # type: ignore[attr-defined]
            titled.with_only_columns(ConversationLabel.conversation_id)
        )
    if operator == "not_equal_to":
        return Conversation.id.not_in(  # type: ignore[attr-defined]
            titled.with_only_columns(ConversationLabel.conversation_id)
        )
    raise _err(400, f"Unsupported operator for labels: {operator}")


def _build_clause(condition: dict[str, Any]) -> ColumnElement[Any]:
    """Convert one condition dict into a SQLAlchemy boolean expression."""
    attr = condition.get("attribute_key")
    operator = condition.get("filter_operator")
    values = condition.get("values") or []

    if not isinstance(attr, str):
        raise _err(400, "attribute_key is required")
    if attr not in _ALLOWED_OPERATORS:
        raise _err(
            400,
            f"Unsupported attribute: {attr} "
            f"(allowed: {sorted(_ALLOWED_OPERATORS)})",
        )
    if not isinstance(operator, str) or operator not in _ALLOWED_OPERATORS[attr]:
        raise _err(
            400,
            f"Operator {operator!r} not allowed for {attr} "
            f"(allowed: {sorted(_ALLOWED_OPERATORS[attr])})",
        )
    if operator in _VALUE_REQUIRED_OPS:
        if not isinstance(values, list) or not values:
            raise _err(400, f"values is required for {attr} {operator}")

    if attr == "labels":
        return _build_label_clause(operator=operator, values=[str(v) for v in values])

    column = _column_for(attr)

    if operator == "is_present":
        return column.is_not(None)  # type: ignore[no-any-return]
    if operator == "is_not_present":
        return column.is_(None)  # type: ignore[no-any-return]

    # Coerce values per attribute datatype.
    coerced: list[Any]
    if attr == "status":
        coerced = _coerce_status_values(values)
    elif attr == "priority":
        coerced = _coerce_priority_values(values)
    elif attr in ("assignee_id", "inbox_id", "team_id"):
        coerced = _coerce_int_values(values, attr=attr)
    elif attr in _DATE_ATTRS:
        coerced = _coerce_date_values(values, attr=attr)
    else:  # pragma: no cover — guarded by allow-list above
        coerced = list(values)

    # Date columns get cast to ::date so equality compares calendar days
    # (mirrors Rails' ``(table.col)::date = :v_n``).
    expr_left: Any = (
        func.date(column) if attr in _DATE_ATTRS else column
    )

    if operator == "equal_to":
        return expr_left.in_(coerced)  # type: ignore[no-any-return]
    if operator == "not_equal_to":
        return expr_left.not_in(coerced)  # type: ignore[no-any-return]
    if operator == "contains":
        return or_(
            *[expr_left.ilike(f"%{v}%") for v in coerced]
        )
    if operator == "does_not_contain":
        return and_(
            *[expr_left.not_ilike(f"%{v}%") for v in coerced]
        )
    raise _err(400, f"Unsupported operator: {operator}")


def _validate_query_operator(value: Any) -> None:
    if value is None or value == "":
        return
    if str(value).upper() not in ("AND", "OR"):
        raise _err(
            400, f"Invalid query_operator: {value!r} (allowed: AND, OR)"
        )


def _combine(clauses: list[ColumnElement[Any]], ops: list[str]) -> ColumnElement[Any]:
    """Combine clauses left-to-right honouring per-step operator.

    Mirrors Rails' string-concatenation pattern: each condition carries
    a ``query_operator`` that joins it with the *next* condition. The
    last condition has no operator. We collapse to nested ``and_``/``or_``
    by applying the operator between condition ``i`` and ``i+1``.

    Rails (and us) does NOT honour boolean precedence — left-to-right
    only. ``A AND B OR C`` becomes ``(A AND B) OR C``.
    """
    if not clauses:
        # Defensive — caller should have raised earlier.
        return and_()  # always-true
    out: ColumnElement[Any] = clauses[0]
    for idx in range(1, len(clauses)):
        op = ops[idx - 1].upper() if idx - 1 < len(ops) else "AND"
        if op == "OR":
            out = or_(out, clauses[idx])
        else:
            out = and_(out, clauses[idx])
    return out


async def conversation_filter(
    session: AsyncSession,
    *,
    account_id: int,
    current_user_id: int,
    payload: list[dict[str, Any]],
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> dict[str, Any]:
    """Run a filter-DSL request and return ``{conversations, count}``.

    Mirrors ``Conversations::FilterService#perform``. ``payload`` is the
    array of condition dicts the controller receives — Rails calls it
    ``params[:payload]``.
    """
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

    base = (
        select(Conversation)
        .where(Conversation.account_id == account_id)
        .where(where_expr)
    )
    base = await apply_permission_scope(
        base,
        session=session,
        account_id=account_id,
        current_user_id=current_user_id,
    )
    count_base = (
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.account_id == account_id)
        .where(where_expr)
    )
    count_base = await apply_permission_scope(
        count_base,
        session=session,
        account_id=account_id,
        current_user_id=current_user_id,
    )

    all_count = int((await session.exec(count_base)).one() or 0)
    mine_count = int(
        (
            await session.exec(
                count_base.where(Conversation.assignee_id == current_user_id)  # type: ignore[arg-type]
            )
        ).one()
        or 0
    )
    unassigned_count = int(
        (
            await session.exec(
                count_base.where(Conversation.assignee_id.is_(None))  # type: ignore[attr-defined]
            )
        ).one()
        or 0
    )
    assigned_count = all_count - unassigned_count

    listed = (
        base.order_by(Conversation.last_activity_at.desc())  # type: ignore[attr-defined]
        .offset((max(page, 1) - 1) * per_page)
        .limit(per_page)
    )
    rows = list((await session.exec(listed)).all())

    return {
        "conversations": rows,
        "count": {
            "mine_count": mine_count,
            "assigned_count": assigned_count,
            "unassigned_count": unassigned_count,
            "all_count": all_count,
        },
    }


__all__ = ["conversation_filter"]
