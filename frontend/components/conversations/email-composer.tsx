"use client";

import { Loader2, Send } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useSendMessage } from "@/lib/api/conversations";

/** Replying to an email, not sending a chat line.
 *
 *  The differences that matter: a reply can copy other people, it is
 *  written in paragraphs rather than one line, and Enter has to insert a
 *  newline instead of sending — the chat composer's muscle memory would
 *  fire off half a paragraph to a customer. */
export function EmailComposer({
  accountId,
  displayId,
  replyTo,
}: {
  accountId: string;
  displayId: number;
  replyTo?: string | null;
}) {
  const send = useSendMessage(accountId, displayId);
  const [content, setContent] = useState("");
  const [cc, setCc] = useState("");
  const [bcc, setBcc] = useState("");
  const [showCopies, setShowCopies] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!content.trim()) return;
    setError(null);
    try {
      await send.mutateAsync({
        content: content.trim(),
        ccEmails: cc.trim(),
        bccEmails: bcc.trim(),
      });
      setContent("");
      setCc("");
      setBcc("");
      setShowCopies(false);
    } catch (err) {
      setError((err as { message?: string })?.message ?? "No se pudo enviar.");
    }
  }

  return (
    <form
      onSubmit={submit}
      className="space-y-2 rounded-xl border border-border bg-surface p-3"
    >
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2 text-xs text-fg-muted">
        <span>
          Para: <span className="text-fg">{replyTo ?? "el contacto"}</span>
        </span>
        {!showCopies ? (
          <button
            type="button"
            onClick={() => setShowCopies(true)}
            className="rounded px-1.5 py-0.5 text-primary hover:bg-surface-2"
          >
            CC / CCO
          </button>
        ) : null}
      </div>

      {showCopies ? (
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="cc">CC</Label>
            <Input
              id="cc"
              value={cc}
              onChange={(e) => setCc(e.target.value)}
              placeholder="otra@persona.com, tercera@persona.com"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="bcc">CCO</Label>
            <Input
              id="bcc"
              value={bcc}
              onChange={(e) => setBcc(e.target.value)}
              placeholder="copia@oculta.com"
            />
          </div>
        </div>
      ) : null}

      <Textarea
        aria-label="Tu respuesta"
        rows={5}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Escribí tu respuesta…"
      />

      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-fg-muted">
          Se envía con la firma y el diseño de la casilla.
        </p>
        <Button type="submit" size="sm" disabled={!content.trim() || send.isPending}>
          {send.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <Send className="h-4 w-4" aria-hidden />
          )}
          Enviar
        </Button>
      </div>
    </form>
  );
}
