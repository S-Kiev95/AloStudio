"use client";

import { ChevronRight, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { SegmentedControl } from "@/components/ui/segmented-control";
import { type InstagramPost, useInstagramPosts } from "@/lib/api/instagram-posts";
import { relativeTime } from "@/lib/time";

import { PostThumb } from "./post-media";
import { StateBadge } from "./state-badge";

const STATE_TABS = [
  { value: undefined, label: "Todas" },
  { value: "pending", label: "Pendientes" },
  { value: "published", label: "Publicadas" },
  { value: "failed", label: "Fallidas" },
] as const;

export function PostList({ accountId }: { accountId: string }) {
  const [state, setState] = useState<string | undefined>(undefined);
  const { data, isLoading, isError } = useInstagramPosts(accountId, { state });

  return (
    <div className="space-y-3">
      <SegmentedControl
        ariaLabel="Filtrar publicaciones"
        size="sm"
        value={state}
        onValueChange={setState}
        options={STATE_TABS}
      />

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
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
          <ul className="divide-y divide-glass">
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
    <li className="flex items-center gap-1 pr-2 transition-colors hover:bg-hover-glass">
      <Link
        href={`/accounts/${accountId}/instagram/posts/${post.id}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-neon"
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
            <span className="truncate font-numeric tabular-nums">{when}</span>
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
          className="rounded-md p-1.5 text-fg-muted hover:bg-hover-glass hover:text-fg"
        >
          <ExternalLink className="h-4 w-4" aria-hidden />
        </a>
      ) : null}
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
