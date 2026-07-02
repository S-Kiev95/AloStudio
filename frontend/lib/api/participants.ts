import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { Agent } from "./account";
import { apiFetch } from "./fetcher";

function base(accountId: string, displayId: number): string {
  return `/api/v1/accounts/${accountId}/conversations/${displayId}/participants`;
}

/** GET participants — a bare array of agent objects (the watcher set). */
export function useParticipants(accountId: string, displayId: number) {
  return useQuery({
    queryKey: ["participants", accountId, displayId],
    queryFn: () => apiFetch<Agent[]>(base(accountId, displayId)),
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
  displayId: number,
) {
  qc.invalidateQueries({ queryKey: ["participants", accountId, displayId] });
}

/** POST — add a user to the watcher set; returns the full list. */
export function useAddParticipant(accountId: string, displayId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: number) =>
      apiFetch<Agent[]>(base(accountId, displayId), {
        method: "POST",
        body: JSON.stringify({ user_ids: [userId] }),
      }),
    onSuccess: () => invalidate(qc, accountId, displayId),
  });
}

/** DELETE — drop a user from the watcher set (Rails ``head :ok``). */
export function useRemoveParticipant(accountId: string, displayId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: number) =>
      apiFetch<Record<string, never>>(base(accountId, displayId), {
        method: "DELETE",
        body: JSON.stringify({ user_ids: [userId] }),
      }),
    onSuccess: () => invalidate(qc, accountId, displayId),
  });
}
