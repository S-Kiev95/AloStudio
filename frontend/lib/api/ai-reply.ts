import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** The answer AloStudio's AI proposes in shadow mode (PLAN.agente-ia.md,
 *  2b): it waits above the composer until someone uses or discards it. With
 *  ``handoff`` the AI would hand the conversation to a person, and
 *  ``summary`` says why. */
export type AiSuggestion = {
  id: number;
  content: string | null;
  summary: string | null;
  handoff: boolean;
  /** What it would also do (book, save data…): a person does it. */
  actions: string[];
  created_at: string | null;
};

function url(accountId: string, displayId: number): string {
  return `/api/v1/accounts/${accountId}/conversations/${displayId}/ai_reply`;
}

// Under "conversation": every cable event refetches it (``use-cable``).
function key(accountId: string, displayId: number) {
  return ["conversation", accountId, displayId, "ai-reply"] as const;
}

export function useAiSuggestion(accountId: string, displayId: number) {
  return useQuery({
    queryKey: key(accountId, displayId),
    queryFn: () => apiFetch<{ ai_reply: AiSuggestion | null }>(url(accountId, displayId)),
    select: (data) => data.ai_reply,
  });
}

export function useDiscardAiSuggestion(accountId: string, displayId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<{ ai_reply: null }>(`${url(accountId, displayId)}/${id}/discard`, {
        method: "POST",
      }),
    onSettled: () => qc.invalidateQueries({ queryKey: key(accountId, displayId) }),
  });
}
