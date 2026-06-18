"use client";

import { Send } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useSendMessage } from "@/lib/api/conversations";
import { cn } from "@/lib/utils";

export function MessageComposer({
  accountId,
  displayId,
}: {
  accountId: string;
  displayId: number;
}) {
  const [content, setContent] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const send = useSendMessage(accountId, displayId);

  function submit() {
    const text = content.trim();
    if (!text || send.isPending) return;
    send.mutate(
      { content: text, isPrivate },
      { onSuccess: () => setContent("") },
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
      <div className="flex items-end gap-2">
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
          disabled={!content.trim()}
          size="icon"
          aria-label="Enviar"
        >
          <Send className="h-4 w-4" aria-hidden />
        </Button>
      </div>
      {send.isError ? (
        <p role="alert" className="mt-1 text-xs text-danger">
          No se pudo enviar. Reintentá.
        </p>
      ) : null}
    </div>
  );
}
