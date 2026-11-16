"""WhatsApp and the Meta catalogue (F5 + F11).

The CRM keeps the account's products in a Meta catalogue
(:mod:`app.domains.crm.meta_catalog`, which records each product's
``meta_retailer_id``). This module uses it on WhatsApp:

  * **Send products** in a chat: one product (``interactive.type=product``)
    or a list (``product_list``, up to 30). The message carries
    ``content_attributes["whatsapp_products"]``; the outbound sender turns
    it into the interactive message. Only inside the 24 h window (Meta
    refuses product messages outside it).
  * **Orders**: a contact's cart arrives as an ``order`` message. It is
    stored with ``content_attributes["whatsapp_order"]`` (items matched to
    our products, total) and opens an opportunity in the default pipeline.
  * **Commerce settings** of the number (catalogue shown on the profile,
    cart on) and linking the catalogue to the WhatsApp Business Account.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import ChatwootHTTPException
from app.domains.conversations.models import Conversation, Message
from app.domains.inboxes.models import WhatsappChannel
from app.domains.products.models import Product

log = logging.getLogger(__name__)

PRODUCTS_KEY = "whatsapp_products"
ORDER_KEY = "whatsapp_order"
MAX_LIST_ITEMS = 30
_SECTION_TITLE_MAX = 24
_HEADER_MAX = 60
_BODY_MAX = 1024


def _unprocessable(message: str) -> ChatwootHTTPException:
    return ChatwootHTTPException(status_code=422, detail={"message": message})


async def catalog_id_for(session: AsyncSession, account_id: int) -> str | None:
    from app.domains.crm.meta_catalog import get_link

    hook = await get_link(session, account_id)
    if hook is None:
        return None
    catalog_id = (hook.settings or {}).get("catalog_id")
    return str(catalog_id) if catalog_id else None


def is_sendable(product: Product) -> bool:
    """In the catalogue and accepted by Meta."""
    return bool(
        product.enabled
        and product.meta_retailer_id
        and product.meta_synced_at
        and not product.meta_sync_error
    )


async def sendable_products(session: AsyncSession, account_id: int) -> list[Product]:
    rows = (
        await session.exec(
            select(Product)
            .where(Product.account_id == account_id)
            .order_by(Product.name)  # type: ignore[arg-type]
        )
    ).all()
    return [p for p in rows if is_sendable(p)]


def present_product(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": float(product.price) if product.price is not None else None,
        "currency": product.currency,
        "image_url": product.image_url,
        "url": product.url,
        "retailer_id": product.meta_retailer_id,
    }


def _format_price(amount: Decimal | float | None, currency: str | None) -> str:
    if amount is None:
        return ""
    value = f"{float(amount):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if value.endswith(",00"):
        value = value[:-3]
    return f"{currency or ''} {value}".strip()


# ---------------------------------------------------------------------------
# Sending products
# ---------------------------------------------------------------------------
async def build_products_message(
    session: AsyncSession,
    *,
    account_id: int,
    product_ids: list[int],
    body: str | None,
    header: str | None,
) -> tuple[str, dict[str, Any]]:
    """``(content, content_attributes)`` of an outgoing products message.
    422 when the catalogue isn't connected or a product isn't in it."""
    catalog_id = await catalog_id_for(session, account_id)
    if not catalog_id:
        raise _unprocessable(
            "La cuenta no tiene un catálogo de Meta conectado (CRM → Productos)."
        )
    ids = list(dict.fromkeys(i for i in product_ids if isinstance(i, int)))
    if not ids:
        raise _unprocessable("Elegí al menos un producto.")
    if len(ids) > MAX_LIST_ITEMS:
        raise _unprocessable(f"Se pueden mandar hasta {MAX_LIST_ITEMS} productos juntos.")
    rows = {
        p.id: p
        for p in (
            await session.exec(
                select(Product).where(
                    Product.account_id == account_id,
                    Product.id.in_(ids),  # type: ignore[union-attr]
                )
            )
        ).all()
    }
    products = [rows[i] for i in ids if i in rows]
    if len(products) != len(ids) or not all(is_sendable(p) for p in products):
        raise _unprocessable(
            "Algún producto no está en el catálogo de Meta: revisalo en CRM → Productos."
        )
    body = (body or "").strip()[:_BODY_MAX]
    header = (header or "").strip()[:_HEADER_MAX]
    if len(products) > 1:
        header = header or "Nuestras propuestas"
        body = body or "Elegí lo que te interese y mandanos tu pedido."
    lines = [
        f"• {p.name}" + (f" — {_format_price(p.price, p.currency)}" if p.price is not None else "")
        for p in products
    ]
    content = "\n".join([*([header] if header else []), *([body] if body else []), *lines])
    attrs = {
        PRODUCTS_KEY: {
            "catalog_id": catalog_id,
            "header": header or None,
            "body": body or None,
            "items": [present_product(p) for p in products],
        }
    }
    return content, attrs


def interactive_for(spec: dict[str, Any]) -> dict[str, Any] | None:
    """The ``interactive`` object Meta takes for a products message."""
    items = [i for i in spec.get("items") or [] if isinstance(i, dict) and i.get("retailer_id")]
    catalog_id = spec.get("catalog_id")
    if not items or not catalog_id:
        return None
    if len(items) == 1:
        out: dict[str, Any] = {
            "type": "product",
            "action": {
                "catalog_id": str(catalog_id),
                "product_retailer_id": str(items[0]["retailer_id"]),
            },
        }
        if spec.get("body"):
            out["body"] = {"text": spec["body"]}
        return out
    return {
        "type": "product_list",
        "header": {"type": "text", "text": spec.get("header") or "Nuestras propuestas"},
        "body": {"text": spec.get("body") or "Elegí lo que te interese."},
        "action": {
            "catalog_id": str(catalog_id),
            "sections": [
                {
                    "title": (spec.get("header") or "Productos")[:_SECTION_TITLE_MAX],
                    "product_items": [
                        {"product_retailer_id": str(i["retailer_id"])}
                        for i in items[:MAX_LIST_ITEMS]
                    ],
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
async def order_from_message(
    session: AsyncSession, *, account_id: int, msg: dict[str, Any]
) -> tuple[str, dict[str, Any]] | None:
    """``(content, content_attributes)`` for an incoming ``order`` message,
    with each item matched to our product by its retailer id."""
    order = msg.get("order")
    if msg.get("type") != "order" or not isinstance(order, dict):
        return None
    raw_items = [i for i in order.get("product_items") or [] if isinstance(i, dict)]
    retailer_ids = [str(i.get("product_retailer_id") or "") for i in raw_items]
    products = {
        p.meta_retailer_id: p
        for p in (
            await session.exec(
                select(Product).where(
                    Product.account_id == account_id,
                    Product.meta_retailer_id.in_([r for r in retailer_ids if r]),  # type: ignore[union-attr]
                )
            )
        ).all()
    }
    items: list[dict[str, Any]] = []
    total = Decimal(0)
    currency: str | None = None
    for raw, rid in zip(raw_items, retailer_ids, strict=True):
        product = products.get(rid)
        try:
            quantity = int(raw.get("quantity") or 1)
            price = Decimal(str(raw.get("item_price") or 0))
        except (ValueError, ArithmeticError):
            quantity, price = 1, Decimal(0)
        currency = currency or raw.get("currency")
        total += price * quantity
        items.append(
            {
                "retailer_id": rid,
                "product_id": product.id if product else None,
                "name": product.name if product else rid,
                "quantity": quantity,
                "item_price": float(price),
                "currency": raw.get("currency"),
            }
        )
    lines = [
        f"• {i['quantity']} x {i['name']} — {_format_price(i['item_price'], i['currency'])}"
        for i in items
    ]
    note = str(order.get("text") or "").strip()
    content = "\n".join(
        ["🛒 Pedido", *lines, f"Total: {_format_price(total, currency)}", *([note] if note else [])]
    )
    attrs = {
        ORDER_KEY: {
            "catalog_id": order.get("catalog_id"),
            "items": items,
            "total": float(total),
            "currency": currency,
            "note": note or None,
            "opportunity_id": None,
        }
    }
    return content, attrs


async def open_opportunity_for_order(
    session: AsyncSession, *, message: Message, conversation: Conversation
) -> None:
    """An order opens an opportunity in the default pipeline (value = the
    order total, product = the first item). Never raises: the webhook must
    not fail over the CRM."""
    from app.domains.contacts.models import Contact
    from app.domains.crm.service import save_opportunity

    attrs = dict(message.content_attributes or {})
    order = dict(attrs.get(ORDER_KEY) or {})
    if not order:
        return
    try:
        async with session.begin_nested():
            contact = await session.get(Contact, conversation.contact_id)
            items = order.get("items") or []
            first = next((i for i in items if i.get("product_id")), None)
            who = (contact.name if contact else None) or "WhatsApp"
            title = f"Pedido de {who}" + (f": {first['name']}" if first else "")
            payload: dict[str, Any] = {
                "title": title[:255],
                "value": order.get("total") or None,
                "currency": order.get("currency"),
                "contact_id": conversation.contact_id,
                "conversation_id": conversation.id,
                "description": message.content,
            }
            if first:
                payload["product_id"] = first["product_id"]
            opportunity = await save_opportunity(
                session,
                account_id=conversation.account_id,
                opportunity=None,
                payload=payload,
            )
            order["opportunity_id"] = opportunity.id
            attrs[ORDER_KEY] = order
            message.content_attributes = attrs
            session.add(message)
            await session.flush()
    except Exception:
        log.exception(
            "whatsapp.order.opportunity_failed message_id=%s", message.id
        )


# ---------------------------------------------------------------------------
# Commerce settings and linking the catalogue to the WhatsApp account
# ---------------------------------------------------------------------------
async def commerce_status(session: AsyncSession, channel: WhatsappChannel) -> dict[str, Any]:
    from app.domains.whatsapp.business import _phone_number_id
    from app.domains.whatsapp.templates import _graph_call, _waba

    pnid = _phone_number_id(channel)
    waba, _ = _waba(channel)
    settings = await _graph_call(channel, "GET", f"{pnid}/whatsapp_commerce_settings")
    rows = settings.get("data")
    row = rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else {}
    linked: list[str] = []
    try:
        catalogs = await _graph_call(channel, "GET", f"{waba}/product_catalogs")
        linked = [str(c.get("id")) for c in catalogs.get("data") or [] if isinstance(c, dict)]
    except ChatwootHTTPException:
        pass
    account_catalog = await catalog_id_for(session, channel.account_id)
    return {
        "account_catalog_id": account_catalog,
        "linked_catalog_ids": linked,
        "catalog_linked": bool(account_catalog and account_catalog in linked),
        "is_catalog_visible": bool(row.get("is_catalog_visible")),
        "is_cart_enabled": bool(row.get("is_cart_enabled")),
        "products_ready": len(await sendable_products(session, channel.account_id)),
    }


async def update_commerce(
    session: AsyncSession,
    channel: WhatsappChannel,
    *,
    is_catalog_visible: bool | None,
    is_cart_enabled: bool | None,
) -> dict[str, Any]:
    from app.domains.whatsapp.business import _phone_number_id
    from app.domains.whatsapp.templates import _graph_call

    pnid = _phone_number_id(channel)
    params: dict[str, Any] = {}
    if is_catalog_visible is not None:
        params["is_catalog_visible"] = "true" if is_catalog_visible else "false"
    if is_cart_enabled is not None:
        params["is_cart_enabled"] = "true" if is_cart_enabled else "false"
    if params:
        await _graph_call(channel, "POST", f"{pnid}/whatsapp_commerce_settings", params=params)
    return await commerce_status(session, channel)


async def link_catalog(session: AsyncSession, channel: WhatsappChannel) -> dict[str, Any]:
    """Connect the account's catalogue to the number's WhatsApp Business
    Account (Meta needs it before product messages can be sent)."""
    from app.domains.whatsapp.templates import _graph_call, _waba

    waba, _ = _waba(channel)
    catalog_id = await catalog_id_for(session, channel.account_id)
    if not catalog_id:
        raise _unprocessable(
            "La cuenta no tiene un catálogo de Meta conectado (CRM → Productos)."
        )
    await _graph_call(
        channel, "POST", f"{waba}/product_catalogs", json={"catalog_id": catalog_id}
    )
    return await commerce_status(session, channel)


__all__ = [
    "ORDER_KEY",
    "PRODUCTS_KEY",
    "build_products_message",
    "commerce_status",
    "interactive_for",
    "link_catalog",
    "open_opportunity_for_order",
    "order_from_message",
    "present_product",
    "sendable_products",
    "update_commerce",
]
