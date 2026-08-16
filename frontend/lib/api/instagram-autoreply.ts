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
  /** Null follows the installation default. */
  max_distance: number | null;
  /** What the rule actually matches at, default resolved server-side. */
  effective_max_distance: number;
};

export type PostRuleInput = {
  match_type: MatchType;
  keywords?: string | null;
  reply_text?: string | null;
  delivery: Delivery;
  enabled: boolean;
  max_distance?: number | null;
};

export type CommentReply = {
  id: number;
  trigger: string;
  reply: string;
  enabled: boolean;
  /** False when the answer has no embedding yet, so it can never match. */
  indexed: boolean;
  /** Only present when the list was read for a publication: whether that
   *  publication offers this answer. */
  selected?: boolean;
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

/** The whole library. With `postId`, each row also carries `selected` —
 *  whether that publication offers it. */
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

/** Replace the answers a publication offers.
 *
 *  Whole-set replace, matching the endpoint: the UI edits checkboxes, and
 *  sending the resulting set means a lost request leaves the selection as
 *  it was rather than half-applied. An empty list falls back to the whole
 *  library. */
export function useSetReplyPicks(accountId: string, postId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (replyIds: number[]) =>
      apiFetch<{ post_id: number; reply_ids: number[] }>(
        `${base(accountId)}/instagram_posts/${postId}/comment_replies`,
        { method: "PUT", body: JSON.stringify({ reply_ids: replyIds }) },
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
