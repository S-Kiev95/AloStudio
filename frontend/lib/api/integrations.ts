import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export type IntegrationHook = {
  id: number;
  app_id: string;
  status: boolean;
  account_id: number;
  hook_type: string;
  inbox: { id: number; name: string } | null;
  settings?: Record<string, unknown>;
  reference_id?: string | null;
};

export type IntegrationApp = {
  id: string;
  name: string;
  description: string;
  short_description: string;
  enabled: boolean;
  allow_multiple_hooks?: boolean;
  hooks: IntegrationHook[];
};

export type HookInput = {
  app_id: string;
  inbox_id?: number | null;
  hook_type?: string;
  settings?: Record<string, unknown>;
};

function appsBase(accountId: string): string {
  return `/api/v1/accounts/${accountId}/integrations/apps`;
}

function hooksBase(accountId: string): string {
  return `/api/v1/accounts/${accountId}/integrations/hooks`;
}

export function useIntegrationApps(accountId: string) {
  return useQuery({
    queryKey: ["integration-apps", accountId],
    queryFn: async () => {
      const res = await apiFetch<{ payload: IntegrationApp[] }>(
        appsBase(accountId),
      );
      return res.payload;
    },
  });
}

export function useIntegrationApp(accountId: string, appId: string) {
  return useQuery({
    queryKey: ["integration-app", accountId, appId],
    queryFn: () => apiFetch<IntegrationApp>(`${appsBase(accountId)}/${appId}`),
    enabled: Boolean(appId),
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["integration-apps", accountId] });
  qc.invalidateQueries({ queryKey: ["integration-app", accountId] });
}

export function useCreateIntegrationHook(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: HookInput) =>
      apiFetch<IntegrationHook>(hooksBase(accountId), {
        method: "POST",
        body: JSON.stringify({ hook: input }),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteIntegrationHook(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${hooksBase(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}
