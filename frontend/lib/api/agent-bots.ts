import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export type AgentBot = {
  id: number;
  name: string;
  description: string | null;
  thumbnail: string;
  outgoing_url?: string | null;
  /** ``ai``: AloStudio's AI answering customers (PLAN.agente-ia.md, 2b). */
  bot_type: "webhook" | "ai";
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
  /** On create only. */
  bot_type?: "webhook" | "ai";
};

/** The AI bot's settings (``bot_config``). */
export type AiBotMode = "shadow" | "live";
export type AiBotRespondWhen = "always" | "out_of_hours" | "nobody_available";
export type AiBotConfig = {
  instructions: string;
  mode: AiBotMode;
  respond_when: AiBotRespondWhen;
};

export function aiBotConfig(bot: Pick<AgentBot, "bot_config"> | undefined): AiBotConfig {
  const raw = (bot?.bot_config ?? {}) as Partial<AiBotConfig>;
  return {
    instructions: typeof raw.instructions === "string" ? raw.instructions : "",
    mode: raw.mode === "live" ? "live" : "shadow",
    respond_when:
      raw.respond_when === "out_of_hours" || raw.respond_when === "nobody_available"
        ? raw.respond_when
        : "always",
  };
}

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

function inboxBotKey(accountId: string, inboxId: number) {
  return ["agent-bots", accountId, "inbox", inboxId] as const;
}

/** The bot attached to an inbox, or null. Administrators only. */
export function useInboxAgentBot(accountId: string, inboxId: number) {
  return useQuery({
    queryKey: inboxBotKey(accountId, inboxId),
    queryFn: () =>
      apiFetch<{ agent_bot: AgentBot | null }>(
        `/api/v1/accounts/${accountId}/inboxes/${inboxId}/agent_bot`,
      ),
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
