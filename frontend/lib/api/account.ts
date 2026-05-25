import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export type Agent = {
  id: number;
  name: string;
  available_name?: string;
  email?: string;
};

export type Label = {
  id: number;
  title: string;
  color?: string;
};

export function useAgents(accountId: string) {
  return useQuery({
    queryKey: ["agents", accountId],
    queryFn: () => apiFetch<Agent[]>(`/api/v1/accounts/${accountId}/agents`),
    staleTime: 5 * 60_000,
  });
}

export function useLabels(accountId: string) {
  return useQuery({
    queryKey: ["labels", accountId],
    queryFn: () =>
      apiFetch<{ payload: Label[] }>(`/api/v1/accounts/${accountId}/labels`),
    staleTime: 5 * 60_000,
  });
}
