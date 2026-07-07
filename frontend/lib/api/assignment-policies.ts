import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Assignment-order strategy. OSS ships only round-robin. */
export type AssignmentOrder = "round_robin";

/** Which waiting conversation an agent picks up first. */
export type ConversationPriority = "earliest_created" | "longest_waiting";

/** An auto-assignment policy owned by one account. */
export type AssignmentPolicy = {
  id: number;
  name: string;
  description: string | null;
  enabled: boolean;
  assignment_order: AssignmentOrder;
  conversation_priority: ConversationPriority;
  fair_distribution_limit: number;
  fair_distribution_window: number;
};

/** The editable slice (create + update share the same shape). */
export type AssignmentPolicyInput = {
  name: string;
  description?: string | null;
  enabled?: boolean;
  assignment_order?: AssignmentOrder;
  conversation_priority?: ConversationPriority;
  fair_distribution_limit?: number;
  fair_distribution_window?: number;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/assignment_policies`;
}

/** Index — a bare array (no ``payload`` envelope). */
export function useAssignmentPolicies(accountId: string) {
  return useQuery({
    queryKey: ["assignment-policies", accountId],
    queryFn: () => apiFetch<AssignmentPolicy[]>(base(accountId)),
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["assignment-policies", accountId] });
}

export function useCreateAssignmentPolicy(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: AssignmentPolicyInput) =>
      apiFetch<AssignmentPolicy>(base(accountId), {
        method: "POST",
        body: JSON.stringify({ assignment_policy: input }),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateAssignmentPolicy(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: AssignmentPolicyInput }) =>
      apiFetch<AssignmentPolicy>(`${base(accountId)}/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify({ assignment_policy: input.patch }),
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteAssignmentPolicy(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}
