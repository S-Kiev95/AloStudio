import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** The month's spend of an account (F6): WhatsApp per Meta, split by
 *  number, category, country and mass send; and the AI calls. */

type Bucket = { volume: number; cost: number };

export type UsageSummary = {
  month: string;
  whatsapp: {
    currency: string | null;
    total_cost: number;
    messages: number;
    billable_messages: number;
    by_category: Array<Bucket & { category: string }>;
    by_country: Array<Bucket & { country: string }>;
    by_inbox: Array<Bucket & { inbox_id: number; name: string | null }>;
    by_day: Array<{ day: string; cost: number }>;
    last_synced_at: number | null;
  };
  campaigns: Array<{
    campaign_id: number | null;
    title: string | null;
    inbox_id: number | null;
    messages: number;
    billable_messages: number;
    estimated_cost: number;
    complete: boolean;
  }>;
  ai: {
    currency: string;
    total_cost: number;
    requests: number;
    prices_checked_on: string;
    items: Array<{
      purpose: string | null;
      model: string | null;
      requests: number;
      input_tokens: number;
      output_tokens: number;
      cost: number;
    }>;
  };
  sync_errors?: Array<{ inbox_id: number; name: string; message: string | null }>;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/usage`;
}

export function useUsageSummary(accountId: string, month: string) {
  return useQuery({
    queryKey: ["usage", accountId, month],
    queryFn: () =>
      apiFetch<UsageSummary>(`${base(accountId)}?month=${encodeURIComponent(month)}`),
    retry: false,
  });
}

export function useSyncWhatsappCosts(accountId: string, month: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<UsageSummary>(
        `${base(accountId)}/whatsapp/sync?month=${encodeURIComponent(month)}`,
        { method: "POST" },
      ),
    onSuccess: (data) => qc.setQueryData(["usage", accountId, month], data),
  });
}

/** `2026-11` → `2026-10` / `2026-12`. */
export function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + delta, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

export function currentMonth(now = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}
