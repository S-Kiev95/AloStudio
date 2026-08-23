"use client";

import { Send } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useTestSendEmailTemplate } from "@/lib/api/email-templates";
import { useInboxes } from "@/lib/api/inboxes";

const EMAIL_CHANNEL = "Channel::Email";

/**
 * Mail the template to a real address.
 *
 * Email breaks where a preview cannot show it: Outlook renders with
 * Word's engine, Gmail clips past ~102 KB, and most clients hide images
 * until the reader allows them. Judging a letterhead from a browser
 * preview is judging it in the one place it will never be read.
 *
 * It goes through a chosen mailbox's own SMTP, so it doubles as a check
 * that the transport carrying the real replies works.
 */
export function TestSendBox({
  accountId,
  templateId,
  disabled = false,
}: {
  accountId: string;
  templateId: number;
  disabled?: boolean;
}) {
  const inboxes = useInboxes(accountId);
  const send = useTestSendEmailTemplate(accountId);
  const [to, setTo] = useState("");
  const [inboxId, setInboxId] = useState<string>("");
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mailboxes = (inboxes.data ?? []).filter(
    (i) => i.channel_type === EMAIL_CHANNEL,
  );
  const chosen = inboxId || (mailboxes[0]?.id ? String(mailboxes[0].id) : "");

  async function onSend() {
    setResult(null);
    setError(null);
    try {
      const res = await send.mutateAsync({
        id: templateId,
        inboxId: Number(chosen),
        to: to.trim(),
      });
      setResult(res.message);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo enviar la prueba.",
      );
    }
  }

  if (mailboxes.length === 0) {
    return (
      <p className="text-xs text-fg-muted">
        Para mandarte una prueba hace falta al menos una casilla de correo
        con envío (SMTP) configurado.
      </p>
    );
  }

  return (
    <div className="space-y-3 rounded-lg border border-border p-3">
      <div>
        <p className="text-sm font-medium">Enviarte una prueba</p>
        <p className="mt-0.5 text-xs text-fg-muted">
          La vista previa de arriba es el navegador. Gmail y Outlook
          renderizan distinto — mandate la plantilla y miratela ahí.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-[10rem] flex-1 space-y-1.5">
          <Label htmlFor="test-inbox">Enviar desde</Label>
          <select
            id="test-inbox"
            value={chosen}
            onChange={(e) => setInboxId(e.target.value)}
            className="h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {mailboxes.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name}
              </option>
            ))}
          </select>
        </div>
        <div className="min-w-[12rem] flex-1 space-y-1.5">
          <Label htmlFor="test-to">Enviar a</Label>
          <Input
            id="test-to"
            type="email"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="vos@ejemplo.com"
          />
        </div>
        <Button
          onClick={onSend}
          loading={send.isPending}
          disabled={disabled || !to.includes("@") || !chosen}
        >
          <Send className="h-4 w-4" aria-hidden />
          Enviar prueba
        </Button>
      </div>

      {result ? (
        <p role="status" className="text-xs text-success">
          {result}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}
      {disabled ? (
        <p className="text-xs text-fg-muted">
          Guardá los cambios antes de mandar la prueba: se envía la
          plantilla guardada, no la que estás editando.
        </p>
      ) : null}
    </div>
  );
}
