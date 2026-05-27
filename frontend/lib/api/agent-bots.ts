import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export type AgentBot = {
  id: number;
  name: string;
  description: string | null;
  thumbnail: string;
  outgoing_url?: string | null;
  bot_type: "webhook";
  bot_config: Record<string, unknown>;
  account_id: number | null; // null for system bots
  secret?: string | null;
  system_bot: boolean;
};

export type AgentBotInput = {
  name: string;
  description?: string | null;
  outgoing_url?: string | null;
  bot_config?: Record<string, unknown>;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/agent_bots`;
}

export function useAgentBots(accountId: string) {
  return useQuery({
    queryKey: ["agent-bots", accountId],
    queryFn: () => apiFetch<AgentBot[]>(base(accountId)),
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["agent-bots", accountId] });
}

export function useCreateAgentBot(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: AgentBotInput) =>
      apiFetch<AgentBot>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateAgentBot(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: AgentBotInput }) =>
      apiFetch<AgentBot>(`${base(accountId)}/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify(input.patch),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteAgentBot(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useResetBotSecret(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<AgentBot>(`${base(accountId)}/${id}/reset_secret`, {
        method: "POST",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

/** Attach/detach a bot on an inbox. ``agent_bot=null`` detaches. */
export function useSetAgentBot(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { inbox_id: number; agent_bot: number | null }) =>
      apiFetch<Record<string, never>>(
        `/api/v1/accounts/${accountId}/inboxes/${input.inbox_id}/set_agent_bot`,
        {
          method: "POST",
          body: JSON.stringify({ agent_bot: input.agent_bot }),
        },
      ),
    onSuccess: () => invalidate(qc, accountId),
  });
}
