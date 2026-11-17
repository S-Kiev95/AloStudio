import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Meta's Conversions API for WhatsApp (F17): which ad conversations
 *  became leads or sales. */
export const CONVERSION_EVENTS = ["LeadSubmitted", "QualifiedLead", "Purchase"] as const;
export type ConversionEventName = (typeof CONVERSION_EVENTS)[number];

export const CRM_TRIGGERS = [
  "opportunity_created",
  "opportunity_qualified",
  "opportunity_won",
] as const;
export type CrmTrigger = (typeof CRM_TRIGGERS)[number];

export type ClosingRule = { event: ConversionEventName; value: number | null };

export type ConversionRules = Record<CrmTrigger, ConversionEventName | null> & {
  closing: Record<string, ClosingRule>;
};

export type ConversionSettings = {
  enabled: boolean;
  currency: string;
  rules: ConversionRules;
  inboxes: Array<{ inbox_id: number; name: string; dataset_id: string | null }>;
};

export type ConversionEvent = {
  id: number;
  conversation_id: number;
  event_name: ConversionEventName;
  trigger: string;
  detail: string | null;
  value: number | null;
  currency: string | null;
  status: "pending" | "sent" | "failed";
  error: string | null;
  created_at: string;
  sent_at: string | null;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/conversions`;
}

function settingsKey(accountId: string) {
  return ["conversions", accountId, "settings"] as const;
}

export function useConversionSettings(accountId: string) {
  return useQuery({
    queryKey: settingsKey(accountId),
    queryFn: () => apiFetch<ConversionSettings>(`${base(accountId)}/settings`),
  });
}

export function useSaveConversionSettings(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { enabled: boolean; currency: string; rules: ConversionRules }) =>
      apiFetch<ConversionSettings>(`${base(accountId)}/settings`, {
        method: "PUT",
        body: JSON.stringify(input),
      }),
    onSuccess: (saved) => qc.setQueryData(settingsKey(accountId), saved),
  });
}

/** Ask Meta for a WhatsApp number's dataset. */
export function useConnectDataset(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (inboxId: number) =>
      apiFetch<ConversionSettings>(`${base(accountId)}/inboxes/${inboxId}/dataset`, {
        method: "POST",
      }),
    onSuccess: (saved) => qc.setQueryData(settingsKey(accountId), saved),
  });
}

export function useConversionEvents(accountId: string) {
  return useQuery({
    queryKey: ["conversions", accountId, "events"] as const,
    queryFn: () =>
      apiFetch<{ payload: ConversionEvent[] }>(`${base(accountId)}/events`).then((r) => r.payload),
    refetchInterval: 60_000,
  });
}

/** Our wording for a refusal, and Meta's words when it gave them. */
export function conversionProblem(err: unknown): { key: string; meta: string | null } {
  const body = (err as { body?: { code?: unknown; message?: unknown } })?.body;
  const code = typeof body?.code === "string" ? body.code : "";
  const key = code.startsWith("conversions.")
    ? `conversions.problems.${code.slice(12)}`
    : "conversions.problems.failed";
  const meta =
    typeof body?.message === "string" && body.message !== code.slice(12) ? body.message : null;
  return { key, meta };
}
