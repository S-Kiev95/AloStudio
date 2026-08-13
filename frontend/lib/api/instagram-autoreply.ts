import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export type AutoreplyMode = "off" | "fixed" | "semantic";

export type AutoreplyConfig = {
  channel_instagram_id: number;
  mode: AutoreplyMode;
  text: string | null;
  max_distance: number;
  /** False when no OPENAI_API_KEY is configured — the semantic option is
   *  then offered as disabled with an explanation, rather than letting an
   *  admin pick a mode that would silently never fire. */
  semantic_available: boolean;
};

export type CommentReply = {
  id: number;
  trigger: string;
  reply: string;
  enabled: boolean;
  /** False when the answer has no embedding yet, so it can never match. */
  indexed: boolean;
};

export type CommentReplyInput = {
  trigger: string;
  reply: string;
  enabled: boolean;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}`;
}

// ---------------------------------------------------------------------------
// Per-inbox configuration
// ---------------------------------------------------------------------------
export function useAutoreplyConfig(
  accountId: string,
  channelId: number | null,
) {
  return useQuery({
    queryKey: ["ig-autoreply", accountId, channelId],
    queryFn: () =>
      apiFetch<AutoreplyConfig>(
        `${base(accountId)}/instagram_channels/${channelId}/autoreply`,
      ),
    enabled: channelId != null,
    retry: false,
  });
}

export function useUpdateAutoreplyConfig(
  accountId: string,
  channelId: number | null,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: {
      mode?: AutoreplyMode;
      text?: string | null;
      max_distance?: number;
    }) =>
      apiFetch<AutoreplyConfig>(
        `${base(accountId)}/instagram_channels/${channelId}/autoreply`,
        { method: "PATCH", body: JSON.stringify(patch) },
      ),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ["ig-autoreply", accountId, channelId],
      }),
  });
}

// ---------------------------------------------------------------------------
// Prepared answers
// ---------------------------------------------------------------------------
export function useCommentReplies(accountId: string, enabled = true) {
  return useQuery({
    queryKey: ["ig-comment-replies", accountId],
    queryFn: () =>
      apiFetch<CommentReply[]>(`${base(accountId)}/instagram_comment_replies`),
    enabled,
  });
}

function invalidateReplies(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["ig-comment-replies", accountId] });
}

export function useCreateCommentReply(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CommentReplyInput) =>
      apiFetch<CommentReply>(`${base(accountId)}/instagram_comment_replies`, {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidateReplies(qc, accountId),
  });
}

export function useUpdateCommentReply(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { id: number; input: CommentReplyInput }) =>
      apiFetch<CommentReply>(
        `${base(accountId)}/instagram_comment_replies/${args.id}`,
        { method: "PATCH", body: JSON.stringify(args.input) },
      ),
    onSuccess: () => invalidateReplies(qc, accountId),
  });
}

export function useDeleteCommentReply(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(
        `${base(accountId)}/instagram_comment_replies/${id}`,
        { method: "DELETE" },
      ),
    onSuccess: () => invalidateReplies(qc, accountId),
  });
}
