import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "./errors";
import { apiFetch } from "./fetcher";

export type Network = "instagram" | "facebook_page" | string;

export type Channel = {
  id: number;
  network: Network;
  name: string | null;
  username: string | null;
  avatar_url: string | null;
  inbox_id: number | null;
  status: "active" | "reconnect";
  status_message: string | null;
};

export type MediaIn =
  | { media_id: number }
  | { type: "image" | "video"; url: string };

export type InstagramPostType = "feed" | "reels" | "story";

export type TargetIn = {
  channel_id: number;
  settings?: { post_type?: InstagramPostType };
  content_override?: string | null;
};

export type PublicationIn = {
  content?: string | null;
  media?: MediaIn[];
  scheduled_for?: string | null;
  draft?: boolean;
  targets: TargetIn[];
};

export type PublicationPatchIn = Partial<PublicationIn>;

export type PublicationState =
  | "draft"
  | "scheduled"
  | "publishing"
  | "published"
  | "partially_published"
  | "failed";

export type TargetState = "pending" | "publishing" | "published" | "failed";

export type MetricName =
  | "views"
  | "reach"
  | "likes"
  | "comments"
  | "shares"
  | "saves"
  | "interactions";

export type Metrics = Partial<Record<MetricName, number>>;

export type PublicationMedia = {
  type: "image" | "video";
  url: string;
  media_id?: number;
};

export type PublicationTarget = {
  id: number;
  channel: Channel;
  settings: { post_type?: string };
  content_override: string | null;
  state: TargetState;
  external_id: string | null;
  permalink: string | null;
  error_code: string | null;
  error_message: string | null;
  attempts: number;
  published_at: string | null;
  metrics: Metrics;
  metrics_updated_at: string | null;
  metrics_error: string | null;
};

export type Publication = {
  id: number;
  account_id: number;
  content: string | null;
  media: PublicationMedia[];
  scheduled_for: string | null;
  state: PublicationState;
  created_by_id: number | null;
  published_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  targets: PublicationTarget[];
};

export type ConnectionField = {
  name: string;
  label: string;
  help: string;
  secret: boolean;
};

export type NetworkOption = {
  network: string;
  label: string;
  configured: boolean;
  kind: "authorize" | "form";
  fields: ConnectionField[];
};

export type AnalyticsSeriesPoint = {
  date: string;
  followers?: number;
} & Pick<Metrics, "views" | "reach" | "interactions">;

export type AnalyticsChannel = {
  channel: Channel;
  posts: number;
  metrics: Metrics;
  followers: number | null;
  followers_change: number | null;
  series: AnalyticsSeriesPoint[];
};

export type AnalyticsTopPost = {
  publication_id: number;
  target_id: number;
  channel: Channel | null;
  content: string;
  permalink: string | null;
  published_at: string | null;
  metrics: Metrics;
};

export type Analytics = {
  from: string;
  to: string;
  totals: { posts: number } & Metrics;
  channels: AnalyticsChannel[];
  top_posts: AnalyticsTopPost[];
};

export type Signature = {
  id: number;
  content: string;
  auto_add: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type PublicationSetMedia =
  | { media_id: number; type: "image" | "video"; url: string }
  | { type: "image" | "video"; url: string };

export type PublicationSetTarget = {
  channel_id: number;
  channel: Channel | null;
  settings: { post_type?: string };
  content_override: string | null;
};

export type PublicationSet = {
  id: number;
  name: string;
  content: string | null;
  media: PublicationSetMedia[];
  targets: PublicationSetTarget[];
  created_at: string | null;
  updated_at: string | null;
};

export type PublicationSetIn = {
  name: string;
  content?: string | null;
  media?: MediaIn[];
  targets: TargetIn[];
};

export type ParsedPublicationError = {
  message: string;
  errors: string[];
};

/**
 * Extract both ``message`` and ``errors[]`` from backend 422 responses
 * (``{"message": string, "errors"?: string[]}``) verbatim.
 */
export function parsePublicationError(
  err: unknown,
  fallback = "Ocurrió un error al procesar la solicitud.",
): ParsedPublicationError {
  if (err instanceof ApiError) {
    const body =
      err.body && typeof err.body === "object"
        ? (err.body as Record<string, unknown>)
        : null;
    const rawErrors = Array.isArray(body?.errors)
      ? body.errors.filter((e): e is string => typeof e === "string")
      : [];
    const msg =
      typeof body?.message === "string" ? body.message : err.message || fallback;
    return { message: msg, errors: rawErrors };
  }
  if (err && typeof err === "object" && "message" in err) {
    const m = (err as { message?: unknown }).message;
    if (typeof m === "string" && m.trim()) {
      return { message: m, errors: [] };
    }
  }
  return { message: fallback, errors: [] };
}

export function canEditPublication(state: PublicationState): boolean {
  return state === "draft" || state === "scheduled";
}

export function canDeletePublication(state: PublicationState): boolean {
  return state === "draft" || state === "scheduled" || state === "failed";
}

export function canRetryPublication(state: PublicationState): boolean {
  return state === "failed" || state === "partially_published";
}

export function canRefreshMetrics(state: PublicationState): boolean {
  return state === "published" || state === "partially_published";
}

export const PUBLICATIONS_PAGE_SIZE = 50;

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/publications`;
}

function invalidatePublications(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
  publicationId?: number,
) {
  qc.invalidateQueries({ queryKey: ["publications", accountId] });
  if (publicationId !== undefined) {
    qc.invalidateQueries({
      queryKey: ["publication", accountId, publicationId],
    });
  }
  qc.invalidateQueries({ queryKey: ["publication-analytics", accountId] });
}

export function usePublicationChannels(accountId: string) {
  return useQuery({
    queryKey: ["publication-channels", accountId],
    queryFn: () => apiFetch<Channel[]>(`${base(accountId)}/channels`),
  });
}

export function usePublicationNetworks(accountId: string, enabled = true) {
  return useQuery({
    queryKey: ["publication-networks", accountId],
    queryFn: () => apiFetch<NetworkOption[]>(`${base(accountId)}/networks`),
    enabled,
  });
}

export function useAuthorizeChannel(accountId: string) {
  return useMutation({
    mutationFn: (network: string) =>
      apiFetch<{ authorize_url: string }>(
        `${base(accountId)}/channels/connect/${encodeURIComponent(network)}`,
        { method: "POST" },
      ),
  });
}

export function useConnectFormChannel(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { network: string; fields: Record<string, string> }) =>
      apiFetch<{ channel: Channel }>(
        `${base(accountId)}/channels/connect/${encodeURIComponent(input.network)}`,
        {
          method: "POST",
          body: JSON.stringify({ fields: input.fields }),
        },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["publication-channels", accountId] });
      qc.invalidateQueries({ queryKey: ["publication-analytics", accountId] });
    },
  });
}

export function useDeleteChannel(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (channelId: number) =>
      apiFetch<Record<string, never>>(
        `${base(accountId)}/channels/${channelId}`,
        { method: "DELETE" },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["publication-channels", accountId] });
      invalidatePublications(qc, accountId);
    },
  });
}

export type PublicationsRangeFilters = {
  from?: string;
  to?: string;
  state?: PublicationState;
  channel_id?: number;
};

/**
 * ``GET /publications`` returns a fixed 50 items per page; to cover a calendar
 * range, fetch sequential pages until a batch returns fewer than 50 items.
 */
export async function fetchAllPublications(
  accountId: string,
  filters: PublicationsRangeFilters = {},
): Promise<Publication[]> {
  const all: Publication[] = [];
  const maxPages = 100;

  for (let page = 1; page <= maxPages; page++) {
    const sp = new URLSearchParams();
    if (filters.from) sp.set("from", filters.from);
    if (filters.to) sp.set("to", filters.to);
    if (filters.state) sp.set("state", filters.state);
    if (filters.channel_id !== undefined) {
      sp.set("channel_id", String(filters.channel_id));
    }
    if (page > 1) sp.set("page", String(page));
    const qs = sp.toString();
    const batch = await apiFetch<Publication[]>(
      `${base(accountId)}${qs ? `?${qs}` : ""}`,
    );
    all.push(...batch);
    if (batch.length < PUBLICATIONS_PAGE_SIZE) break;
  }

  return all;
}

export function usePublicationsRange(
  accountId: string,
  filters: PublicationsRangeFilters = {},
) {
  const { from, to, state, channel_id } = filters;
  return useQuery({
    queryKey: [
      "publications",
      accountId,
      from ?? null,
      to ?? null,
      state ?? null,
      channel_id ?? null,
    ],
    queryFn: () =>
      fetchAllPublications(accountId, { from, to, state, channel_id }),
  });
}

export function usePublication(
  accountId: string,
  publicationId: number | null,
  initialData?: Publication,
) {
  return useQuery({
    queryKey: ["publication", accountId, publicationId],
    queryFn: () =>
      apiFetch<Publication>(`${base(accountId)}/${publicationId}`),
    enabled: publicationId !== null,
    initialData,
  });
}

export function useCreatePublication(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: PublicationIn) =>
      apiFetch<Publication>(base(accountId), {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => invalidatePublications(qc, accountId),
  });
}

export function useUpdatePublication(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: PublicationPatchIn }) =>
      apiFetch<Publication>(`${base(accountId)}/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify(input.patch),
      }),
    onSuccess: (_data, vars) => invalidatePublications(qc, accountId, vars.id),
  });
}

export function useDeletePublication(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: (_data, id) => invalidatePublications(qc, accountId, id),
  });
}

export function useRetryPublication(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Publication>(`${base(accountId)}/${id}/retry`, {
        method: "POST",
      }),
    onSuccess: (_data, id) => invalidatePublications(qc, accountId, id),
  });
}

export function useRefreshPublicationMetrics(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Publication>(`${base(accountId)}/${id}/refresh_metrics`, {
        method: "POST",
      }),
    onSuccess: (_data, id) => invalidatePublications(qc, accountId, id),
  });
}

export type AnalyticsFilters = {
  from?: string;
  to?: string;
  channel_id?: number;
  enabled?: boolean;
};

export function usePublicationAnalytics(
  accountId: string,
  filters: AnalyticsFilters = {},
) {
  const { from, to, channel_id, enabled = true } = filters;
  return useQuery({
    queryKey: [
      "publication-analytics",
      accountId,
      from ?? null,
      to ?? null,
      channel_id ?? null,
    ],
    queryFn: () => {
      const sp = new URLSearchParams();
      if (from) sp.set("from", from);
      if (to) sp.set("to", to);
      if (channel_id !== undefined) sp.set("channel_id", String(channel_id));
      const qs = sp.toString();
      return apiFetch<Analytics>(
        `${base(accountId)}/analytics${qs ? `?${qs}` : ""}`,
      );
    },
    enabled,
  });
}

export function usePublicationSignatures(accountId: string, enabled = true) {
  return useQuery({
    queryKey: ["publication-signatures", accountId],
    queryFn: () => apiFetch<Signature[]>(`${base(accountId)}/signatures`),
    enabled,
  });
}

export function usePublicationSets(accountId: string, enabled = true) {
  return useQuery({
    queryKey: ["publication-sets", accountId],
    queryFn: () => apiFetch<PublicationSet[]>(`${base(accountId)}/sets`),
    enabled,
  });
}

export function useCreatePublicationSet(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: PublicationSetIn) =>
      apiFetch<PublicationSet>(`${base(accountId)}/sets`, {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["publication-sets", accountId] });
    },
  });
}
