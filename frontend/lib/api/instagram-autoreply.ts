import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** How a rule decides a comment is for it. Evaluated most-specific first,
 *  so a keyword rule always beats a catch-all on the same post. */
export type MatchType = "keyword" | "semantic" | "all";

/** Public reply under the post, or a private message to the commenter. */
export type Delivery = "public" | "dm";

export type PostRule = {
  id: number;
  post_id: number;
  match_type: MatchType;
  keywords: string | null;
  reply_text: string | null;
  delivery: Delivery;
  enabled: boolean;
};

export type PostRuleInput = {
  match_type: MatchType;
  keywords?: string | null;
  reply_text?: string | null;
  delivery: Delivery;
  enabled: boolean;
};

export type CommentReply = {
  id: number;
  trigger: string;
  reply: string;
  enabled: boolean;
  /** Null when the answer is shared across every publication. */
  post_id: number | null;
  /** False when the answer has no embedding yet, so it can never match. */
  indexed: boolean;
};

export type CommentReplyInput = {
  trigger: string;
  reply: string;
  enabled: boolean;
  post_id?: number | null;
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}`;
}

// ---------------------------------------------------------------------------
// Rules on one publication
// ---------------------------------------------------------------------------
export function usePostRules(accountId: string, postId: number) {
  return useQuery({
    queryKey: ["ig-post-rules", accountId, postId],
    queryFn: () =>
      apiFetch<PostRule[]>(
        `${base(accountId)}/instagram_posts/${postId}/autoreply_rules`,
      ),
    enabled: Number.isFinite(postId),
  });
}

function invalidateRules(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["ig-post-rules", accountId] });
}

export function useCreatePostRule(accountId: string, postId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: PostRuleInput) =>
      apiFetch<PostRule>(
        `${base(accountId)}/instagram_posts/${postId}/autoreply_rules`,
        { method: "POST", body: JSON.stringify(input) },
      ),
    onSuccess: () => invalidateRules(qc, accountId),
  });
}

export function useUpdatePostRule(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { id: number; input: PostRuleInput }) =>
      apiFetch<PostRule>(`${base(accountId)}/autoreply_rules/${args.id}`, {
        method: "PATCH",
        body: JSON.stringify(args.input),
      }),
    onSuccess: () => invalidateRules(qc, accountId),
  });
}

export function useDeletePostRule(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(
        `${base(accountId)}/autoreply_rules/${id}`,
        { method: "DELETE" },
      ),
    onSuccess: () => invalidateRules(qc, accountId),
  });
}

// ---------------------------------------------------------------------------
// Prepared answers (used by `semantic` rules)
// ---------------------------------------------------------------------------
/** Whether similarity matching can run at all on this installation.
 *
 *  Without an embedding provider a `semantic` rule is inert and every
 *  answer saves unindexed, so the UI has to say that rather than tell the
 *  admin to save again. */
export function useAutoreplyStatus(accountId: string) {
  return useQuery({
    queryKey: ["ig-autoreply-status", accountId],
    queryFn: () =>
      apiFetch<{ semantic_available: boolean }>(
        `${base(accountId)}/instagram_autoreply_status`,
      ),
    staleTime: 5 * 60 * 1000,
  });
}

/** `postId` narrows to what that publication matches against: its own
 *  answers plus the shared ones. Omitted, the whole library. */
export function useCommentReplies(
  accountId: string,
  opts: { postId?: number; enabled?: boolean } = {},
) {
  const { postId, enabled = true } = opts;
  return useQuery({
    queryKey: ["ig-comment-replies", accountId, postId ?? null],
    queryFn: () =>
      apiFetch<CommentReply[]>(
        `${base(accountId)}/instagram_comment_replies` +
          (postId != null ? `?post_id=${postId}` : ""),
      ),
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
