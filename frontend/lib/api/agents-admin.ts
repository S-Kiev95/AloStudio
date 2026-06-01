import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { Agent } from "./account";
import { apiFetch } from "./fetcher";

export type AgentRole = "agent" | "administrator";

export const ROLE_LABEL: Record<AgentRole, string> = {
  administrator: "Administrador",
  agent: "Agente",
};

export type InviteAgentInput = {
  email: string;
  name: string;
  role?: AgentRole;
};

export type UpdateAgentInput = {
  name?: string;
  role?: AgentRole;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/agents`;
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["agents", accountId] });
}

/**
 * ``POST /agents`` — invite a new member by email + role. The backend
 * mints a reset_password_token and emails the invitee a link that
 * lands them on ``/reset-password?token=…`` to set their password.
 */
export function useInviteAgent(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: InviteAgentInput) =>
      apiFetch<Agent & { role: number }>(base(accountId), {
        method: "POST",
        body: JSON.stringify({ agent: input }),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

/** ``PATCH /agents/{user_id}`` — admin-only rename or re-role. */
export function useUpdateAgent(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { user_id: number; patch: UpdateAgentInput }) =>
      apiFetch<Agent & { role: number }>(
        `${base(accountId)}/${input.user_id}`,
        { method: "PATCH", body: JSON.stringify({ agent: input.patch }) },
      ),
    onSuccess: () => invalidate(qc, accountId),
  });
}

/**
 * ``DELETE /agents/{user_id}`` — remove the AccountUser link. The User
 * row stays (it may belong to other accounts).
 */
export function useRemoveAgent(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (user_id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${user_id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}
