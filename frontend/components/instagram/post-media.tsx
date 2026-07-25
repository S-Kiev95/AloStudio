"use client";

import {
  CircleDashed,
  Film,
  Image as ImageIcon,
  Images,
  type LucideIcon,
  Video,
} from "lucide-react";
import { useState } from "react";

import type { InstagramPost, MediaType } from "@/lib/api/instagram-posts";
import { cn } from "@/lib/utils";

export const MEDIA_ICON: Record<MediaType, LucideIcon> = {
  IMAGE: ImageIcon,
  VIDEO: Video,
  REELS: Film,
  CAROUSEL: Images,
  STORIES: CircleDashed,
};

/** One piece of media the composer stored in a post's untyped `source` blob. */
export type MediaItem = { kind: "image" | "video"; url: string };

function itemFrom(o: Record<string, unknown>): MediaItem | null {
  // Prefer a still: a video's cover is the only thing we can render as an
  // image, and `video_url` needs the <video> player.
  if (typeof o.image_url === "string" && o.image_url) {
    return { kind: "image", url: o.image_url };
  }
  if (typeof o.cover_url === "string" && o.cover_url) {
    return { kind: "image", url: o.cover_url };
  }
  if (typeof o.video_url === "string" && o.video_url) {
    return { kind: "video", url: o.video_url };
  }
  return null;
}

/** Every media item in a post, in order (carousels yield one per child). */
export function mediaItems(source: Record<string, unknown>): MediaItem[] {
  const kids = source.children;
  if (Array.isArray(kids)) {
    const out: MediaItem[] = [];
    for (const k of kids) {
      if (k && typeof k === "object") {
        const item = itemFrom(k as Record<string, unknown>);
        if (item) out.push(item);
      }
    }
    if (out.length) return out;
  }
  const top = itemFrom(source);
  return top ? [top] : [];
}

/** The first still usable as a thumbnail, or null (video-only, no cover). */
export function thumbFrom(source: Record<string, unknown>): string | null {
  return mediaItems(source).find((m) => m.kind === "image")?.url ?? null;
}

/** A media-type icon on a neutral tile — the fallback whenever there's no
 *  renderable still (video without a cover, expired signed URL). */
export function MediaIconTile({
  mediaType,
  className,
}: {
  mediaType: MediaType;
  className?: string;
}) {
  const Icon = MEDIA_ICON[mediaType] ?? ImageIcon;
  return (
    <span
      className={cn(
        "grid shrink-0 place-items-center rounded-lg border border-border bg-surface-2 text-fg-muted",
        className,
      )}
    >
      <Icon className="h-5 w-5" aria-hidden />
    </span>
  );
}

/** Square thumbnail for a list row: the stored still, else an icon tile. */
export function PostThumb({ post }: { post: InstagramPost }) {
  const [broken, setBroken] = useState(false);
  const url = thumbFrom(post.source);
  if (!url || broken) {
    return <MediaIconTile mediaType={post.media_type} className="h-12 w-12" />;
  }
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

/** One rendered frame of a post's media (image or playable video). */
function MediaFrame({ item }: { item: MediaItem }) {
  const [broken, setBroken] = useState(false);

  if (item.kind === "video") {
    return (
      <video
        controls
        preload="metadata"
        src={item.url}
        className="max-h-[28rem] w-full rounded-lg border border-border bg-black object-contain"
      >
        <track kind="captions" />
      </video>
    );
  }
  if (broken) {
    return (
      <div className="grid h-48 w-full place-items-center rounded-lg border border-border bg-surface-2 text-xs text-fg-muted">
        No se pudo cargar la vista previa.
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={item.url}
      alt="Vista previa de la publicación"
      loading="lazy"
      onError={() => setBroken(true)}
      className="max-h-[28rem] w-full rounded-lg border border-border bg-surface-2 object-contain"
    />
  );
}

/**
 * The post's media, full-width — the hero of a post detail on a platform
 * that is fundamentally visual. Carousels get a thumbnail strip to page
 * through; a post with no renderable media renders nothing.
 */
export function PostMediaPreview({ post }: { post: InstagramPost }) {
  const items = mediaItems(post.source);
  const [index, setIndex] = useState(0);
  if (items.length === 0) return null;

  const current = items[Math.min(index, items.length - 1)];

  return (
    <div className="space-y-2">
      <MediaFrame item={current} />
      {items.length > 1 ? (
        <div
          className="flex gap-2 overflow-x-auto pb-1"
          aria-label="Elementos del carrusel"
        >
          {items.map((item, i) => (
            <button
              key={`${item.url}-${i}`}
              type="button"
              onClick={() => setIndex(i)}
              aria-current={i === index ? "true" : undefined}
              aria-label={`Elemento ${i + 1} de ${items.length}`}
              className={cn(
                "relative h-14 w-14 shrink-0 overflow-hidden rounded-lg border-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                i === index ? "border-primary" : "border-border opacity-70 hover:opacity-100",
              )}
            >
              {item.kind === "image" ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={item.url}
                  alt=""
                  loading="lazy"
                  className="h-full w-full object-cover"
                />
              ) : (
                <span className="grid h-full w-full place-items-center bg-surface-2 text-fg-muted">
                  <Video className="h-4 w-4" aria-hidden />
                </span>
              )}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
