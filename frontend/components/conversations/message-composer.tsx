"use client";

import { Paperclip, Send, X } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useSendMessage } from "@/lib/api/conversations";
import { uploadAttachment } from "@/lib/api/uploads";
import { cn } from "@/lib/utils";

type PendingAttachment = {
  key: string;
  external_url: string;
  file_type: string;
  name: string;
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
  const keyRef = useRef(0);
  const send = useSendMessage(accountId, displayId);

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
      files.map(async (file) => {
        const up = await uploadAttachment(accountId, file);
        return { ...up, name: file.name, key: String(keyRef.current++) };
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
    setAttachments((prev) => prev.filter((a) => a.key !== key));
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
          setAttachments([]);
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
          {attachments.map((att) => (
            <span
              key={att.key}
              className="flex items-center gap-2 rounded-md border border-border bg-surface-2 px-2 py-1 text-xs"
            >
              <Paperclip className="h-3 w-3 shrink-0 text-fg-muted" aria-hidden />
              <span className="max-w-[12rem] truncate text-fg">{att.name}</span>
              <button
                type="button"
                onClick={() => removeAttachment(att.key)}
                aria-label={`Quitar ${att.name}`}
                className="rounded p-0.5 text-fg-muted hover:text-danger"
              >
                <X className="h-3 w-3" aria-hidden />
              </button>
            </span>
          ))}
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
        <Textarea
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
