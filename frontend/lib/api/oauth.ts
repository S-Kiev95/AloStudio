import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export type OAuthScope = "read" | "write";

export const OAUTH_SCOPE_LABEL: Record<OAuthScope, string> = {
  read: "Lectura",
  write: "Lectura y escritura",
};

/** An account's registered app (no secret). */
export type OAuthApp = {
  id: number;
  name: string;
  client_id: string;
  confidential: boolean;
  redirect_uris: string[];
  authorizations_count: number;
  created_at: string | null;
};

/** Create and rotate only: the secret is shown this once. */
export type OAuthAppWithSecret = OAuthApp & { client_secret?: string };

export type OAuthEndpoints = {
  authorization: string;
  token: string;
  revocation: string;
  metadata: string;
  mcp: string;
};

export type OAuthAppsResponse = {
  apps: OAuthApp[];
  endpoints: OAuthEndpoints;
};

export type OAuthAppInput = {
  name: string;
  redirect_uris: string[];
  confidential: boolean;
};

export type OAuthAuthorization = {
  app: { id: number; name: string; client_id: string };
  scope: OAuthScope;
  authorized_at: string | null;
  last_used_at: string | null;
};

export type OAuthConsentAccount = {
  id: number;
  name: string;
  role: "administrator" | "agent";
  can_grant: boolean;
};

export type OAuthConsent = {
  app: { name: string; client_id: string; owner_account_name: string | null };
  scope: OAuthScope;
  redirect_uri: string;
  accounts: OAuthConsentAccount[];
};

/** The consent data, or where to send the browser right away (an invalid
 *  request goes back to the app with its error). */
export type OAuthConsentResponse = OAuthConsent | { redirect_to: string };

/** The authorization request's parameters, as they came, plus the answer. */
export type OAuthConsentAnswer = {
  [param: string]: string | number | boolean | undefined;
  account_id?: number;
  approve: boolean;
};

function appsBase(accountId: string): string {
  return `/api/v1/accounts/${accountId}/oauth_apps`;
}

function authorizationsBase(accountId: string): string {
  return `/api/v1/accounts/${accountId}/oauth_authorizations`;
}

/** Admin-only: pass ``enabled: false`` for an agent, whose 401 would be a
 *  pointless request. */
export function useOAuthApps(accountId: string, enabled = true) {
  return useQuery({
    queryKey: ["oauth-apps", accountId],
    queryFn: () => apiFetch<OAuthAppsResponse>(appsBase(accountId)),
    enabled,
  });
}

function invalidateApps(qc: ReturnType<typeof useQueryClient>, accountId: string) {
  qc.invalidateQueries({ queryKey: ["oauth-apps", accountId] });
}

export function useCreateOAuthApp(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: OAuthAppInput) =>
      apiFetch<OAuthAppWithSecret>(appsBase(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidateApps(qc, accountId),
  });
}

export function useUpdateOAuthApp(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      id: number;
      patch: { name?: string; redirect_uris?: string[] };
    }) =>
      apiFetch<OAuthApp>(`${appsBase(accountId)}/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify(input.patch),
      }),
    onSuccess: () => invalidateApps(qc, accountId),
  });
}

export function useRotateOAuthAppSecret(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<OAuthAppWithSecret>(`${appsBase(accountId)}/${id}/secret`, {
        method: "POST",
      }),
    onSuccess: () => invalidateApps(qc, accountId),
  });
}

export function useDeleteOAuthApp(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${appsBase(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidateApps(qc, accountId),
  });
}

export function useOAuthAuthorizations(accountId: string) {
  return useQuery({
    queryKey: ["oauth-authorizations", accountId],
    queryFn: async () => {
      const res = await apiFetch<{ authorizations: OAuthAuthorization[] }>(
        authorizationsBase(accountId),
      );
      return res.authorizations;
    },
  });
}

export function useRevokeOAuthAuthorization(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (appId: number) =>
      apiFetch<Record<string, never>>(`${authorizationsBase(accountId)}/${appId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["oauth-authorizations", accountId] });
      invalidateApps(qc, accountId);
    },
  });
}

/** ``search`` is the consent page's query string, as the app built it. */
export function useOAuthConsent(search: string) {
  return useQuery({
    queryKey: ["oauth-consent", search],
    queryFn: () =>
      apiFetch<OAuthConsentResponse>(`/api/v1/oauth/authorize${search}`),
    retry: false,
    staleTime: Infinity,
  });
}

export function useSubmitOAuthConsent() {
  return useMutation({
    mutationFn: (answer: OAuthConsentAnswer) =>
      apiFetch<{ redirect_to: string }>("/api/v1/oauth/authorize", {
        method: "POST",
        body: JSON.stringify(answer),
      }),
  });
}
