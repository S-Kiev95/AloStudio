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

/** Who decides: the decisions service (Jev, or Laya later) or the model
 *  running on this server (Qwen: free, slower, reads the business context). */
export type DecisionProvider = "api" | "local";

export type DecisionSettings = {
  enabled: boolean;
  provider?: DecisionProvider;
  /** What the installation has set up, per provider. */
  providers?: Record<DecisionProvider, boolean>;
  /** The chosen provider is set up. */
  configured: boolean;
  model: string;
  /** The model each provider uses (the chosen one's is shown). */
  models?: Partial<Record<DecisionProvider, string | null>>;
  /** What the local model has to know about the business. */
  context?: string;
  /** The urgency sets the conversation's priority (never a person's). */
  apply_priority?: boolean;
  questions: DecisionQuestion[];
};

export type DecisionSettingsInput = {
  enabled: boolean;
  questions?: DecisionQuestion[];
  provider?: DecisionProvider;
  context?: string;
  apply_priority?: boolean;
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
  /** The automatic priority: conversations where the AI set it, and where
   *  someone (a person, a rule) changed it afterwards. */
  priority?: { set_by_ai: number; changed_by_others: number };
};

export type LabelingItem = {
  conversation_id: number;
  text: string;
  questions: DecisionQuestion[];
  answered: Record<string, string>;
};

/** The team question's key: its options are the account's teams. */
export const TEAM_QUESTION = "team";

/** The urgency options that set the conversation's priority. */
export const URGENCY_QUESTION = "urgency";
export const PRIORITY_BY_URGENCY: Record<string, "low" | "medium" | "high" | "urgent"> = {
  baja: "low",
  media: "medium",
  alta: "high",
  urgente: "urgent",
};

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
    mutationFn: (body: DecisionSettingsInput) =>
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
