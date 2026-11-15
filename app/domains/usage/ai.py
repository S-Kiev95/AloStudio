"""AI usage per account (F6).

The OpenAI calls live in :mod:`app.core.llm`, which knows nothing about
accounts. A caller that does know marks the stretch of code with
:func:`ai_usage` (its session, the account and what the call is for); every
call inside records one :class:`UsageRecord` in that session, so it commits or
rolls back with the caller's work. Calls outside any scope are not recorded.

Prices: OpenAI list prices in USD per 1M tokens, standard tier, read on
2026-11-14 at https://developers.openai.com/api/docs/pricing. A model not in
the table is recorded with its tokens and no cost.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.domains.usage.models import KIND_AI, UsageRecord

log = logging.getLogger(__name__)

# model -> (input, cached input, output), USD per 1M tokens.
PRICES_USD_PER_MILLION: dict[str, tuple[Decimal, Decimal, Decimal]] = {
    "gpt-5.4-mini": (Decimal("0.75"), Decimal("0.075"), Decimal("4.50")),
    "gpt-4o": (Decimal("2.50"), Decimal("1.25"), Decimal("10.00")),
    "text-embedding-3-small": (Decimal("0.02"), Decimal("0.02"), Decimal("0")),
}
PRICES_CHECKED_ON = "2026-11-14"

_scope: ContextVar[tuple[AsyncSession, int, str] | None] = ContextVar(
    "ai_usage_scope", default=None
)


@contextmanager
def ai_usage(session: AsyncSession, account_id: int | None, purpose: str) -> Iterator[None]:
    """Record the AI calls made inside this block for ``account_id``."""
    if account_id is None:
        yield
        return
    token = _scope.set((session, account_id, purpose))
    try:
        yield
    finally:
        _scope.reset(token)


def cost_of(
    model: str, *, input_tokens: int, cached_tokens: int, output_tokens: int
) -> Decimal | None:
    prices = PRICES_USD_PER_MILLION.get(model)
    if prices is None:
        # Dated snapshots (``gpt-4o-2024-08-06``) bill like their family.
        prices = next(
            (p for name, p in PRICES_USD_PER_MILLION.items() if model.startswith(f"{name}-")),
            None,
        )
    if prices is None:
        return None
    price_in, price_cached, price_out = prices
    fresh = max(input_tokens - cached_tokens, 0)
    total = fresh * price_in + cached_tokens * price_cached + output_tokens * price_out
    return (total / Decimal(1_000_000)).quantize(Decimal("0.000001"))


async def ai_budget_reached() -> bool:
    """Whether the account of the current scope reached its AI spend cap.
    False outside a scope or without a cap."""
    scope = _scope.get()
    if scope is None:
        return False
    from app.domains.usage.limits import limit_reached

    session, account_id, _ = scope
    return await limit_reached(session, account_id, KIND_AI)


def record_ai_call(model: str, usage: Any) -> None:
    """Called by :mod:`app.core.llm` after each successful request with the
    response's ``usage`` block. No-op outside an :func:`ai_usage` scope;
    never raises (spend tracking must not break a reply)."""
    scope = _scope.get()
    if scope is None or not isinstance(usage, dict):
        return
    session, account_id, purpose = scope
    try:
        input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}
        cached = int(details.get("cached_tokens") or 0) if isinstance(details, dict) else 0
        session.add(
            UsageRecord(
                account_id=account_id,
                kind=KIND_AI,
                occurred_at=datetime.now(UTC),
                category=purpose,
                model=model,
                input_tokens=input_tokens,
                cached_tokens=cached,
                output_tokens=output_tokens,
                cost=cost_of(
                    model,
                    input_tokens=input_tokens,
                    cached_tokens=cached,
                    output_tokens=output_tokens,
                ),
                currency="USD",
            )
        )
    except Exception:
        log.exception("usage.ai.record_failed model=%s", model)


__all__ = ["PRICES_CHECKED_ON", "ai_budget_reached", "ai_usage", "cost_of", "record_ai_call"]
