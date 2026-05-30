"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useInstagramInboxes } from "@/lib/api/instagram";
import {
  type CreatePostInput,
  type MediaType,
  useCreatePost,
  useProducts,
} from "@/lib/api/instagram-posts";
import { cn } from "@/lib/utils";

const MEDIA_TYPES: { value: MediaType; label: string }[] = [
  { value: "IMAGE", label: "Imagen" },
  { value: "VIDEO", label: "Video" },
  { value: "REELS", label: "Reel" },
  { value: "CAROUSEL", label: "Carrusel" },
  { value: "STORIES", label: "Story" },
];

const selectClass =
  "h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

type Child = { kind: "image" | "video"; url: string };

export function PostComposer({
  accountId,
  onCreated,
}: {
  accountId: string;
  onCreated?: () => void;
}) {
  const inboxes = useInstagramInboxes(accountId);
  const products = useProducts(accountId);
  const create = useCreatePost(accountId);

  const [inboxId, setInboxId] = useState<string>("");
  const [mediaType, setMediaType] = useState<MediaType>("IMAGE");
  const [caption, setCaption] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [coverUrl, setCoverUrl] = useState("");
  const [shareToFeed, setShareToFeed] = useState(true);
  const [storyKind, setStoryKind] = useState<"image" | "video">("image");
  const [storyUrl, setStoryUrl] = useState("");
  const [children, setChildren] = useState<Child[]>([
    { kind: "image", url: "" },
    { kind: "image", url: "" },
  ]);
  const [scheduleLater, setScheduleLater] = useState(false);
  const [scheduledFor, setScheduledFor] = useState("");
  const [productIds, setProductIds] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);

  function buildSource(): Record<string, unknown> | null {
    switch (mediaType) {
      case "IMAGE":
        return imageUrl ? { image_url: imageUrl } : null;
      case "VIDEO":
        return videoUrl ? { video_url: videoUrl } : null;
      case "REELS":
        return videoUrl
          ? {
              video_url: videoUrl,
              ...(coverUrl ? { cover_url: coverUrl } : {}),
              share_to_feed: shareToFeed,
            }
          : null;
      case "STORIES":
        return storyUrl
          ? storyKind === "video"
            ? { video_url: storyUrl }
            : { image_url: storyUrl }
          : null;
      case "CAROUSEL": {
        const valid = children.filter((c) => c.url.trim());
        if (valid.length < 2) return null;
        return {
          children: valid.map((c) =>
            c.kind === "video" ? { video_url: c.url } : { image_url: c.url },
          ),
        };
      }
    }
  }

  async function submit() {
    setError(null);
    if (!inboxId) return setError("Elegí una cuenta de Instagram.");
    const source = buildSource();
    if (!source)
      return setError(
        mediaType === "CAROUSEL"
          ? "El carrusel necesita al menos 2 elementos con URL."
          : "Completá la URL del contenido.",
      );

    const input: CreatePostInput = {
      inbox_id: Number(inboxId),
      media_type: mediaType,
      source,
      ...(caption.trim() ? { caption: caption.trim() } : {}),
      ...(productIds.length ? { product_ids: productIds } : {}),
    };
    if (scheduleLater && scheduledFor) {
      input.scheduled_for = new Date(scheduledFor).toISOString();
    }

    try {
      await create.mutateAsync(input);
      // reset
      setImageUrl("");
      setVideoUrl("");
      setCoverUrl("");
      setStoryUrl("");
      setCaption("");
      setChildren([
        { kind: "image", url: "" },
        { kind: "image", url: "" },
      ]);
      setProductIds([]);
      setScheduleLater(false);
      setScheduledFor("");
      onCreated?.();
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo crear la publicación.",
      );
    }
  }

  function toggleProduct(id: number) {
    setProductIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  return (
    <div className="space-y-4">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="c-inbox" required>
            Cuenta
          </Label>
          <select
            id="c-inbox"
            className={selectClass}
            value={inboxId}
            onChange={(e) => setInboxId(e.target.value)}
          >
            <option value="">Elegí una cuenta…</option>
            {inboxes.data?.map((ib) => (
              <option key={ib.id} value={ib.id}>
                {ib.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="c-type">Tipo</Label>
          <select
            id="c-type"
            className={selectClass}
            value={mediaType}
            onChange={(e) => setMediaType(e.target.value as MediaType)}
          >
            {MEDIA_TYPES.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Source fields per media type */}
      {mediaType === "IMAGE" ? (
        <UrlField id="c-img" label="URL de imagen (JPEG público)" value={imageUrl} onChange={setImageUrl} />
      ) : null}
      {mediaType === "VIDEO" ? (
        <UrlField id="c-vid" label="URL de video (MP4)" value={videoUrl} onChange={setVideoUrl} />
      ) : null}
      {mediaType === "REELS" ? (
        <>
          <UrlField id="c-reel" label="URL de video" value={videoUrl} onChange={setVideoUrl} />
          <UrlField id="c-cover" label="URL de portada (opcional)" value={coverUrl} onChange={setCoverUrl} required={false} />
          <label className="flex items-center gap-2 text-sm text-fg">
            <input type="checkbox" checked={shareToFeed} onChange={(e) => setShareToFeed(e.target.checked)} />
            También compartir en el feed
          </label>
        </>
      ) : null}
      {mediaType === "STORIES" ? (
        <div className="space-y-1.5">
          <div className="flex gap-3 text-sm">
            <label className="flex items-center gap-1.5">
              <input type="radio" checked={storyKind === "image"} onChange={() => setStoryKind("image")} /> Imagen
            </label>
            <label className="flex items-center gap-1.5">
              <input type="radio" checked={storyKind === "video"} onChange={() => setStoryKind("video")} /> Video
            </label>
          </div>
          <UrlField id="c-story" label="URL del contenido" value={storyUrl} onChange={setStoryUrl} />
        </div>
      ) : null}
      {mediaType === "CAROUSEL" ? (
        <div className="space-y-2">
          <Label>Elementos (2–10)</Label>
          {children.map((c, i) => (
            <div key={i} className="flex items-center gap-2">
              <select
                className="h-11 rounded-md border border-border bg-surface px-2 text-sm"
                value={c.kind}
                onChange={(e) =>
                  setChildren((prev) =>
                    prev.map((x, j) =>
                      j === i ? { ...x, kind: e.target.value as "image" | "video" } : x,
                    ),
                  )
                }
              >
                <option value="image">Imagen</option>
                <option value="video">Video</option>
              </select>
              <Input
                placeholder="URL"
                value={c.url}
                onChange={(e) =>
                  setChildren((prev) =>
                    prev.map((x, j) => (j === i ? { ...x, url: e.target.value } : x)),
                  )
                }
              />
              {children.length > 2 ? (
                <button
                  type="button"
                  aria-label="Quitar"
                  onClick={() => setChildren((prev) => prev.filter((_, j) => j !== i))}
                  className="rounded-md p-2 text-fg-muted hover:bg-surface-2"
                >
                  <X className="h-4 w-4" aria-hidden />
                </button>
              ) : null}
            </div>
          ))}
          {children.length < 10 ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setChildren((prev) => [...prev, { kind: "image", url: "" }])}
            >
              <Plus className="h-4 w-4" aria-hidden /> Agregar elemento
            </Button>
          ) : null}
        </div>
      ) : null}

      <div className="space-y-1.5">
        <Label htmlFor="c-caption">Caption</Label>
        <Textarea id="c-caption" rows={3} value={caption} onChange={(e) => setCaption(e.target.value)} maxLength={2200} />
      </div>

      {/* Products */}
      {products.data?.length ? (
        <div className="space-y-1.5">
          <Label>Productos vinculados</Label>
          <div className="flex flex-wrap gap-1.5">
            {products.data.map((p) => {
              const on = productIds.includes(p.id);
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => toggleProduct(p.id)}
                  aria-pressed={on}
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-xs",
                    on ? "border-primary bg-primary text-primary-fg" : "border-border text-fg-muted hover:bg-surface-2",
                  )}
                >
                  {p.name}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      {/* Schedule */}
      <div className="space-y-1.5">
        <label className="flex items-center gap-2 text-sm text-fg">
          <input type="checkbox" checked={scheduleLater} onChange={(e) => setScheduleLater(e.target.checked)} />
          Programar para más tarde
        </label>
        {scheduleLater ? (
          <Input type="datetime-local" value={scheduledFor} onChange={(e) => setScheduledFor(e.target.value)} />
        ) : (
          <p className="text-xs text-fg-muted">Se publica ahora (en el próximo ciclo del worker).</p>
        )}
      </div>

      <Button onClick={submit} loading={create.isPending}>
        {scheduleLater ? "Programar publicación" : "Publicar"}
      </Button>
    </div>
  );
}

function UrlField({
  id,
  label,
  value,
  onChange,
  required = true,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} required={required}>
        {label}
      </Label>
      <Input id={id} type="url" value={value} onChange={(e) => onChange(e.target.value)} placeholder="https://…" />
    </div>
  );
}
