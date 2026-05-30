import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

// Chatwoot message_type integers.
export const MESSAGE_TYPE = {
  incoming: 0,
  outgoing: 1,
  activity: 2,
  template: 3,
} as const;

export type Sender = {
  id?: number;
  name?: string;
  thumbnail?: string;
  type?: string;
};

export type Message = {
  id: number;
  content: string | null;
  message_type: number;
  content_type: string;
  status: string;
  created_at: number;
  private: boolean;
  sender?: Sender;
  attachments?: Array<{ id: number; data_url?: string; file_type?: string }>;
};

export type ConversationMeta = {
  sender?: { id: number; name: string; thumbnail?: string } | null;
  channel?: string | null;
  assignee?: { id: number; name: string } | null;
};

export type Conversation = {
  id: number; // display_id
  status: string;
  priority: string | null;
  unread_count: number;
  inbox_id: number;
  labels: string[];
  meta: ConversationMeta;
  messages: Message[];
  last_non_activity_message?: Message | null;
  timestamp: number;
  last_activity_at: number;
  created_at: number;
};

export type ConversationsIndex = {
  data: {
    meta: {
      mine_count: number;
      assigned_count: number;
      unassigned_count: number;
      all_count: number;
    };
    payload: Conversation[];
  };
};

export type MessagesIndex = {
  meta: Record<string, unknown>;
  payload: Message[];
};

export type ConversationFilters = {
  status?: string;
  assigneeType?: string;
  page?: number;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/conversations`;
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------
export function useConversations(
  accountId: string,
  filters: ConversationFilters,
) {
  const { status = "open", assigneeType, page = 1 } = filters;
  return useQuery({
    queryKey: ["conversations", accountId, status, assigneeType ?? null, page],
    queryFn: () => {
      const sp = new URLSearchParams();
      sp.set("status", status);
      if (assigneeType) sp.set("assignee_type", assigneeType);
      sp.set("page", String(page));
      return apiFetch<ConversationsIndex>(`${base(accountId)}?${sp}`);
    },
  });
}

export function useConversation(accountId: string, displayId: number) {
  return useQuery({
    queryKey: ["conversation", accountId, displayId],
    queryFn: () =>
      apiFetch<Conversation>(`${base(accountId)}/${displayId}`),
  });
}

export function useMessages(accountId: string, displayId: number) {
  return useQuery({
    queryKey: ["messages", accountId, displayId],
    queryFn: () =>
      apiFetch<MessagesIndex>(`${base(accountId)}/${displayId}/messages`),
    refetchInterval: 15_000, // light polling until realtime (F.3 follow-up)
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------
export function useSendMessage(accountId: string, displayId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { content: string; isPrivate?: boolean }) =>
      apiFetch<Message>(`${base(accountId)}/${displayId}/messages`, {
        method: "POST",
        body: JSON.stringify({
          content: input.content,
          message_type: "outgoing",
          private: Boolean(input.isPrivate),
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["messages", accountId, displayId] });
      qc.invalidateQueries({ queryKey: ["conversations", accountId] });
    },
  });
}

export function useToggleStatus(accountId: string, displayId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (status: "open" | "resolved" | "pending") =>
      apiFetch<{ payload: { current_status: string } }>(
        `${base(accountId)}/${displayId}/toggle_status`,
        { method: "POST", body: JSON.stringify({ status }) },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversation", accountId, displayId] });
      qc.invalidateQueries({ queryKey: ["conversations", accountId] });
    },
  });
}

export type Priority = "none" | "low" | "medium" | "high" | "urgent";

export function useTogglePriority(accountId: string, displayId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (priority: Priority) =>
      apiFetch<unknown>(`${base(accountId)}/${displayId}/toggle_priority`, {
        method: "POST",
        body: JSON.stringify({
          priority: priority === "none" ? null : priority,
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversation", accountId, displayId] });
      qc.invalidateQueries({ queryKey: ["conversations", accountId] });
    },
  });
}

export function useAssignAgent(accountId: string, displayId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (assigneeId: number | null) =>
      apiFetch<unknown>(`${base(accountId)}/${displayId}/assignments`, {
        method: "POST",
        body: JSON.stringify({ assignee_id: assigneeId }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversation", accountId, displayId] });
      qc.invalidateQueries({ queryKey: ["conversations", accountId] });
    },
  });
}

export function useSetLabels(accountId: string, displayId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (labels: string[]) =>
      apiFetch<unknown>(`${base(accountId)}/${displayId}/labels`, {
        method: "POST",
        body: JSON.stringify({ labels }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversation", accountId, displayId] });
    },
  });
}
