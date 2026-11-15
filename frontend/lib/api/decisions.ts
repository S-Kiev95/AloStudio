import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Decisions about conversations, in shadow mode (F10). */
export type DecisionOption = { key: string; description: string };

export type DecisionQuestion = {
  key: string;
  enabled: boolean;
  instructions: string;
  /** Empty for the team question: its options come from the teams. */
  options: DecisionOption[];
};

export type DecisionSettings = {
  enabled: boolean;
  /** The installation has a decisions service (Jev or Laya) set up. */
  configured: boolean;
  model: string;
  questions: DecisionQuestion[];
};

export type DecisionReport = {
  days: number;
  conversations: number;
  labeled_conversations: number;
  questions: Array<{
    key: string;
    instructions: string;
    options: DecisionOption[];
    decided: number;
    compared: number;
    agreed: number;
    agreement: number | null;
    mean_confidence: number | null;
    answers: Record<string, number>;
  }>;
  month: { calls: number; cost_usd: number };
};

export type LabelingItem = {
  conversation_id: number;
  text: string;
  questions: DecisionQuestion[];
  answered: Record<string, string>;
};

/** The team question's key: its options are the account's teams. */
export const TEAM_QUESTION = "team";

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/decisions`;
}

export function useDecisionSettings(accountId: string) {
  return useQuery({
    queryKey: ["decisions", accountId, "settings"] as const,
    queryFn: () => apiFetch<DecisionSettings>(`${base(accountId)}/settings`),
    retry: false,
  });
}

export function useSaveDecisionSettings(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { enabled: boolean; questions?: DecisionQuestion[] }) =>
      apiFetch<DecisionSettings>(`${base(accountId)}/settings`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: (saved) => qc.setQueryData(["decisions", accountId, "settings"], saved),
  });
}

export function useDecisionReport(accountId: string, enabled = true) {
  return useQuery({
    queryKey: ["decisions", accountId, "report"] as const,
    queryFn: () => apiFetch<DecisionReport>(`${base(accountId)}/report`),
    enabled,
  });
}

export function useNextToLabel(accountId: string, skip: number[], enabled = true) {
  return useQuery({
    queryKey: ["decisions", accountId, "labeling", skip] as const,
    queryFn: () => {
      const params = new URLSearchParams();
      skip.forEach((id) => params.append("skip", String(id)));
      const qs = params.toString();
      return apiFetch<{ payload: LabelingItem | null }>(
        `${base(accountId)}/labeling/next${qs ? `?${qs}` : ""}`,
      ).then((r) => r.payload);
    },
    enabled,
  });
}

export function useSaveLabels(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { conversation_id: number; answers: Record<string, string> }) =>
      apiFetch<{ saved: number }>(`${base(accountId)}/labels`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["decisions", accountId, "labeling"] });
      qc.invalidateQueries({ queryKey: ["decisions", accountId, "report"] });
    },
  });
}
