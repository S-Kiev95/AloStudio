"""Polar (polar.sh) — the payment provider and Merchant of Record (F2 paso 3).

  * Plans are Polar *products*; we read them from Polar, nothing to keep
    in sync here.
  * Paying: a checkout session for one product, with our account id as
    Polar's ``external_customer_id`` and in ``metadata``, so every webhook
    says which account it is about.
  * Managing the plan (card, cancel): Polar's customer portal.
  * Webhooks are signed with Standard Webhooks
    (``webhook-id`` / ``webhook-timestamp`` / ``webhook-signature``).
    Secrets from 2026-09-08 on are standard ``whsec_<base64 key>``; older
    ones are HMAC'd with the whole ``whsec_…`` string as key. Both are
    accepted, like Polar's own SDK does.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException

log = logging.getLogger(__name__)

_TOLERANCE_SECONDS = 5 * 60


def api_base() -> str:
    server = (get_settings().polar_server or "sandbox").strip().lower()
    return "https://api.polar.sh/v1" if server == "production" else "https://sandbox-api.polar.sh/v1"


def _unprocessable(message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=422, detail={"message": message})


class PolarRejected(ChatwootHTTPException):
    """Polar answered 4xx; ``fields`` are the request fields its validation
    named (``customer_email``…), so a caller can retry without one."""

    def __init__(self, message: str, fields: frozenset[str]) -> None:
        super().__init__(status_code=422, detail={"message": message})
        self.fields = fields


async def _call(method: str, path: str, *, json: dict[str, Any] | None = None,
                params: dict[str, Any] | None = None) -> Any:
    token = get_settings().polar_access_token
    if not token:
        raise _unprocessable("Falta configurar POLAR_ACCESS_TOKEN (Ajustes → Instalación).")
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.request(
                method,
                f"{api_base()}{path}",
                json=json,
                params=params,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        raise _unprocessable("Polar no respondió. Probá de nuevo en un rato.") from exc
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail")
        except ValueError:
            detail = None
        log.warning("billing.polar.error %s %s status=%s detail=%s", method, path, resp.status_code, detail)
        raise PolarRejected(
            _detail_message(detail) or "Polar rechazó el pedido.", _detail_fields(detail)
        )
    return resp.json() if resp.content else {}


def _validation_items(detail: Any) -> list[dict[str, Any]]:
    if not isinstance(detail, list):
        return []
    return [i for i in detail if isinstance(i, dict) and i.get("msg") and i.get("type") != "missing"]


def _detail_fields(detail: Any) -> frozenset[str]:
    return frozenset(str(i["loc"][-1]) for i in _validation_items(detail) if i.get("loc"))


def _detail_message(detail: Any) -> str | None:
    """Polar's ``detail``: a string, or a validation list ``[{loc, msg}]``.
    Its ``missing`` entries come from the request shapes it did not pick
    (one product vs. several), not from ours."""
    if isinstance(detail, str):
        return detail
    msgs = dict.fromkeys(str(i["msg"]) for i in _validation_items(detail))
    return "; ".join(msgs) or None


def _price_of(product: dict[str, Any]) -> dict[str, Any]:
    prices = [p for p in product.get("prices") or [] if isinstance(p, dict) and not p.get("is_archived")]
    price = prices[0] if prices else {}
    return {
        "amount": (price.get("price_amount") or 0) / 100 if price.get("price_amount") is not None else None,
        "currency": (price.get("price_currency") or "").upper() or None,
        "interval": product.get("recurring_interval"),
    }


_TRIAL_UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


def _trial_days(product: dict[str, Any]) -> int | None:
    """The free trial as days (Polar keeps unit + count), or None."""
    unit = _TRIAL_UNIT_DAYS.get(str(product.get("trial_interval") or ""))
    count = product.get("trial_interval_count")
    if unit is None or not isinstance(count, int) or count <= 0:
        return None
    return unit * count


async def list_plans() -> list[dict[str, Any]]:
    """The active recurring products of the organisation, cheapest first."""
    body = await _call("GET", "/products/", params={"is_archived": "false", "is_recurring": "true", "limit": 100})
    items = body.get("items") if isinstance(body, dict) else None
    plans = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "description": p.get("description"),
            "trial_days": _trial_days(p),
            **_price_of(p),
        }
        for p in items or []
        if isinstance(p, dict) and p.get("id")
    ]
    return sorted(plans, key=lambda p: (p["amount"] is None, p["amount"] or 0))


CREDITS_KIND = "ai_credits"


async def credits_product_id() -> str:
    """The one-time "Créditos de IA" product (metadata ``kind: ai_credits``,
    a pay-what-you-want price)."""
    body = await _call("GET", "/products/", params={"is_archived": "false", "is_recurring": "false", "limit": 100})
    for p in (body.get("items") if isinstance(body, dict) else None) or []:
        metadata = p.get("metadata") if isinstance(p, dict) else None
        if isinstance(metadata, dict) and str(metadata.get("kind", "")).strip() == CREDITS_KIND:
            return str(p["id"])
    raise _unprocessable("Falta crear en Polar el producto de créditos (metadata kind: ai_credits).")


async def create_checkout(
    *,
    account_id: int,
    product_id: str,
    customer_email: str | None,
    success_url: str,
    amount_cents: int | None = None,
    allow_trial: bool = True,
) -> str:
    """``amount_cents`` sets the amount of a pay-what-you-want price;
    ``allow_trial=False`` leaves out the product's free trial."""
    payload: dict[str, Any] = {
        "products": [product_id],
        "external_customer_id": str(account_id),
        "customer_email": customer_email or None,
        "success_url": success_url,
        "metadata": {"account_id": str(account_id)},
    }
    if amount_cents is not None:
        payload["amount"] = amount_cents
    if not allow_trial:
        payload["allow_trial"] = False
    try:
        body = await _call("POST", "/checkouts/", json=payload)
    except PolarRejected as exc:
        # The email only pre-fills Polar's form, and Polar refuses one whose
        # domain takes no mail: let the client type it there instead.
        if exc.fields != {"customer_email"}:
            raise
        body = await _call("POST", "/checkouts/", json={**payload, "customer_email": None})
    url = body.get("url") if isinstance(body, dict) else None
    if not url:
        raise _unprocessable("Polar no devolvió el enlace de pago.")
    return str(url)


async def customer_portal_url(*, account_id: int) -> str:
    body = await _call("POST", "/customer-sessions/", json={"external_customer_id": str(account_id)})
    url = body.get("customer_portal_url") if isinstance(body, dict) else None
    if not url:
        raise _unprocessable("Polar no devolvió el enlace del portal.")
    return str(url)


# ---------------------------------------------------------------------------
# Webhook signatures (Standard Webhooks)
# ---------------------------------------------------------------------------
def _keys(secret: str) -> list[bytes]:
    keys = [secret.encode("utf-8")]  # legacy Polar HMAC: the whole string
    raw = secret.removeprefix("whsec_")
    with contextlib.suppress(ValueError):  # binascii.Error is a ValueError
        keys.insert(0, base64.b64decode(raw, validate=True))
    return keys


def verify_signature(
    *, body: bytes, webhook_id: str, timestamp: str, signature: str, secret: str,
    now: float | None = None,
) -> bool:
    """True when one of the ``v1,<base64>`` signatures matches and the
    timestamp is within five minutes (replays are refused)."""
    if not (body is not None and webhook_id and timestamp and signature and secret):
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs((now or time.time()) - ts) > _TOLERANCE_SECONDS:
        return False
    signed = f"{webhook_id}.{timestamp}.".encode() + body
    given = [part.split(",", 1)[1] for part in signature.split() if part.startswith("v1,")]
    for key in _keys(secret):
        expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
        if any(hmac.compare_digest(expected, g) for g in given):
            return True
    return False


__all__ = ["api_base", "create_checkout", "customer_portal_url", "list_plans", "verify_signature"]
