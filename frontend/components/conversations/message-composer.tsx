"use client";

import { Paperclip, Send, X } from "lucide-react";
import { useRef, useState } from "react";

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
  const [attachments, setAttachments] = useState<PendingAttachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const keyRef = useRef(0);
  const send = useSendMessage(accountId, displayId);
  const canned = useCannedResponses(accountId);

  // Canned-response quick-insert: while the whole draft is a single
  // "/token", offer the matching responses (Chatwoot's "/" shortcut).
  const slashMatch = /^\/(\S*)$/.exec(content);
  const slashQuery = slashMatch ? slashMatch[1].toLowerCase() : null;
  const cannedMatches =
    slashQuery !== null
      ? (canned.data ?? [])
          .filter((c) => c.short_code.toLowerCase().includes(slashQuery))
          .slice(0, 6)
      : [];

  function insertCanned(text: string) {
    setContent(text);
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
    <div className="border-t border-border bg-surface p-3">
      <div className="mb-2 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setIsPrivate(false)}
          aria-pressed={!isPrivate}
          className={cn(
            "rounded-md px-2 py-1 text-xs font-medium",
            !isPrivate ? "bg-surface-2 font-semibold text-fg" : "text-fg-muted hover:bg-surface-2",
          )}
        >
          Responder
        </button>
        <button
          type="button"
          onClick={() => setIsPrivate(true)}
          aria-pressed={isPrivate}
          className={cn(
            "rounded-md px-2 py-1 text-xs font-medium",
            isPrivate ? "bg-warning/15 font-semibold text-warning" : "text-fg-muted hover:bg-surface-2",
          )}
        >
          Nota privada
        </button>
      </div>

      {attachments.length > 0 ? (
        <div className="mb-2 flex flex-wrap gap-2">
          {attachments.map((att) =>
            att.previewUrl ? (
              <div
                key={att.key}
                className="group relative h-20 w-20 overflow-hidden rounded-md border border-border"
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
                  className="absolute right-1 top-1 rounded-full bg-black/60 p-0.5 text-white hover:bg-black/80"
                >
                  <X className="h-3.5 w-3.5" aria-hidden />
                </button>
              </div>
            ) : (
              <span
                key={att.key}
                className="flex items-center gap-2 rounded-md border border-border bg-surface-2 px-2 py-1 text-xs"
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
                  className="rounded p-0.5 text-fg-muted hover:text-danger"
                >
                  <X className="h-3 w-3" aria-hidden />
                </button>
              </span>
            ),
          )}
        </div>
      ) : null}

      <div className="flex items-end gap-2">
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
          size="icon"
          onClick={() => fileRef.current?.click()}
          loading={uploading}
          disabled={uploading || send.isPending || attachments.length >= MAX_ATTACHMENTS}
          aria-label="Adjuntar archivos"
        >
          <Paperclip className="h-4 w-4" aria-hidden />
        </Button>
        <div className="relative flex-1">
          {cannedMatches.length > 0 ? (
            <ul
              role="listbox"
              aria-label="Respuestas predefinidas"
              className="absolute bottom-full left-0 z-10 mb-1 max-h-56 w-full overflow-auto rounded-md border border-border bg-surface shadow-lg"
            >
              {cannedMatches.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => insertCanned(c.content)}
                    className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left hover:bg-surface-2 focus-visible:bg-surface-2 focus-visible:outline-none"
                  >
                    <code className="text-xs font-semibold text-primary">
                      /{c.short_code}
                    </code>
                    <span className="w-full truncate text-xs text-fg-muted">
                      {c.content}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
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
            rows={2}
            placeholder={
              isPrivate ? "Nota interna (no la ve el cliente)…" : "Escribí una respuesta…"
            }
            aria-label={isPrivate ? "Nota privada" : "Respuesta"}
          />
        </div>
        <Button
          onClick={submit}
          loading={send.isPending}
          disabled={uploading || (!content.trim() && attachments.length === 0)}
          size="icon"
          aria-label="Enviar"
        >
          <Send className="h-4 w-4" aria-hidden />
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
