import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Who takes a conversation that Meta's agent or AloStudio's AI hands to
 *  the team (PLAN.agente-ia.md, 2a). Administrators only. The most specific
 *  level wins: the chat, then the labels in order, then the inbox's
 *  responsible (Ajustes → Bandejas), then the account's. */
export type HandoffTarget = { user_id: number | null; to_ai: boolean };

export type HandoffLabelRule = HandoffTarget & { label_id: number };

export type HandoffRules = {
  account: HandoffTarget | null;
  labels: HandoffLabelRule[];
  /** Whether AloStudio's AI can be chosen (paso 2b). */
  ai_available: boolean;
};

export type ContactHandoff = { contact: HandoffTarget | null; ai_available: boolean };

export const LABEL_RULES_MAX = 50;

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/handoff`;
}

function rulesKey(accountId: string) {
  return ["handoff", accountId, "rules"] as const;
}

function contactKey(accountId: string, contactId: number) {
  return ["handoff", accountId, "contact", contactId] as const;
}

export function useHandoffRules(accountId: string) {
  return useQuery({
    queryKey: rulesKey(accountId),
    queryFn: () => apiFetch<HandoffRules>(base(accountId)),
    staleTime: 60_000,
  });
}

export function useSaveHandoffRules(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { account: HandoffTarget; labels: HandoffLabelRule[] }) =>
      apiFetch<HandoffRules>(base(accountId), {
        method: "PUT",
        body: JSON.stringify(input),
      }),
    onSuccess: (saved) => qc.setQueryData(rulesKey(accountId), saved),
  });
}

export function useContactHandoff(accountId: string, contactId: number, enabled: boolean) {
  return useQuery({
    queryKey: contactKey(accountId, contactId),
    queryFn: () => apiFetch<ContactHandoff>(`${base(accountId)}/contacts/${contactId}`),
    enabled,
    staleTime: 60_000,
  });
}

export function useSaveContactHandoff(accountId: string, contactId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: HandoffTarget) =>
      apiFetch<{ contact: HandoffTarget | null }>(`${base(accountId)}/contacts/${contactId}`, {
        method: "PUT",
        body: JSON.stringify(input),
      }),
    onSuccess: (saved) =>
      qc.setQueryData<ContactHandoff>(contactKey(accountId, contactId), (old) =>
        old ? { ...old, contact: saved.contact } : old,
      ),
  });
}

/** A target as one select value: "" nobody, "ai" the AI, else a user id. */
export const TARGET_AI = "ai";

export function targetValue(target: HandoffTarget | null | undefined): string {
  if (!target) return "";
  if (target.to_ai) return TARGET_AI;
  return target.user_id ? String(target.user_id) : "";
}

export function targetFromValue(value: string): HandoffTarget {
  if (value === TARGET_AI) return { user_id: null, to_ai: true };
  return { user_id: value ? Number(value) : null, to_ai: false };
}

/** Our wording for what the backend refused, by its code. */
export function handoffProblemKey(err: unknown): string {
  const code = (err as { body?: { code?: unknown } })?.body?.code;
  if (typeof code === "string" && code.startsWith("handoff.")) {
    return `handoff.problems.${code.slice(8)}`;
  }
  return "handoff.problems.failed";
}
