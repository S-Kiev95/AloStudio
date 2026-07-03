import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export type CampaignType = "ongoing" | "one_off";
export type CampaignStatus = "active" | "completed";

export const CAMPAIGN_TYPES: { value: CampaignType; label: string }[] = [
  { value: "ongoing", label: "Continua (widget web)" },
  { value: "one_off", label: "Puntual (programada)" },
];

/** One entry in the audience array — Chatwoot scopes campaigns by labels. */
export type AudienceEntry = {
  type: "Label" | "Contact";
  id: number;
};

export type Campaign = {
  id: number; // = display_id
  display_id: number;
  title: string | null;
  description: string | null;
  message: string | null;
  sender_id: number | null;
  enabled: boolean;
  account_id: number;
  inbox_id: number | null;
  trigger_rules: Record<string, unknown>;
  campaign_type: CampaignType;
  campaign_status: CampaignStatus;
  audience: AudienceEntry[];
  scheduled_at: string | null;
  trigger_only_during_business_hours: boolean | null;
  template_params: Record<string, unknown> | null;
  created_at: number | null;
};

export type CampaignInput = {
  title: string;
  description?: string | null;
  message?: string | null;
  inbox_id?: number | null;
  sender_id?: number | null;
  enabled?: boolean;
  campaign_type?: CampaignType;
  scheduled_at?: string | null;
  audience?: AudienceEntry[];
  trigger_rules?: Record<string, unknown>;
  trigger_only_during_business_hours?: boolean | null;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/campaigns`;
}

export function useCampaigns(accountId: string) {
  return useQuery({
    queryKey: ["campaigns", accountId],
    queryFn: () => apiFetch<Campaign[]>(base(accountId)),
  });
}

export function useCampaign(accountId: string, displayId: number) {
  return useQuery({
    queryKey: ["campaign", accountId, displayId],
    queryFn: () => apiFetch<Campaign>(`${base(accountId)}/${displayId}`),
    enabled: Number.isFinite(displayId),
  });
}

/** Per-campaign delivery metrics (conversations + message-status breakdown). */
export type CampaignAnalytics = {
  campaign_id: number;
  audience_count: number;
  conversations_count: number;
  messages_count: number;
  delivery: {
    sent: number;
    delivered: number;
    read: number;
    failed: number;
  };
};

export function useCampaignAnalytics(accountId: string, displayId: number) {
  return useQuery({
    queryKey: ["campaign-analytics", accountId, displayId],
    queryFn: () =>
      apiFetch<CampaignAnalytics>(
        `${base(accountId)}/${displayId}/analytics`,
      ),
    enabled: Number.isFinite(displayId),
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["campaigns", accountId] });
  qc.invalidateQueries({ queryKey: ["campaign", accountId] });
}

export function useCreateCampaign(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CampaignInput) =>
      apiFetch<Campaign>(base(accountId), {
        method: "POST",
        body: JSON.stringify({ campaign: input }),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateCampaign(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { displayId: number; patch: CampaignInput }) =>
      apiFetch<Campaign>(`${base(accountId)}/${input.displayId}`, {
        method: "PATCH",
        body: JSON.stringify({ campaign: input.patch }),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteCampaign(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (displayId: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${displayId}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}
