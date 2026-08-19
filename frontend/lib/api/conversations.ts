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
  content_attributes?: {
    deleted?: boolean;
    /** Present on Channel::Email messages — the headers the thread view
     *  needs to render this as an email rather than a chat line. */
    email?: {
      subject?: string | null;
      from?: string | null;
      from_name?: string | null;
      to?: string[];
      cc?: string[];
      date?: string | null;
      message_id?: string | null;
    };
  } & Record<string, unknown>;
  attachments?: Array<{
    id: number;
    data_url?: string;
    file_type?: string;
    extension?: string;
    coordinates_lat?: number;
    coordinates_long?: number;
    fallback_title?: string;
  }>;
};

export type ConversationMeta = {
  sender?: { id: number; name: string; thumbnail?: string } | null;
  channel?: string | null;
  assignee?: { id: number; name: string } | null;
};

/** Which Meta ad this conversation came from — null unless the person
 *  arrived through a click-to-WhatsApp / click-to-Messenger ad. */
export type AdReferral = {
  source: string | null;
  ad_id: string | null;
  headline: string | null;
  click_id: string | null;
  captured_at: number;
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
  ad_referral?: AdReferral | null;
  /** ``mail_subject`` on an email conversation — the subject the whole
   *  thread hangs off, which is per-thread and not per-message. */
  additional_attributes?: { mail_subject?: string } & Record<string, unknown>;
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

/** Search/filter envelope — one level less than the index (no `data` wrap). */
export type ConversationsSearch = {
  meta: {
    mine_count: number;
    unassigned_count: number;
    all_count: number;
  };
  payload: Conversation[];
};

/** Free-text search across message content (`GET /conversations/search`). */
export function useSearchConversations(
  accountId: string,
  q: string,
  page = 1,
) {
  const trimmed = q.trim();
  return useQuery({
    queryKey: ["conversations-search", accountId, trimmed, page],
    queryFn: () => {
      const sp = new URLSearchParams();
      sp.set("q", trimmed);
      sp.set("page", String(page));
      return apiFetch<ConversationsSearch>(`${base(accountId)}/search?${sp}`);
    },
    enabled: trimmed.length > 0,
  });
}

// ---------------------------------------------------------------------------
// Advanced filter DSL (`POST /conversations/filter`)
// ---------------------------------------------------------------------------
export type FilterOperator =
  | "equal_to"
  | "not_equal_to"
  | "contains"
  | "does_not_contain"
  | "starts_with"
  | "is_present"
  | "is_not_present"
  | "is_greater_than"
  | "is_less_than";

/** One condition row of the filter DSL (mirrors the Ruby payload entry). */
export type FilterCondition = {
  attribute_key: string;
  filter_operator: FilterOperator;
  values: (string | number)[];
  query_operator?: "AND" | "OR";
};

/**
 * Run the filter DSL. Same `{meta, payload}` envelope as search. Disabled
 * until at least one condition exists so the index stays in charge.
 */
export function useFilterConversations(
  accountId: string,
  conditions: FilterCondition[],
  page = 1,
) {
  return useQuery({
    queryKey: ["conversations-filter", accountId, JSON.stringify(conditions), page],
    queryFn: () =>
      apiFetch<ConversationsSearch>(`${base(accountId)}/filter?page=${page}`, {
        method: "POST",
        body: JSON.stringify({ payload: conditions }),
      }),
    enabled: conditions.length > 0,
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
export type OutgoingAttachment = { external_url: string; file_type: string };

export function useSendMessage(accountId: string, displayId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      content?: string;
      isPrivate?: boolean;
      attachments?: OutgoingAttachment[];
      /** Email only. Omitted on every other channel, which has no
       *  concept of copying a third party on a reply. */
      ccEmails?: string;
      bccEmails?: string;
    }) =>
      apiFetch<Message>(`${base(accountId)}/${displayId}/messages`, {
        method: "POST",
        body: JSON.stringify({
          content: input.content,
          message_type: "outgoing",
          private: Boolean(input.isPrivate),
          attachments: input.attachments,
          cc_emails: input.ccEmails || undefined,
          bcc_emails: input.bccEmails || undefined,
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["messages", accountId, displayId] });
      qc.invalidateQueries({ queryKey: ["conversations", accountId] });
    },
  });
}

/** Soft-delete a message — the backend replaces it with a "deleted" marker
 * (it does NOT unsend it from the recipient's WhatsApp). */
export function useDeleteMessage(accountId: string, displayId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (messageId: number) =>
      apiFetch<Record<string, never>>(
        `${base(accountId)}/${displayId}/messages/${messageId}`,
        { method: "DELETE" },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["messages", accountId, displayId] });
    },
  });
}

/** Bulk action over many conversations (`POST /bulk_actions`). */
export function useBulkAction(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      ids: number[];
      fields?: { status?: string; assignee_id?: number | null };
      labels?: { add?: string[]; remove?: string[] };
    }) =>
      apiFetch<{ payload: { updated: number[] } }>(
        `/api/v1/accounts/${accountId}/bulk_actions`,
        {
          method: "POST",
          body: JSON.stringify({
            type: "Conversation",
            ids: input.ids,
            fields: input.fields ?? {},
            labels: input.labels,
          }),
        },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversations", accountId] });
      qc.invalidateQueries({ queryKey: ["conversations-search", accountId] });
      qc.invalidateQueries({ queryKey: ["conversations-filter", accountId] });
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

/** An ad this account has received at least one conversation from.
 *
 *  There is no local table of ads — Meta owns them, and we only learn one
 *  exists when an attributed conversation arrives. So this is the distinct
 *  set seen so far, which is what the inbox filter offers as options. */
export type KnownAd = { ad_id: string; headline: string };

export function useKnownAds(accountId: string) {
  return useQuery({
    queryKey: ["known-ads", accountId],
    queryFn: () => apiFetch<KnownAd[]>(`${base(accountId)}/ads`),
    staleTime: 5 * 60_000, // changes only when a new campaign starts
  });
}
