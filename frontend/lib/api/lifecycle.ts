import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Contact lifecycle (F17): where each contact stands, from new lead to
 *  customer (``lost``: where people drop out). */
export type LifecycleStage = {
  key: string;
  name: string;
  emoji: string;
  description: string;
  kind: "stage" | "lost";
  /** The stage a contact's first message puts them in. */
  default: boolean;
};

export type LifecycleSettings = { enabled: boolean; stages: LifecycleStage[] };

export type ContactStage = {
  stage: LifecycleStage | null;
  changed_at: string | null;
  changed_by: { id: number; name: string } | null;
};

export type LifecycleReport = {
  days: number;
  enabled: boolean;
  stages: Array<{
    key: string;
    name: string;
    emoji: string;
    kind: "stage" | "lost";
    count: number;
    entered: number;
  }>;
};

export const STAGES_MAX = 20;
export const NAME_MAX = 40;
export const DESCRIPTION_MAX = 160;

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/lifecycle`;
}

function settingsKey(accountId: string) {
  return ["lifecycle", accountId, "settings"] as const;
}

function contactKey(accountId: string, contactId: number) {
  return ["lifecycle", accountId, "contact", contactId] as const;
}

export function useLifecycleSettings(accountId: string) {
  return useQuery({
    queryKey: settingsKey(accountId),
    queryFn: () => apiFetch<LifecycleSettings>(`${base(accountId)}/settings`),
    staleTime: 60_000,
  });
}

export function useSaveLifecycleSettings(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { enabled: boolean; stages: Array<Partial<LifecycleStage>> }) =>
      apiFetch<LifecycleSettings>(`${base(accountId)}/settings`, {
        method: "PUT",
        body: JSON.stringify(input),
      }),
    onSuccess: (saved) => {
      qc.setQueryData(settingsKey(accountId), saved);
      qc.invalidateQueries({ queryKey: ["lifecycle", accountId] });
    },
  });
}

export function useContactStage(accountId: string, contactId: number, enabled = true) {
  return useQuery({
    queryKey: contactKey(accountId, contactId),
    queryFn: () => apiFetch<ContactStage>(`${base(accountId)}/contacts/${contactId}`),
    enabled,
  });
}

/** Move the contact; with ``conversationId`` (its number) the chat says so. */
export function useSetContactStage(accountId: string, contactId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { stage_key: string | null; conversation_id?: number }) =>
      apiFetch<ContactStage>(`${base(accountId)}/contacts/${contactId}`, {
        method: "PUT",
        body: JSON.stringify(input),
      }),
    onSuccess: (saved) => {
      qc.setQueryData(contactKey(accountId, contactId), saved);
      qc.invalidateQueries({ queryKey: ["messages", accountId] });
    },
  });
}

export function useLifecycleReport(accountId: string, days: number) {
  return useQuery({
    queryKey: ["lifecycle", accountId, "report", days] as const,
    queryFn: () => apiFetch<LifecycleReport>(`${base(accountId)}/report?days=${days}`),
  });
}

export function lifecycleProblemKey(err: unknown): string {
  const code = (err as { body?: { code?: unknown } })?.body?.code;
  if (typeof code === "string" && code.startsWith("lifecycle.")) {
    return `lifecycle.problems.${code.slice(10)}`;
  }
  return "lifecycle.problems.failed";
}
