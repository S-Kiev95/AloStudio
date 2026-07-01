"use client";

import { Paperclip, Send, X } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useSendMessage } from "@/lib/api/conversations";
import { uploadAttachment } from "@/lib/api/uploads";
import { cn } from "@/lib/utils";

type PendingAttachment = {
  external_url: string;
  file_type: string;
  name: string;
};

export function MessageComposer({
  accountId,
  displayId,
}: {
  accountId: string;
  displayId: number;
}) {
  const [content, setContent] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [attachment, setAttachment] = useState<PendingAttachment | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const send = useSendMessage(accountId, displayId);

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // let the same file be re-picked after removal
    if (!file) return;
    setUploadError(false);
    setUploading(true);
    try {
      const up = await uploadAttachment(accountId, file);
      setAttachment({ ...up, name: file.name });
    } catch {
      setUploadError(true);
    } finally {
      setUploading(false);
    }
  }

  function submit() {
    const text = content.trim();
    if ((!text && !attachment) || send.isPending || uploading) return;
    send.mutate(
      {
        content: text || undefined,
        isPrivate,
        attachments: attachment
          ? [
              {
                external_url: attachment.external_url,
                file_type: attachment.file_type,
              },
            ]
          : undefined,
      },
      {
        onSuccess: () => {
          setContent("");
          setAttachment(null);
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

      {attachment ? (
        <div className="mb-2 flex items-center gap-2 rounded-md border border-border bg-surface-2 px-2 py-1 text-xs">
          <Paperclip className="h-3 w-3 shrink-0 text-fg-muted" aria-hidden />
          <span className="max-w-[16rem] truncate text-fg">
            {attachment.name}
          </span>
          <button
            type="button"
            onClick={() => setAttachment(null)}
            aria-label="Quitar adjunto"
            className="ml-auto rounded p-0.5 text-fg-muted hover:text-danger"
          >
            <X className="h-3 w-3" aria-hidden />
          </button>
        </div>
      ) : null}

      <div className="flex items-end gap-2">
        <input
          ref={fileRef}
          type="file"
          onChange={onPickFile}
          className="hidden"
          aria-label="Adjuntar archivo"
          tabIndex={-1}
        />
        <Button
          type="button"
          variant="secondary"
          size="icon"
          onClick={() => fileRef.current?.click()}
          loading={uploading}
          disabled={uploading || send.isPending}
          aria-label="Adjuntar archivo"
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
          disabled={uploading || (!content.trim() && !attachment)}
          size="icon"
          aria-label="Enviar"
        >
          <Send className="h-4 w-4" aria-hidden />
        </Button>
      </div>

      {uploadError ? (
        <p role="alert" className="mt-1 text-xs text-danger">
          No se pudo subir el archivo. Reintentá.
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
