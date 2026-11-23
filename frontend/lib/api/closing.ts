import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Why a conversation closes (F17): the account's categories, and whether
 *  the panel asks for one when resolving. */
export type ClosingSettings = {
  enabled: boolean;
  required: boolean;
  categories: string[];
};

export type ClosingReport = {
  days: number;
  total: number;
  /** Most first; ``null`` for closings with a note only. */
  categories: Array<{ category: string | null; count: number }>;
};

export const CATEGORY_MAX = 60;
export const CATEGORIES_MAX = 30;
export const NOTE_MAX = 2000;

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/closing_notes`;
}

function settingsKey(accountId: string) {
  return ["closing", accountId, "settings"] as const;
}

export function useClosingSettings(accountId: string) {
  return useQuery({
    queryKey: settingsKey(accountId),
    queryFn: () => apiFetch<ClosingSettings>(`${base(accountId)}/settings`),
    staleTime: 60_000,
  });
}

export function useSaveClosingSettings(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ClosingSettings) =>
      apiFetch<ClosingSettings>(`${base(accountId)}/settings`, {
        method: "PUT",
        body: JSON.stringify(input),
      }),
    onSuccess: (saved) => qc.setQueryData(settingsKey(accountId), saved),
  });
}

/** Resolve the conversation saying why. */
export function useCloseConversation(accountId: string, displayId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { category: string | null; note: string | null }) =>
      apiFetch<{ status: string; category: string | null; note: string | null }>(
        `${base(accountId)}/${displayId}`,
        { method: "POST", body: JSON.stringify(input) },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversation", accountId, displayId] });
      qc.invalidateQueries({ queryKey: ["conversations", accountId] });
      qc.invalidateQueries({ queryKey: ["messages", accountId] });
    },
  });
}

export function useClosingReport(accountId: string, days: number, enabled = true) {
  return useQuery({
    queryKey: ["closing", accountId, "report", days] as const,
    queryFn: () => apiFetch<ClosingReport>(`${base(accountId)}/report?days=${days}`),
    enabled,
  });
}

/** Our wording for what the backend refused, by its code. */
export function closingProblemKey(err: unknown): string {
  const code = (err as { body?: { code?: unknown } })?.body?.code;
  if (typeof code === "string" && code.startsWith("closing.")) {
    return `closing.problems.${code.slice(8)}`;
  }
  return "closing.problems.failed";
}
