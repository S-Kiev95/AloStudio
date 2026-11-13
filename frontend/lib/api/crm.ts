import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Sales pipeline (F11): pipelines, their stages and opportunities. */
export type StageKind = "open" | "won" | "lost";

export type Stage = {
  id: number;
  /** Seeded stages: ``new`` … ``lost``, named by the dictionary. */
  code: string | null;
  /** Set when someone names the stage; wins over ``code``. */
  name: string | null;
  kind: StageKind;
  probability: number;
  position: number;
};

export type Pipeline = {
  id: number;
  /** Null on the default pipeline: named by the dictionary. */
  name: string | null;
  is_default: boolean;
  rotten_days: number;
  stages: Stage[];
};

export type Opportunity = {
  id: number;
  pipeline_id: number;
  stage_id: number;
  title: string;
  description: string | null;
  value: number | null;
  currency: string | null;
  contact_id: number | null;
  product_id: number | null;
  owner_id: number | null;
  conversation_id: number | null;
  /** ``YYYY-MM-DD`` */
  expected_close_on: string | null;
  closed_at: number | null;
  lost_reason: string | null;
  position: number;
  stage_changed_at: number | null;
  created_at: number | null;
  updated_at: number | null;
  contact: { id: number; name: string | null; avatar_url: string | null } | null;
  product: { id: number; name: string } | null;
  owner: { id: number; name: string } | null;
};

export type OpportunityInput = {
  title?: string;
  description?: string | null;
  value?: number | null;
  currency?: string | null;
  stage_id?: number;
  contact_id?: number | null;
  product_id?: number | null;
  owner_id?: number | null;
  conversation_id?: number | null;
  expected_close_on?: string | null;
  lost_reason?: string | null;
  position?: number;
};

export type StageInput = {
  id?: number;
  name?: string | null;
  kind: StageKind;
  probability: number;
};

export type OpportunityFilters = {
  pipeline_id?: number;
  contact_id?: number;
  owner_id?: number;
  status?: StageKind;
  q?: string;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/crm`;
}

export function usePipelines(accountId: string) {
  return useQuery({
    queryKey: ["crm-pipelines", accountId],
    queryFn: () => apiFetch<Pipeline[]>(`${base(accountId)}/pipelines`),
  });
}

export function useOpportunities(accountId: string, filters: OpportunityFilters = {}) {
  return useQuery({
    queryKey: ["crm-opportunities", accountId, filters],
    queryFn: () => {
      const sp = new URLSearchParams();
      for (const [k, v] of Object.entries(filters)) {
        if (v !== undefined && v !== "") sp.set(k, String(v));
      }
      const qs = sp.toString();
      return apiFetch<Opportunity[]>(`${base(accountId)}/opportunities${qs ? `?${qs}` : ""}`);
    },
  });
}

function invalidate(qc: ReturnType<typeof useQueryClient>, accountId: string) {
  qc.invalidateQueries({ queryKey: ["crm-opportunities", accountId] });
}

export function useCreateOpportunity(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: OpportunityInput) =>
      apiFetch<Opportunity>(`${base(accountId)}/opportunities`, {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateOpportunity(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: OpportunityInput }) =>
      apiFetch<Opportunity>(`${base(accountId)}/opportunities/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify(input.patch),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteOpportunity(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/opportunities/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdatePipeline(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      id: number;
      patch: { name?: string | null; rotten_days?: number; stages?: StageInput[] };
    }) =>
      apiFetch<Pipeline>(`${base(accountId)}/pipelines/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify(input.patch),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["crm-pipelines", accountId] }),
  });
}

/** Whole days since the opportunity last moved — the "stale" flag compares
 *  it with the pipeline's ``rotten_days``. */
export function daysIdle(o: Opportunity, now: number = Date.now()): number {
  const since = o.stage_changed_at ?? o.updated_at ?? o.created_at;
  if (!since) return 0;
  return Math.floor((now / 1000 - since) / 86_400);
}
