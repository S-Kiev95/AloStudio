"use client";

import { Lock, MapPin, Paperclip, Pause, Play, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { MESSAGE_TYPE, type Message } from "@/lib/api/conversations";
import { clockTime } from "@/lib/time";
import { cn } from "@/lib/utils";

type Attachment = NonNullable<Message["attachments"]>[number];

/** Inline thumbnail that opens a full-screen lightbox on click. */
function ImageAttachment({ src }: { src: string }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mt-1 block cursor-zoom-in"
        aria-label="Ampliar imagen"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt="Adjunto"
          className="max-h-56 max-w-full rounded-md border border-border object-contain"
        />
      </button>
      {open ? (
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
        >
          <button
            type="button"
            aria-label="Cerrar"
            className="absolute right-4 top-4 rounded-md p-2 text-white/80 hover:bg-white/10 hover:text-white"
          >
            <X className="h-6 w-6" aria-hidden />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={src}
            alt="Adjunto"
            onClick={(e) => e.stopPropagation()}
            className="max-h-full max-w-full rounded object-contain"
          />
        </div>
      ) : null}
    </>
  );
}

function fmtTime(s: number): string {
  if (!Number.isFinite(s) || s < 0) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60)
    .toString()
    .padStart(2, "0");
  return `${m}:${sec}`;
}

/** WhatsApp-style voice/audio player: round play button + seek bar + time. */
function AudioAttachment({ src }: { src: string }) {
  const ref = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [cur, setCur] = useState(0);
  const [dur, setDur] = useState(0);

  function toggle() {
    const a = ref.current;
    if (!a) return;
    if (a.paused) void a.play();
    else a.pause();
  }

  function seek(e: React.MouseEvent<HTMLDivElement>) {
    const a = ref.current;
    if (!a || !dur) return;
    const rect = e.currentTarget.getBoundingClientRect();
    a.currentTime = Math.min(
      Math.max((e.clientX - rect.left) / rect.width, 0),
      1,
    ) * dur;
  }

  const pct = dur ? (cur / dur) * 100 : 0;

  return (
    <div className="mt-1 flex w-56 max-w-full items-center gap-2 rounded-full bg-surface-2 px-2 py-1.5">
      <audio
        ref={ref}
        src={src}
        preload="metadata"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onTimeUpdate={(e) => setCur(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setDur(e.currentTarget.duration)}
      >
        <track kind="captions" />
      </audio>
      <button
        type="button"
        onClick={toggle}
        aria-label={playing ? "Pausar" : "Reproducir"}
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {playing ? (
          <Pause className="h-4 w-4" aria-hidden />
        ) : (
          <Play className="h-4 w-4 translate-x-[1px]" aria-hidden />
        )}
      </button>
      <div
        onClick={seek}
        className="h-1.5 min-w-0 flex-1 cursor-pointer rounded-full bg-border"
      >
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="shrink-0 text-[10px] tabular-nums text-fg-muted">
        {fmtTime(cur > 0 ? cur : dur)}
      </span>
    </div>
  );
}

/** Location bubble: an embedded OpenStreetMap preview + a maps link. */
function LocationAttachment({
  lat,
  lng,
  title,
}: {
  lat: number;
  lng: number;
  title?: string;
}) {
  const d = 0.004;
  const bbox = `${lng - d},${lat - d},${lng + d},${lat + d}`;
  const embed = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lng}`;
  const maps = `https://www.google.com/maps?q=${lat},${lng}`;
  return (
    <div className="mt-1 w-56 max-w-full overflow-hidden rounded-md border border-border">
      <iframe
        src={embed}
        title="Ubicación"
        loading="lazy"
        className="block h-32 w-full border-0"
      />
      <a
        href={maps}
        target="_blank"
        rel="noreferrer"
        className="flex items-center gap-1.5 bg-surface px-2 py-1.5 text-xs font-medium text-primary hover:underline"
      >
        <MapPin className="h-3 w-3 shrink-0" aria-hidden />
        {title || `${lat.toFixed(5)}, ${lng.toFixed(5)}`}
      </a>
    </div>
  );
}

function AttachmentView({ att }: { att: Attachment }) {
  // Location carries coordinates, not a blob — render an embedded map.
  if (att.file_type === "location") {
    const lat = att.coordinates_lat;
    const lng = att.coordinates_long;
    if (lat == null || lng == null) return null;
    return (
      <LocationAttachment lat={lat} lng={lng} title={att.fallback_title} />
    );
  }
  if (!att.data_url) return null;
  if (att.file_type === "image") {
    return <ImageAttachment src={att.data_url} />;
  }
  if (att.file_type === "audio") {
    return <AudioAttachment src={att.data_url} />;
  }
  if (att.file_type === "video") {
    return (
      <video
        controls
        src={att.data_url}
        className="mt-1 max-h-56 max-w-full rounded-md border border-border"
      >
        <track kind="captions" />
      </video>
    );
  }
  return (
    <a
      href={att.data_url}
      target="_blank"
      rel="noreferrer"
      className="mt-1 flex items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-1 text-xs font-medium text-primary hover:underline"
    >
      <Paperclip className="h-3 w-3 shrink-0" aria-hidden />
      Descargar adjunto
    </a>
  );
}

/**
 * One message in the thread. Outgoing = right + primary; incoming = left +
 * surface; activity = centered system note; private notes get a warning
 * tint + a lock. Attachments render inline (image preview or a download link).
 */
export function MessageBubble({ message }: { message: Message }) {
  if (message.message_type === MESSAGE_TYPE.activity) {
    return (
      <div className="my-2 text-center text-xs text-fg-muted">
        {message.content}
      </div>
    );
  }

  const outgoing = message.message_type === MESSAGE_TYPE.outgoing;
  const isPrivate = message.private;

  return (
    <div className={cn("flex", outgoing ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[75%] rounded-lg px-3 py-2 text-sm",
          isPrivate
            ? "border border-warning/40 bg-warning/10 text-fg"
            : outgoing
              ? "bg-surface-2 text-fg"
              : "border border-border bg-surface text-fg",
        )}
      >
        {isPrivate ? (
          <span className="mb-1 flex items-center gap-1 text-xs font-medium text-warning">
            <Lock className="h-3 w-3" aria-hidden /> Nota privada
          </span>
        ) : null}
        {message.content ? (
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        ) : null}
        {message.attachments?.map((att) => (
          <AttachmentView key={att.id} att={att} />
        ))}
        <span className="mt-1 block text-right text-[10px] tabular-nums text-fg-muted">
          {clockTime(message.created_at)}
        </span>
      </div>
    </div>
  );
}
