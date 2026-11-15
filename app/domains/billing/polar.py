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
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import ChatwootHTTPException

_TOLERANCE_SECONDS = 5 * 60


def api_base() -> str:
    server = (get_settings().polar_server or "sandbox").strip().lower()
    return "https://api.polar.sh/v1" if server == "production" else "https://sandbox-api.polar.sh/v1"


def _unprocessable(message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=422, detail={"message": message})


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
        message = detail if isinstance(detail, str) else "Polar rechazó el pedido."
        raise _unprocessable(message)
    return resp.json() if resp.content else {}


def _price_of(product: dict[str, Any]) -> dict[str, Any]:
    prices = [p for p in product.get("prices") or [] if isinstance(p, dict) and not p.get("is_archived")]
    price = prices[0] if prices else {}
    return {
        "amount": (price.get("price_amount") or 0) / 100 if price.get("price_amount") is not None else None,
        "currency": (price.get("price_currency") or "").upper() or None,
        "interval": product.get("recurring_interval"),
    }


async def list_plans() -> list[dict[str, Any]]:
    """The active recurring products of the organisation, cheapest first."""
    body = await _call("GET", "/products/", params={"is_archived": "false", "is_recurring": "true", "limit": 100})
    items = body.get("items") if isinstance(body, dict) else None
    plans = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "description": p.get("description"),
            **_price_of(p),
        }
        for p in items or []
        if isinstance(p, dict) and p.get("id")
    ]
    return sorted(plans, key=lambda p: (p["amount"] is None, p["amount"] or 0))


async def create_checkout(
    *, account_id: int, product_id: str, customer_email: str | None, success_url: str
) -> str:
    body = await _call(
        "POST",
        "/checkouts/",
        json={
            "products": [product_id],
            "external_customer_id": str(account_id),
            "customer_email": customer_email or None,
            "success_url": success_url,
            "metadata": {"account_id": str(account_id)},
        },
    )
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
