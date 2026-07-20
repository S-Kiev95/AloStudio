import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export type IgComment = {
  id: number; // local row id (used to address reply/hide/delete)
  ig_comment_id: string;
  parent_comment_id: string | null;
  from_username: string | null;
  text: string | null;
  hidden: boolean;
  ig_created_at: string | null;
};

function postBase(accountId: string, postId: number): string {
  return `/api/v1/accounts/${accountId}/instagram_posts/${postId}/comments`;
}
function cmtBase(accountId: string, commentId: number): string {
  return `/api/v1/accounts/${accountId}/instagram_comments/${commentId}`;
}

/** Live-sync comments for a post's media from Meta (published posts only).
 *
 * The `comments` webhook mirrors new comments into our DB as they arrive, but
 * the panel has no realtime push, so it polls while open — matching the
 * conversation thread. Gated on `enabled` so a closed panel makes no calls
 * (each fetch hits Meta). Backs off when the tab is hidden. */
export function useComments(accountId: string, postId: number, enabled: boolean) {
  return useQuery({
    queryKey: ["ig-comments", accountId, postId],
    queryFn: () => apiFetch<IgComment[]>(postBase(accountId, postId)),
    enabled,
    retry: false,
    refetchInterval: enabled ? 15_000 : false,
    refetchIntervalInBackground: false,
  });
}

function invalidate(qc: ReturnType<typeof useQueryClient>, accountId: string, postId: number) {
  qc.invalidateQueries({ queryKey: ["ig-comments", accountId, postId] });
}

export function usePostComment(accountId: string, postId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (message: string) =>
      apiFetch<IgComment>(postBase(accountId, postId), {
        method: "POST",
        body: JSON.stringify({ message }),
      }),
    onSuccess: () => invalidate(qc, accountId, postId),
  });
}

export function useReplyComment(accountId: string, postId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { commentId: number; message: string }) =>
      apiFetch<IgComment>(`${cmtBase(accountId, input.commentId)}/replies`, {
        method: "POST",
        body: JSON.stringify({ message: input.message }),
      }),
    onSuccess: () => invalidate(qc, accountId, postId),
  });
}

export function useHideComment(accountId: string, postId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { commentId: number; hide: boolean }) =>
      apiFetch<IgComment>(`${cmtBase(accountId, input.commentId)}/hide`, {
        method: "POST",
        body: JSON.stringify({ hide: input.hide }),
      }),
    onSuccess: () => invalidate(qc, accountId, postId),
  });
}

export function useDeleteComment(accountId: string, postId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (commentId: number) =>
      apiFetch<{ success: boolean }>(cmtBase(accountId, commentId), {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(qc, accountId, postId),
  });
}
