import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { Agent } from "./account";
import { apiFetch } from "./fetcher";

export type MacroVisibility = "personal" | "global";

/** Allow-list mirrors backend's MACRO_ALLOWED_ACTIONS. */
export const MACRO_ACTIONS = [
  "send_message",
  "add_label",
  "assign_team",
  "assign_agent",
  "mute_conversation",
  "change_status",
  "remove_label",
  "remove_assigned_agent",
  "remove_assigned_team",
  "resolve_conversation",
  "snooze_conversation",
  "change_priority",
  "send_email_transcript",
  "send_attachment",
  "add_private_note",
  "send_webhook_event",
] as const;

export type MacroActionName = (typeof MACRO_ACTIONS)[number];

export type MacroAction = {
  action_name: MacroActionName;
  action_params: unknown[];
};

export type Macro = {
  id: number;
  name: string;
  visibility: MacroVisibility;
  account_id: number;
  actions: MacroAction[];
  created_by?: Agent | null;
  updated_by?: Agent | null;
};

export type MacroInput = {
  name: string;
  visibility: MacroVisibility;
  actions: MacroAction[];
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/macros`;
}

export function useMacros(accountId: string) {
  return useQuery({
    queryKey: ["macros", accountId],
    queryFn: async () => {
      const res = await apiFetch<{ payload: Macro[] }>(base(accountId));
      return res.payload;
    },
  });
}

export function useMacro(accountId: string, macroId: number) {
  return useQuery({
    queryKey: ["macro", accountId, macroId],
    queryFn: async () => {
      const res = await apiFetch<{ payload: Macro }>(
        `${base(accountId)}/${macroId}`,
      );
      return res.payload;
    },
    enabled: Number.isFinite(macroId),
  });
}

function invalidate(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["macros", accountId] });
  qc.invalidateQueries({ queryKey: ["macro", accountId] });
}

export function useCreateMacro(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: MacroInput) => {
      const res = await apiFetch<{ payload: Macro }>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      });
      return res.payload;
    },
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useUpdateMacro(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { id: number; patch: MacroInput }) => {
      const res = await apiFetch<{ payload: Macro }>(
        `${base(accountId)}/${input.id}`,
        {
          method: "PATCH",
          body: JSON.stringify(input.patch),
        },
      );
      return res.payload;
    },
    onSuccess: () => invalidate(qc, accountId),
  });
}

export function useDeleteMacro(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId),
  });
}

/** POST /macros/:id/execute — body {conversation_ids: number[]}, returns 200 + {}. */
export function useExecuteMacro(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; conversation_ids: number[] }) =>
      apiFetch<Record<string, never>>(
        `${base(accountId)}/${input.id}/execute`,
        {
          method: "POST",
          body: JSON.stringify({ conversation_ids: input.conversation_ids }),
        },
      ),
    // A macro applies labels/status/priority/assignment + may add a
    // message, so refresh the affected conversations + their threads.
    onSuccess: (_data, input) => {
      qc.invalidateQueries({ queryKey: ["conversations", accountId] });
      for (const id of input.conversation_ids) {
        qc.invalidateQueries({ queryKey: ["conversation", accountId, id] });
        qc.invalidateQueries({ queryKey: ["messages", accountId, id] });
      }
    },
  });
}
