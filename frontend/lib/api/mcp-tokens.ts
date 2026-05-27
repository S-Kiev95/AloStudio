import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export type MCPScope = "read" | "write" | "admin";

export const MCP_SCOPES: { value: MCPScope; label: string; hint: string }[] = [
  {
    value: "read",
    label: "Lectura",
    hint: "Solo puede leer conversaciones, contactos, posts, etc.",
  },
  {
    value: "write",
    label: "Escritura",
    hint: "Puede crear y modificar (responder, etiquetar, publicar).",
  },
  {
    value: "admin",
    label: "Admin",
    hint: "Acceso completo, igual que un administrador.",
  },
];

/** Index/update view of a token (no plain-text secret). */
export type MCPTokenInfo = {
  id: number;
  account_id: number;
  user_id: number | null;
  name: string;
  scope: MCPScope;
  last_used_at: string | null;
  created_at: string | null;
};

/** Returned by create + rotate only — secret visible once. */
export type MCPTokenWithSecret = MCPTokenInfo & {
  token: string;
};

export type MCPTokenCreateInput = {
  name: string;
  scope?: MCPScope;
};

export type MCPTokenUpdateInput = {
  name?: string;
  scope?: MCPScope;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/mcp_tokens`;
}

export function useMCPTokens(accountId: string) {
  return useQuery({
    queryKey: ["mcp-tokens", accountId],
    queryFn: async () => {
      const res = await apiFetch<{ payload: MCPTokenInfo[] }>(base(accountId));
      return res.payload;
    },
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["mcp-tokens", accountId] });
}

export function useCreateMCPToken(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: MCPTokenCreateInput) =>
      apiFetch<MCPTokenWithSecret>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateMCPToken(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: MCPTokenUpdateInput }) =>
      apiFetch<MCPTokenInfo>(`${base(accountId)}/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify(input.patch),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useRotateMCPToken(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<MCPTokenWithSecret>(`${base(accountId)}/${id}/rotate`, {
        method: "POST",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteMCPToken(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}
