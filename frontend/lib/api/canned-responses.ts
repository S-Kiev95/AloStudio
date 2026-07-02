import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Canned response — a ``/short_code`` → ``content`` reply snippet. */
export type CannedResponse = {
  id: number;
  short_code: string;
  content: string;
  account_id?: number;
};

export type CannedResponseInput = {
  short_code: string;
  content: string;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/canned_responses`;
}

/**
 * Index — a bare array (no ``payload`` envelope, matching the backend's
 * bare ``render json:``). When ``search`` is set the backend ranks
 * short_code prefix > short_code substring > content substring.
 */
export function useCannedResponses(accountId: string, search?: string) {
  const q = search?.trim() ?? "";
  return useQuery({
    queryKey: ["canned-responses", accountId, q || null],
    queryFn: () => {
      const qs = q ? `?search=${encodeURIComponent(q)}` : "";
      return apiFetch<CannedResponse[]>(`${base(accountId)}${qs}`);
    },
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["canned-responses", accountId] });
}

export function useCreateCannedResponse(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CannedResponseInput) =>
      apiFetch<CannedResponse>(base(accountId), {
        method: "POST",
        body: JSON.stringify({ canned_response: input }),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateCannedResponse(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: CannedResponseInput }) =>
      apiFetch<CannedResponse>(`${base(accountId)}/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify({ canned_response: input.patch }),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteCannedResponse(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}
