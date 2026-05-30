import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { Agent } from "./account";
import { apiFetch } from "./fetcher";

export type Team = {
  id: number;
  name: string;
  description: string | null;
  allow_auto_assign: boolean;
  account_id: number;
  is_member: boolean;
};

export type TeamInput = {
  name: string;
  description?: string | null;
  allow_auto_assign?: boolean | null;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/teams`;
}

function membersBase(accountId: string, teamId: number): string {
  return `${base(accountId)}/${teamId}/team_members`;
}

export function useTeams(accountId: string) {
  return useQuery({
    queryKey: ["teams", accountId],
    queryFn: () => apiFetch<Team[]>(base(accountId)),
    staleTime: 60_000,
  });
}

export function useTeam(accountId: string, teamId: number) {
  return useQuery({
    queryKey: ["team", accountId, teamId],
    queryFn: () => apiFetch<Team>(`${base(accountId)}/${teamId}`),
  });
}

function invalidateTeams(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["teams", accountId] });
  qc.invalidateQueries({ queryKey: ["team", accountId] });
}

export function useCreateTeam(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: TeamInput) =>
      apiFetch<Team>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidateTeams(qc, accountId),
  });
}

export function useUpdateTeam(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: TeamInput }) =>
      apiFetch<Team>(`${base(accountId)}/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify(input.patch),
      }),
    onSuccess: () => invalidateTeams(qc, accountId),
  });
}

export function useDeleteTeam(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidateTeams(qc, accountId),
  });
}

// --- team members --------------------------------------------------------
export function useTeamMembers(accountId: string, teamId: number) {
  return useQuery({
    queryKey: ["team-members", accountId, teamId],
    queryFn: () => apiFetch<Agent[]>(membersBase(accountId, teamId)),
    enabled: Number.isFinite(teamId),
  });
}

function invalidateMembers(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
  teamId: number,
) {
  qc.invalidateQueries({ queryKey: ["team-members", accountId, teamId] });
}

/** PATCH replaces the full agent set (add new, drop missing). */
export function useSetTeamMembers(accountId: string, teamId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (user_ids: number[]) =>
      apiFetch<Agent[]>(membersBase(accountId, teamId), {
        method: "PATCH",
        body: JSON.stringify({ user_ids }),
      }),
    onSuccess: () => invalidateMembers(qc, accountId, teamId),
  });
}
