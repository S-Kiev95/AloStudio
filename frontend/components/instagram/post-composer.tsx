"use client";

import { Plus, Upload, X } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useInstagramInboxes } from "@/lib/api/instagram";
import { uploadInstagramMedia } from "@/lib/api/uploads";
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
        <UrlField id="c-img" label="Imagen" value={imageUrl} onChange={setImageUrl} accountId={accountId} uploadKind="image" />
      ) : null}
      {mediaType === "VIDEO" ? (
        <UrlField id="c-vid" label="Video (MP4)" value={videoUrl} onChange={setVideoUrl} accountId={accountId} uploadKind="video" />
      ) : null}
      {mediaType === "REELS" ? (
        <>
          <UrlField id="c-reel" label="Video" value={videoUrl} onChange={setVideoUrl} accountId={accountId} uploadKind="video" />
          <UrlField id="c-cover" label="Portada (opcional)" value={coverUrl} onChange={setCoverUrl} required={false} accountId={accountId} uploadKind="image" />
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
          <UrlField
            id="c-story"
            label={storyKind === "image" ? "Imagen" : "Video"}
            value={storyUrl}
            onChange={setStoryUrl}
            accountId={accountId}
            uploadKind={storyKind}
          />
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
              <CompactImageUpload
                accountId={accountId}
                kind={c.kind}
                label={`Subir ${c.kind === "image" ? "imagen" : "video"} del elemento ${i + 1}`}
                onUploaded={(url) =>
                  setChildren((prev) =>
                    prev.map((x, j) => (j === i ? { ...x, url } : x)),
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
                    on ? "border-primary bg-surface-2 font-semibold text-fg" : "border-border text-fg-muted hover:bg-surface-2",
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

/** Icon-sized uploader for the carousel rows, where a full dropzone would
 *  break the inline layout. Drop still works — the button is a drop target. */
function CompactImageUpload({
  accountId,
  kind,
  label,
  onUploaded,
}: {
  accountId: string;
  kind: "image" | "video";
  label: string;
  onUploaded: (url: string) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function upload(file: File) {
    setUploading(true);
    try {
      onUploaded(await uploadInstagramMedia(accountId, file));
    } catch {
      /* the row keeps its URL input as the manual fallback */
    } finally {
      setUploading(false);
    }
  }

  return (
    <>
      <input
        ref={fileRef}
        type="file"
        accept={kind === "video" ? "video/*" : "image/*"}
        className="hidden"
        aria-label={label}
        tabIndex={-1}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) void upload(file);
        }}
      />
      <button
        type="button"
        aria-label={label}
        title={label}
        disabled={uploading}
        onClick={() => fileRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files?.[0];
          if (file) void upload(file);
        }}
        className={cn(
          "rounded-md border border-dashed p-2 transition-colors",
          dragging
            ? "border-primary bg-primary/10 text-primary"
            : "border-border text-fg-muted hover:text-fg",
          uploading && "opacity-60",
        )}
      >
        <Upload className="h-4 w-4" aria-hidden />
      </button>
    </>
  );
}

function UrlField({
  id,
  label,
  value,
  onChange,
  required = true,
  accountId,
  uploadKind,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  accountId?: string;
  /** Enables drop/pick upload. Images are re-encoded to JPEG server-side;
   *  video is stored as-is (we don't transcode), so it must already be
   *  MP4/H.264 for Meta to accept it. */
  uploadKind?: "image" | "video";
}) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const uploadable = Boolean(accountId && uploadKind);
  const isVideo = uploadKind === "video";

  async function upload(file: File) {
    if (!accountId) return;
    setUploadError(null);
    setUploading(true);
    try {
      onChange(await uploadInstagramMedia(accountId, file));
    } catch (e) {
      setUploadError(
        e instanceof Error ? e.message : "No se pudo subir la imagen.",
      );
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void upload(file);
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} required={required}>
        {label}
      </Label>
      <Input id={id} type="url" value={value} onChange={(e) => onChange(e.target.value)} placeholder="https://…" />
      {uploadable ? (
        <>
          <input
            ref={fileRef}
            type="file"
            accept={isVideo ? "video/*" : "image/*"}
            className="hidden"
            aria-label={`Subir ${isVideo ? "video" : "imagen"} para ${label}`}
            tabIndex={-1}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = ""; // let the same file be re-picked
              if (file) void upload(file);
            }}
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            disabled={uploading}
            className={cn(
              "flex w-full items-center justify-center gap-2 rounded-md border border-dashed px-3 py-4 text-xs transition-colors",
              dragging
                ? "border-primary bg-primary/10 text-primary"
                : "border-border text-fg-muted hover:border-primary/60 hover:text-fg",
              uploading && "opacity-60",
            )}
          >
            <Upload className="h-4 w-4 shrink-0" aria-hidden />
            {uploading
              ? isVideo
                ? "Subiendo video…"
                : "Subiendo y convirtiendo…"
              : dragging
                ? `Soltá ${isVideo ? "el video" : "la imagen"} acá`
                : `Arrastrá ${isVideo ? "un video" : "una imagen"} o hacé clic para elegirlo`}
          </button>
          {uploadError ? (
            <p role="alert" className="text-xs text-danger">
              {uploadError}
            </p>
          ) : (
            <p className="text-xs text-fg-muted">
              {isVideo
                ? "Se sube tal cual: Instagram exige MP4 (H.264 + AAC). No lo convertimos."
                : "Cualquier formato — la convertimos a JPEG (lo único que acepta Instagram)."}
            </p>
          )}
          {value && !uploading ? (
            isVideo ? (
              <video
                controls
                src={value}
                className="max-h-40 w-full rounded-md border border-border"
              >
                <track kind="captions" />
              </video>
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={value}
                alt="Vista previa"
                className="max-h-40 rounded-md border border-border object-contain"
              />
            )
          ) : null}
        </>
      ) : null}
    </div>
  );
}
