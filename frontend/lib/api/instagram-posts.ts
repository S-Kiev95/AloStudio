import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export type MediaType = "IMAGE" | "VIDEO" | "REELS" | "CAROUSEL" | "STORIES";
export type PostState =
  | "pending"
  | "publishing"
  | "published"
  | "failed"
  | "deleted";

export type Product = {
  id: number;
  name: string;
  price: number | null;
  currency: string | null;
  enabled: boolean;
};

export type Container = {
  id: number;
  ig_container_id: string;
  position: number;
  status_code: string;
  poll_count: number;
};

export type InstagramPost = {
  id: number;
  inbox_id: number;
  channel_instagram_id: number;
  state: PostState;
  media_type: MediaType;
  caption: string | null;
  source: Record<string, unknown>;
  ig_media_id: string | null;
  ig_permalink: string | null;
  error_code: string | null;
  error_message: string | null;
  scheduled_for: string | null;
  published_at: string | null;
  created_at: number | null;
  products?: Product[];
  containers?: Container[];
};

export type CreatePostInput = {
  inbox_id: number;
  media_type: MediaType;
  source: Record<string, unknown>;
  caption?: string;
  scheduled_for?: string;
  product_ids?: number[];
};

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/instagram_posts`;
}

export function useInstagramPosts(
  accountId: string,
  filters: { state?: string; page?: number } = {},
) {
  const { state, page = 1 } = filters;
  return useQuery({
    queryKey: ["instagram-posts", accountId, state ?? null, page],
    queryFn: () => {
      const sp = new URLSearchParams();
      if (state) sp.set("state", state);
      sp.set("page", String(page));
      return apiFetch<InstagramPost[]>(`${base(accountId)}?${sp}`);
    },
  });
}

export function useInstagramPost(accountId: string, postId: number) {
  return useQuery({
    queryKey: ["instagram-post", accountId, postId],
    queryFn: () => apiFetch<InstagramPost>(`${base(accountId)}/${postId}`),
    // Pending/publishing posts settle async — poll until terminal.
    refetchInterval: (q) => {
      const s = (q.state.data as InstagramPost | undefined)?.state;
      return s === "pending" || s === "publishing" ? 5_000 : false;
    },
  });
}

export function useCreatePost(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreatePostInput) =>
      apiFetch<InstagramPost>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["instagram-posts", accountId] });
    },
  });
}

export function useDeletePost(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (postId: number) =>
      apiFetch<InstagramPost>(`${base(accountId)}/${postId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["instagram-posts", accountId] });
    },
  });
}

export function useProducts(accountId: string) {
  return useQuery({
    queryKey: ["products", accountId],
    queryFn: () =>
      apiFetch<Product[]>(`/api/v1/accounts/${accountId}/products`),
    staleTime: 5 * 60_000,
  });
}
