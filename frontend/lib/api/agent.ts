import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "./errors";
import { apiFetch } from "./fetcher";
import { invalidatePublications } from "./publications";

export type AgentStatus = {
  enabled: boolean;
  model: string;
  can_write: boolean;
};

export type AgentThreadSummary = {
  id: number;
  title: string;
  updated_at: string;
  has_pending_action: boolean;
};

export type AgentThreadsResponse = {
  threads: AgentThreadSummary[];
};

export type AgentTextItem = {
  id: number;
  kind: "user" | "assistant";
  content: string;
  created_at: string;
};

export type AgentToolStatus = "done" | "error" | "rejected" | "pending";

export type AgentToolItem = {
  id: number;
  kind: "tool";
  tool: string;
  status: AgentToolStatus;
  label: string;
  detail: string | null;
  publication_id: number | null;
  created_at: string;
};

export type AgentItem = AgentTextItem | AgentToolItem;

export type AgentPendingChannel = {
  id: number;
  name: string | null;
  network: string;
};

export type AgentPendingMedia = {
  id?: number | null;
  type: "image" | "video";
  url: string;
};

export type AgentPendingPublication = {
  id: number | null;
  content: string | null;
  scheduled_for: string | null;
  channels: AgentPendingChannel[];
  media: AgentPendingMedia[];
};

export type AgentActionTool = "create_publication" | "cancel_publication";

export type AgentPendingAction = {
  id: string;
  tool: AgentActionTool;
  title: string;
  confirm_label: string;
  publication: AgentPendingPublication;
};

export type AgentThread = {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  items: AgentItem[];
  pending_action: AgentPendingAction | null;
};

export type AgentMessageInput = {
  content: string;
  timezone: string;
};

export function getBrowserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export function getAgentErrorMessage(
  err: unknown,
  fallback = "Ocurrió un error al comunicarse con el agente.",
): string {
  if (err instanceof ApiError) {
    if (err.body && typeof err.body === "object") {
      const msg = (err.body as { message?: unknown }).message;
      if (typeof msg === "string" && msg.trim()) return msg;
    }
    if (err.message.trim()) return err.message;
  }
  if (err instanceof Error && err.message.trim()) {
    return err.message;
  }
  return fallback;
}

export function isAgentErrorStatus(err: unknown, status: number): boolean {
  return err instanceof ApiError && err.status === status;
}

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/agent`;
}

export function agentStatusQueryKey(accountId: string) {
  return ["agent-status", accountId] as const;
}

export function agentThreadsQueryKey(accountId: string) {
  return ["agent-threads", accountId] as const;
}

export function agentThreadQueryKey(accountId: string, threadId: number | null) {
  return ["agent-thread", accountId, threadId] as const;
}

export function useAgentStatus(accountId: string) {
  return useQuery({
    queryKey: agentStatusQueryKey(accountId),
    queryFn: () => apiFetch<AgentStatus>(base(accountId)),
  });
}

export function useAgentThreads(accountId: string) {
  return useQuery({
    queryKey: agentThreadsQueryKey(accountId),
    queryFn: () => apiFetch<AgentThreadsResponse>(`${base(accountId)}/threads`),
  });
}

export function useAgentThread(accountId: string, threadId: number | null) {
  const validId =
    threadId !== null && Number.isFinite(threadId) && threadId > 0;
  return useQuery({
    queryKey: agentThreadQueryKey(accountId, validId ? threadId : null),
    queryFn: () =>
      apiFetch<AgentThread>(`${base(accountId)}/threads/${threadId}`),
    enabled: validId,
    staleTime: 30_000,
  });
}

export function useCreateAgentThread(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: AgentMessageInput) =>
      apiFetch<AgentThread>(`${base(accountId)}/threads`, {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: (thread) => {
      qc.setQueryData(agentThreadQueryKey(accountId, thread.id), thread);
      qc.invalidateQueries({ queryKey: agentThreadsQueryKey(accountId) });
    },
    onError: (err) => {
      if (isAgentErrorStatus(err, 502) || isAgentErrorStatus(err, 409)) {
        qc.invalidateQueries({ queryKey: agentThreadsQueryKey(accountId) });
      }
    },
  });
}

export function useSendAgentMessage(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { threadId: number } & AgentMessageInput) =>
      apiFetch<AgentThread>(`${base(accountId)}/threads/${input.threadId}/messages`, {
        method: "POST",
        body: JSON.stringify({
          content: input.content,
          timezone: input.timezone,
        }),
      }),
    onSuccess: (thread) => {
      qc.setQueryData(agentThreadQueryKey(accountId, thread.id), thread);
      qc.invalidateQueries({ queryKey: agentThreadsQueryKey(accountId) });
    },
    onError: (err, vars) => {
      if (isAgentErrorStatus(err, 502) || isAgentErrorStatus(err, 409)) {
        qc.invalidateQueries({
          queryKey: agentThreadQueryKey(accountId, vars.threadId),
        });
        qc.invalidateQueries({ queryKey: agentThreadsQueryKey(accountId) });
      }
    },
  });
}

function findLatestToolPublicationId(thread: AgentThread): number | undefined {
  for (let i = thread.items.length - 1; i >= 0; i--) {
    const item = thread.items[i];
    if (item && item.kind === "tool" && item.publication_id !== null) {
      return item.publication_id;
    }
  }
  return undefined;
}

export function useConfirmAgentAction(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      threadId: number;
      actionId: string;
      publicationId?: number | null;
    }) =>
      apiFetch<AgentThread>(
        `${base(accountId)}/threads/${input.threadId}/actions/${encodeURIComponent(input.actionId)}/confirm`,
        { method: "POST" },
      ),
    onSuccess: (thread, vars) => {
      qc.setQueryData(agentThreadQueryKey(accountId, thread.id), thread);
      qc.invalidateQueries({ queryKey: agentThreadsQueryKey(accountId) });
      const pubId =
        vars.publicationId ?? findLatestToolPublicationId(thread) ?? undefined;
      invalidatePublications(qc, accountId, pubId);
    },
    onError: (err, vars) => {
      if (isAgentErrorStatus(err, 409) || isAgentErrorStatus(err, 502)) {
        qc.invalidateQueries({
          queryKey: agentThreadQueryKey(accountId, vars.threadId),
        });
        qc.invalidateQueries({ queryKey: agentThreadsQueryKey(accountId) });
      }
    },
  });
}

export function useRejectAgentAction(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      threadId: number;
      actionId: string;
      publicationId?: number | null;
    }) =>
      apiFetch<AgentThread>(
        `${base(accountId)}/threads/${input.threadId}/actions/${encodeURIComponent(input.actionId)}/reject`,
        { method: "POST" },
      ),
    onSuccess: (thread, vars) => {
      qc.setQueryData(agentThreadQueryKey(accountId, thread.id), thread);
      qc.invalidateQueries({ queryKey: agentThreadsQueryKey(accountId) });
      invalidatePublications(qc, accountId, vars.publicationId ?? undefined);
    },
    onError: (err, vars) => {
      if (isAgentErrorStatus(err, 409) || isAgentErrorStatus(err, 502)) {
        qc.invalidateQueries({
          queryKey: agentThreadQueryKey(accountId, vars.threadId),
        });
        qc.invalidateQueries({ queryKey: agentThreadsQueryKey(accountId) });
      }
    },
  });
}

export function useDeleteAgentThread(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (threadId: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/threads/${threadId}`, {
        method: "DELETE",
      }),
    onSuccess: (_data, threadId) => {
      qc.removeQueries({ queryKey: agentThreadQueryKey(accountId, threadId) });
      qc.invalidateQueries({ queryKey: agentThreadsQueryKey(accountId) });
    },
  });
}
