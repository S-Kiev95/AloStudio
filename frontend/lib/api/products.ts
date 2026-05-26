import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Product catalogue row (own-extension, not a Chatwoot mirror). */
export type Product = {
  id: number;
  account_id: number;
  name: string;
  description: string | null;
  sku: string | null;
  price: number | null;
  currency: string | null;
  url: string | null;
  image_url: string | null;
  enabled: boolean;
  created_at: number | null;
};

export type ProductInput = {
  name: string;
  description?: string | null;
  sku?: string | null;
  price?: number | null;
  currency?: string | null;
  url?: string | null;
  image_url?: string | null;
  enabled?: boolean;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/products`;
}

export function useProducts(
  accountId: string,
  filters: { enabled?: boolean; page?: number } = {},
) {
  const { enabled, page } = filters;
  return useQuery({
    queryKey: ["products", accountId, enabled ?? null, page ?? null],
    queryFn: () => {
      const sp = new URLSearchParams();
      if (enabled !== undefined) sp.set("enabled", String(enabled));
      if (page) sp.set("page", String(page));
      const qs = sp.toString();
      return apiFetch<Product[]>(`${base(accountId)}${qs ? `?${qs}` : ""}`);
    },
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["products", accountId] });
}

export function useCreateProduct(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ProductInput) =>
      apiFetch<Product>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateProduct(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: ProductInput }) =>
      apiFetch<Product>(`${base(accountId)}/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify(input.patch),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteProduct(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}
