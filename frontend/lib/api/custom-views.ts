import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { FilterCondition } from "./conversations";
import { apiFetch } from "./fetcher";

export type CustomViewType = "conversation" | "contact";

/** A saved filter-DSL view (backed by the `custom_filters` route). */
export type CustomView = {
  id: number;
  name: string;
  filter_type: CustomViewType;
  query: { payload: FilterCondition[] };
  created_at?: string;
  updated_at?: string;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/custom_filters`;
}

export function useCustomViews(
  accountId: string,
  filterType: CustomViewType = "conversation",
) {
  return useQuery({
    queryKey: ["custom-views", accountId, filterType],
    queryFn: () =>
      apiFetch<CustomView[]>(`${base(accountId)}?filter_type=${filterType}`),
    staleTime: 60_000,
  });
}

export function useCreateCustomView(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      name: string;
      filter_type?: CustomViewType;
      query: { payload: FilterCondition[] };
    }) =>
      apiFetch<CustomView>(base(accountId), {
        method: "POST",
        body: JSON.stringify({ filter_type: "conversation", ...input }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["custom-views", accountId] });
    },
  });
}

export function useDeleteCustomView(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<unknown>(`${base(accountId)}/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["custom-views", accountId] });
    },
  });
}
