import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Label CRUD shape (mirrors the labels jbuilder views). */
export type Label = {
  id: number;
  title: string;
  description?: string | null;
  color?: string | null;
  show_on_sidebar?: boolean | null;
};

export type LabelInput = {
  title: string;
  description?: string | null;
  color?: string | null;
  show_on_sidebar?: boolean | null;
};

/** Chatwoot-style swatch palette for picking a label colour. */
export const LABEL_SWATCHES = [
  "#1f93ff",
  "#1ab8a8",
  "#9b59b6",
  "#e67e22",
  "#e74c3c",
  "#2ecc71",
  "#f1c40f",
  "#34495e",
  "#7f8c8d",
] as const;

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/labels`;
}

/** Returns the labels list — unwrapped from the ``{payload: [...]}`` envelope. */
export function useLabels(accountId: string) {
  return useQuery({
    queryKey: ["labels", accountId],
    queryFn: async () => {
      const res = await apiFetch<{ payload: Label[] }>(base(accountId));
      return res.payload;
    },
    staleTime: 5 * 60_000,
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["labels", accountId] });
}

export function useCreateLabel(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: LabelInput) =>
      apiFetch<Label>(base(accountId), {
        method: "POST",
        body: JSON.stringify({ label: input }),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateLabel(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: LabelInput }) =>
      apiFetch<Label>(`${base(accountId)}/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify({ label: input.patch }),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteLabel(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}
