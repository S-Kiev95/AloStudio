import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { ApiError, messageFromBody } from "./errors";
import { apiFetch } from "./fetcher";

export type MediaKind = "image" | "video";

export type MediaAsset = {
  id: number;
  kind: MediaKind;
  filename: string | null;
  content_type: string | null;
  size_bytes: number;
  url: string;
  uploaded_by_id: number | null;
  created_at: string | null;
};

export const MEDIA_PAGE_SIZE = 50;
/** Presigned preview URLs expire after 1 hour; keep staleTime strictly below. */
export const MEDIA_STALE_TIME = 30 * 60_000;

export const MAX_IMAGE_BYTES = 30 * 1024 * 1024;
export const MAX_VIDEO_BYTES = 200 * 1024 * 1024;

const IMAGE_EXT_RE = /\.(jpe?g|png|gif|webp|avif|bmp|heic|heif)$/i;
const VIDEO_EXT_RE = /\.(mp4|mov|webm|m4v|avi|mkv)$/i;

export function inferMediaKind(file: File): MediaKind | null {
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";
  if (IMAGE_EXT_RE.test(file.name)) return "image";
  if (VIDEO_EXT_RE.test(file.name)) return "video";
  return null;
}

/** Validate type and byte size before uploading to ``POST /media``. */
export function validateMediaFile(file: File): string | null {
  const kind = inferMediaKind(file);
  if (!kind) {
    return "Formato no soportado. Subí una imagen o un video.";
  }
  if (kind === "image" && file.size > MAX_IMAGE_BYTES) {
    return "La imagen supera el límite de 30 MB.";
  }
  if (kind === "video" && file.size > MAX_VIDEO_BYTES) {
    return "El video supera el límite de 200 MB.";
  }
  return null;
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(kb >= 100 ? 0 : 1)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(mb >= 100 ? 0 : 1)} MB`;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/backend";

function base(accountId: string): string {
  return `/api/v1/accounts/${accountId}/media`;
}

export async function fetchMediaPage(
  accountId: string,
  params: { kind?: MediaKind; page?: number } = {},
): Promise<MediaAsset[]> {
  const sp = new URLSearchParams();
  if (params.kind) sp.set("kind", params.kind);
  if (params.page && params.page > 1) sp.set("page", String(params.page));
  const qs = sp.toString();
  return apiFetch<MediaAsset[]>(`${base(accountId)}${qs ? `?${qs}` : ""}`);
}

export function useMediaAssets(
  accountId: string,
  params: { kind?: MediaKind; page?: number } = {},
) {
  const { kind, page } = params;
  return useQuery({
    queryKey: ["media", accountId, "page", kind ?? "all", page ?? 1],
    queryFn: () => fetchMediaPage(accountId, { kind, page }),
    staleTime: MEDIA_STALE_TIME,
    refetchOnWindowFocus: true,
  });
}

export function useInfiniteMediaAssets(
  accountId: string,
  params: { kind?: MediaKind; enabled?: boolean } = {},
) {
  const { kind, enabled = true } = params;
  return useInfiniteQuery({
    queryKey: ["media", accountId, "infinite", kind ?? "all"],
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      fetchMediaPage(accountId, { kind, page: pageParam }),
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length >= MEDIA_PAGE_SIZE ? allPages.length + 1 : undefined,
    staleTime: MEDIA_STALE_TIME,
    refetchOnWindowFocus: true,
    enabled,
  });
}

function invalidateMedia(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["media", accountId] });
}

export function useUploadMedia(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file, file.name);
      const res = await fetch(`${API_BASE}${base(accountId)}`, {
        method: "POST",
        body: form,
      });
      const text = await res.text();
      let body: unknown = null;
      if (text) {
        try {
          body = JSON.parse(text);
        } catch {
          body = text;
        }
      }
      if (
        res.status === 401 &&
        typeof window !== "undefined" &&
        !(
          typeof body === "object" &&
          body !== null &&
          (body as { code?: unknown }).code === "not_authorized"
        )
      ) {
        window.location.href = "/login";
      }
      if (!res.ok) {
        throw new ApiError(
          res.status,
          messageFromBody(body, `No se pudo subir el archivo (${res.status}).`),
          body,
        );
      }
      return body as MediaAsset;
    },
    onSuccess: () => invalidateMedia(qc, accountId),
  });
}

export function useDeleteMedia(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(`${base(accountId)}/${id}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidateMedia(qc, accountId),
  });
}
