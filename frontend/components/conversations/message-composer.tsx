"use client";

import { Lock, Paperclip, Send, Zap, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useCannedResponses } from "@/lib/api/canned-responses";
import { useSendMessage } from "@/lib/api/conversations";
import { uploadAttachment } from "@/lib/api/uploads";
import { cn } from "@/lib/utils";

type PendingAttachment = {
  key: string;
  external_url: string;
  file_type: string;
  name: string;
  // Local object URL for an instant image thumbnail (revoked on remove/send).
  previewUrl?: string;
};

// Matches the backend's NUMBER_OF_PERMITTED_ATTACHMENTS cap.
const MAX_ATTACHMENTS = 15;

export function MessageComposer({
  accountId,
  displayId,
}: {
  accountId: string;
  displayId: number;
}) {
  const [content, setContent] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [attachments, setAttachments] = useState<PendingAttachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const keyRef = useRef(0);
  const send = useSendMessage(accountId, displayId);
  const canned = useCannedResponses(accountId);

  useEffect(() => {
    if (!pickerOpen) return;
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setPickerOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setPickerOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      window.removeEventListener("keydown", onKey);
    };
  }, [pickerOpen]);

  // Canned-response quick-insert: while the whole draft is a single
  // "/token", offer the matching responses (Chatwoot's "/" shortcut).
  const slashMatch = /^\/(\S*)$/.exec(content);
  const slashQuery = slashMatch ? slashMatch[1].toLowerCase() : null;
  const allCanned = canned.data ?? [];
  const slashMatches =
    slashQuery !== null
      ? allCanned
          .filter((c) => c.short_code.toLowerCase().includes(slashQuery))
          .slice(0, 6)
      : [];

  const showListbox =
    (slashQuery !== null && slashMatches.length > 0) || pickerOpen;
  const visibleCanned =
    slashQuery !== null ? slashMatches : allCanned.slice(0, 8);

  function insertCanned(text: string) {
    setContent(text);
    setPickerOpen(false);
    // Refocus so the agent keeps editing right after inserting.
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = [...(e.target.files ?? [])];
    e.target.value = ""; // let the same files be re-picked after removal
    if (picked.length === 0) return;
    const room = MAX_ATTACHMENTS - attachments.length;
    const files = picked.slice(0, Math.max(0, room));
    if (files.length === 0) return;

    setUploadError(false);
    setUploading(true);
    const results = await Promise.allSettled(
      files.map(async (file): Promise<PendingAttachment> => {
        const up = await uploadAttachment(accountId, file);
        const previewUrl = file.type.startsWith("image/")
          ? URL.createObjectURL(file)
          : undefined;
        return {
          ...up,
          name: file.name,
          key: String(keyRef.current++),
          previewUrl,
        };
      }),
    );
    const ok = results
      .filter((r): r is PromiseFulfilledResult<PendingAttachment> => r.status === "fulfilled")
      .map((r) => r.value);
    if (ok.length > 0) setAttachments((prev) => [...prev, ...ok]);
    if (ok.length < files.length) setUploadError(true);
    setUploading(false);
  }

  function removeAttachment(key: string) {
    setAttachments((prev) => {
      const gone = prev.find((a) => a.key === key);
      if (gone?.previewUrl) URL.revokeObjectURL(gone.previewUrl);
      return prev.filter((a) => a.key !== key);
    });
  }

  function submit() {
    const text = content.trim();
    if ((!text && attachments.length === 0) || send.isPending || uploading) {
      return;
    }
    send.mutate(
      {
        content: text || undefined,
        isPrivate,
        attachments: attachments.length
          ? attachments.map((a) => ({
              external_url: a.external_url,
              file_type: a.file_type,
            }))
          : undefined,
      },
      {
        onSuccess: () => {
          setContent("");
          setPickerOpen(false);
          setAttachments((prev) => {
            prev.forEach(
              (a) => a.previewUrl && URL.revokeObjectURL(a.previewUrl),
            );
            return [];
          });
        },
      },
    );
  }

  return (
    <div ref={wrapRef} className="relative border-t border-glass bg-surface p-3">
      {showListbox ? (
        <ul
          role="listbox"
          aria-label="Respuestas predefinidas"
          className="absolute bottom-full left-3 right-3 z-20 mb-1 max-h-56 overflow-auto rounded-md border border-glass bg-surface-2 shadow-menu"
        >
          {visibleCanned.length === 0 ? (
            <li className="px-3 py-2 text-xs text-fg-muted">
              No hay respuestas rápidas configuradas.
            </li>
          ) : (
            visibleCanned.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => insertCanned(c.content)}
                  className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left hover:bg-hover-glass focus-visible:bg-hover-glass focus-visible:outline-none"
                >
                  <code className="text-xs font-semibold text-lit">
                    /{c.short_code}
                  </code>
                  <span className="w-full truncate text-xs text-fg-muted">
                    {c.content}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}

      {attachments.length > 0 ? (
        <div className="mb-2 flex flex-wrap gap-2">
          {attachments.map((att) =>
            att.previewUrl ? (
              <div
                key={att.key}
                className="group relative h-20 w-20 overflow-hidden rounded-md border border-glass"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={att.previewUrl}
                  alt={att.name}
                  className="h-full w-full object-cover"
                />
                <button
                  type="button"
                  onClick={() => removeAttachment(att.key)}
                  aria-label={`Quitar ${att.name}`}
                  className="absolute right-1 top-1 rounded-full bg-backdrop p-0.5 text-white hover:opacity-90"
                >
                  <X className="h-3.5 w-3.5" aria-hidden />
                </button>
              </div>
            ) : (
              <span
                key={att.key}
                className="flex items-center gap-2 rounded-md border border-glass bg-surface-2 px-2 py-1 text-xs"
              >
                <Paperclip
                  className="h-3 w-3 shrink-0 text-fg-muted"
                  aria-hidden
                />
                <span className="max-w-[12rem] truncate text-fg">
                  {att.name}
                </span>
                <button
                  type="button"
                  onClick={() => removeAttachment(att.key)}
                  aria-label={`Quitar ${att.name}`}
                  className="rounded-sm p-0.5 text-fg-muted hover:text-danger"
                >
                  <X className="h-3 w-3" aria-hidden />
                </button>
              </span>
            ),
          )}
        </div>
      ) : null}

      <Textarea
        ref={textareaRef}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            submit();
          }
        }}
        rows={3}
        placeholder={
          isPrivate
            ? "Nota interna (no la ve el cliente)…"
            : "Escribí una respuesta… escribí / para respuestas rápidas"
        }
        aria-label={isPrivate ? "Nota privada" : "Respuesta"}
        className={cn(isPrivate && "border-warning")}
      />

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setIsPrivate((v) => !v)}
          aria-pressed={isPrivate}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-control border px-2.5 py-1.5 text-xs font-medium transition-colors",
            "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
            isPrivate
              ? "border-warning bg-surface-2 text-warning"
              : "border-glass bg-field text-fg-muted hover:bg-hover-glass hover:text-fg",
          )}
        >
          <Lock className="h-3.5 w-3.5" aria-hidden />
          Nota privada
        </button>

        <button
          type="button"
          onClick={() => setPickerOpen((v) => !v)}
          aria-expanded={showListbox}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-control border px-2.5 py-1.5 text-xs font-medium transition-colors",
            "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
            pickerOpen
              ? "border-neon bg-focused text-lit"
              : "border-glass bg-field text-fg-muted hover:bg-hover-glass hover:text-fg",
          )}
        >
          <Zap className="h-3.5 w-3.5" aria-hidden />
          Respuestas rápidas
        </button>

        <input
          ref={fileRef}
          type="file"
          multiple
          onChange={onPickFile}
          className="hidden"
          aria-label="Adjuntar archivos"
          tabIndex={-1}
        />
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => fileRef.current?.click()}
          loading={uploading}
          disabled={
            uploading || send.isPending || attachments.length >= MAX_ATTACHMENTS
          }
          aria-label="Adjuntar archivos"
        >
          <Paperclip className="h-3.5 w-3.5" aria-hidden />
        </Button>

        <Button
          onClick={submit}
          loading={send.isPending}
          disabled={uploading || (!content.trim() && attachments.length === 0)}
          size="sm"
          className="ml-auto"
        >
          <Send className="h-3.5 w-3.5" aria-hidden />
          Enviar
        </Button>
      </div>

      {uploadError ? (
        <p role="alert" className="mt-1 text-xs text-danger">
          No se pudieron subir algunos archivos. Reintentá.
        </p>
      ) : null}
      {send.isError ? (
        <p role="alert" className="mt-1 text-xs text-danger">
          No se pudo enviar. Reintentá.
        </p>
      ) : null}
    </div>
  );
}
