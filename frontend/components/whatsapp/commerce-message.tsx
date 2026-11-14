"use client";

import { ShoppingBag, ShoppingCart } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import type { Message } from "@/lib/api/conversations";
import {
  formatPrice,
  type WhatsappOrderAttrs,
  type WhatsappProductsAttrs,
} from "@/lib/api/whatsapp-catalog";

/** Products sent from the catalogue, or an order a contact sent back, as
 *  the bubble's body (instead of the plain-text summary in `content`). */
export function CommerceMessage({ message }: { message: Message }) {
  const params = useParams<{ accountId?: string }>();
  const attrs = message.content_attributes ?? {};
  const products = attrs.whatsapp_products as WhatsappProductsAttrs | undefined;
  const order = attrs.whatsapp_order as WhatsappOrderAttrs | undefined;

  if (products?.items?.length) {
    return (
      <div className="space-y-2" data-testid="whatsapp-products-message">
        <p className="flex items-center gap-1.5 text-xs font-semibold opacity-85">
          <ShoppingBag className="h-3.5 w-3.5" aria-hidden />
          {products.header || (products.items.length > 1 ? "Productos" : "Producto")}
        </p>
        {products.body ? <p className="whitespace-pre-wrap break-words">{products.body}</p> : null}
        <ul className="space-y-1.5">
          {products.items.map((item) => (
            <li
              key={item.retailer_id}
              className="flex items-center gap-2.5 rounded-lg bg-black/10 p-1.5 pr-3"
            >
              {item.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element -- product images live on any host
                <img
                  src={item.image_url}
                  alt=""
                  className="h-10 w-10 shrink-0 rounded-md object-cover"
                />
              ) : null}
              <span className="min-w-0">
                <span className="block truncate font-medium">{item.name}</span>
                {item.price != null ? (
                  <span className="block text-xs opacity-85">
                    {formatPrice(item.price, item.currency)}
                  </span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (order?.items) {
    return (
      <div className="space-y-2" data-testid="whatsapp-order-message">
        <p className="flex items-center gap-1.5 text-xs font-semibold">
          <ShoppingCart className="h-3.5 w-3.5" aria-hidden />
          Pedido desde el catálogo
        </p>
        <ul className="space-y-1">
          {order.items.map((item) => (
            <li key={item.retailer_id} className="flex justify-between gap-4">
              <span>
                {item.quantity} × {item.name}
              </span>
              <span className="tabular-nums">
                {formatPrice(item.item_price * item.quantity, item.currency)}
              </span>
            </li>
          ))}
        </ul>
        <p className="flex justify-between gap-4 border-t border-glass pt-1.5 font-semibold">
          <span>Total</span>
          <span className="tabular-nums">{formatPrice(order.total, order.currency)}</span>
        </p>
        {order.note ? <p className="whitespace-pre-wrap break-words">{order.note}</p> : null}
        {order.opportunity_id && params?.accountId ? (
          <Link
            href={`/accounts/${params.accountId}/opportunities`}
            className="inline-block text-xs text-lit underline-offset-2 hover:underline"
          >
            Se abrió una oportunidad en el embudo
          </Link>
        ) : null}
      </div>
    );
  }
  return null;
}

/** Whether the message is a catalogue products message or an order. */
export function isCommerceMessage(message: Message): boolean {
  const attrs = message.content_attributes ?? {};
  return Boolean(attrs.whatsapp_products || attrs.whatsapp_order);
}
