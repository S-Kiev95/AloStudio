"use client";

import {
  ChevronRight,
  CircleDashed,
  ExternalLink,
  Film,
  Image as ImageIcon,
  Images,
  type LucideIcon,
  Video,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import {
  type InstagramPost,
  type MediaType,
  useInstagramPosts,
} from "@/lib/api/instagram-posts";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";

import { StateBadge } from "./state-badge";

const STATE_TABS = [
  { key: undefined, label: "Todas" },
  { key: "pending", label: "Pendientes" },
  { key: "published", label: "Publicadas" },
  { key: "failed", label: "Fallidas" },
] as const;

const MEDIA_ICON: Record<MediaType, LucideIcon> = {
  IMAGE: ImageIcon,
  VIDEO: Video,
  REELS: Film,
  CAROUSEL: Images,
  STORIES: CircleDashed,
};

/** Pull the first usable still from a post's untyped `source` blob (the URLs
 *  the composer stored) so the row can show a real thumbnail; null when the
 *  post is video-only with no cover. */
function thumbFrom(source: Record<string, unknown>): string | null {
  const pick = (o: Record<string, unknown>): string | null => {
    if (typeof o.image_url === "string") return o.image_url;
    if (typeof o.cover_url === "string") return o.cover_url;
    return null;
  };
  const top = pick(source);
  if (top) return top;
  const kids = source.children;
  if (Array.isArray(kids)) {
    for (const k of kids) {
      if (k && typeof k === "object") {
        const u = pick(k as Record<string, unknown>);
        if (u) return u;
      }
    }
  }
  return null;
}

/** Post thumbnail — the stored still when it loads, otherwise a media-type
 *  icon tile (covers video-only posts and expired signed URLs). */
function PostThumb({ post }: { post: InstagramPost }) {
  const [broken, setBroken] = useState(false);
  const url = thumbFrom(post.source);
  const Icon = MEDIA_ICON[post.media_type] ?? ImageIcon;
  if (url && !broken) {
    return (
      <span className="relative h-12 w-12 shrink-0 overflow-hidden rounded-lg border border-border bg-surface-2">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={url}
          alt=""
          loading="lazy"
          onError={() => setBroken(true)}
          className="h-full w-full object-cover"
        />
      </span>
    );
  }
  return (
    <span className="grid h-12 w-12 shrink-0 place-items-center rounded-lg border border-border bg-surface-2 text-fg-muted">
      <Icon className="h-5 w-5" aria-hidden />
    </span>
  );
}

export function PostList({ accountId }: { accountId: string }) {
  const [state, setState] = useState<string | undefined>(undefined);
  const { data, isLoading, isError } = useInstagramPosts(accountId, { state });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {STATE_TABS.map((t) => (
          <button
            key={t.label}
            type="button"
            onClick={() => setState(t.key)}
            aria-pressed={state === t.key}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              state === t.key
                ? "bg-surface-2 font-semibold text-fg"
                : "border border-border bg-surface text-fg hover:bg-surface-2",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar las publicaciones.
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay publicaciones todavía.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {data?.map((p) => (
              <PostRow key={p.id} accountId={accountId} post={p} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function PostRow({ accountId, post }: { accountId: string; post: InstagramPost }) {
  const when =
    post.state === "published" && post.published_at
      ? `Publicado ${new Date(post.published_at).toLocaleString()}`
      : post.scheduled_for
        ? `Programado ${new Date(post.scheduled_for).toLocaleString()}`
        : `Creado ${relativeTime(post.created_at)}`;

  return (
    <li className="flex items-center gap-1 pr-2 transition-colors hover:bg-surface-2">
      <Link
        href={`/accounts/${accountId}/instagram/posts/${post.id}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <PostThumb post={post} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm text-fg">
            {post.caption?.trim() || (
              <span className="text-fg-muted">(sin caption)</span>
            )}
          </p>
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-fg-muted">
            <span className="font-medium uppercase tracking-wide">
              {post.media_type}
            </span>
            <span aria-hidden>·</span>
            <span className="truncate">{when}</span>
          </p>
          {post.state === "failed" && post.error_message ? (
            <p className="truncate text-xs text-danger">{post.error_message}</p>
          ) : null}
        </div>
        <StateBadge state={post.state} />
      </Link>
      {post.ig_permalink ? (
        <a
          href={post.ig_permalink}
          target="_blank"
          rel="noreferrer"
          aria-label="Ver en Instagram"
          className="rounded-md p-1.5 text-fg-muted hover:bg-surface"
        >
          <ExternalLink className="h-4 w-4" aria-hidden />
        </a>
      ) : null}
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
