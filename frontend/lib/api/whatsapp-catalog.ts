import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { Message } from "./conversations";
import { apiFetch } from "./fetcher";

/** Products of the account's Meta catalogue on WhatsApp (F5 + F11). */

export type CatalogProduct = {
  id: number;
  name: string;
  description: string | null;
  price: number | null;
  currency: string | null;
  image_url: string | null;
  url: string | null;
  retailer_id: string;
};

export type WhatsappCommerce = {
  account_catalog_id: string | null;
  linked_catalog_ids: string[];
  catalog_linked: boolean;
  is_catalog_visible: boolean;
  is_cart_enabled: boolean;
  products_ready: number;
};

/** What a products message carries (`content_attributes.whatsapp_products`). */
export type WhatsappProductsAttrs = {
  catalog_id: string;
  header: string | null;
  body: string | null;
  items: CatalogProduct[];
};

/** An order a contact sent from the catalogue (`whatsapp_order`). */
export type WhatsappOrderAttrs = {
  catalog_id: string | null;
  items: Array<{
    retailer_id: string;
    product_id: number | null;
    name: string;
    quantity: number;
    item_price: number;
    currency: string | null;
  }>;
  total: number;
  currency: string | null;
  note: string | null;
  opportunity_id: number | null;
};

export function formatPrice(amount: number | null, currency: string | null): string {
  if (amount == null) return "";
  const value = amount.toLocaleString("es-UY", { maximumFractionDigits: 2 });
  return currency ? `${currency} ${value}` : value;
}

export function useCatalogProducts(accountId: string, enabled = true) {
  return useQuery({
    queryKey: ["whatsapp-catalog-products", accountId],
    queryFn: () =>
      apiFetch<{ catalog_id: string | null; products: CatalogProduct[] }>(
        `/api/v1/accounts/${accountId}/whatsapp/catalog/products`,
      ),
    enabled,
    staleTime: 60_000,
  });
}

export function useSendProducts(accountId: string, displayId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { productIds: number[]; body?: string; header?: string }) =>
      apiFetch<Message>(
        `/api/v1/accounts/${accountId}/conversations/${displayId}/whatsapp/products`,
        {
          method: "POST",
          body: JSON.stringify({
            product_ids: input.productIds,
            body: input.body || undefined,
            header: input.header || undefined,
          }),
        },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["messages", accountId, displayId] });
      void qc.invalidateQueries({ queryKey: ["conversations", accountId] });
    },
  });
}

function commerceBase(accountId: string, inboxId: number): string {
  return `/api/v1/accounts/${accountId}/inboxes/${inboxId}/whatsapp/commerce`;
}

export function useWhatsappCommerce(accountId: string, inboxId: number) {
  return useQuery({
    queryKey: ["whatsapp-commerce", accountId, inboxId],
    queryFn: () => apiFetch<WhatsappCommerce>(commerceBase(accountId, inboxId)),
    retry: false,
  });
}

export function useUpdateWhatsappCommerce(accountId: string, inboxId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { is_catalog_visible?: boolean; is_cart_enabled?: boolean }) =>
      apiFetch<WhatsappCommerce>(commerceBase(accountId, inboxId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: (data) => qc.setQueryData(["whatsapp-commerce", accountId, inboxId], data),
  });
}

export function useLinkWhatsappCatalog(accountId: string, inboxId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<WhatsappCommerce>(`${commerceBase(accountId, inboxId)}/link`, {
        method: "POST",
      }),
    onSuccess: (data) => qc.setQueryData(["whatsapp-commerce", accountId, inboxId], data),
  });
}
