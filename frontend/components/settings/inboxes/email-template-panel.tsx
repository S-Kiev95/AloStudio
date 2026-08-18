"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { type InboxDetail, useUpdateInbox } from "@/lib/api/inboxes";

const CONTENT = "{{contenido}}";

const PLACEHOLDERS: { token: string; what: string }[] = [
  { token: CONTENT, what: "el mensaje que escribe el agente (obligatorio)" },
  { token: "{{firma}}", what: "la firma de esta casilla" },
  { token: "{{logo}}", what: "el logo, como imagen" },
];

const EXAMPLE = `<div style="background:#003366;padding:24px;text-align:center">
  {{logo}}
</div>
<div style="padding:24px;font-family:Arial,sans-serif;color:#1f2328">
  {{contenido}}
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
  <div style="font-size:13px;color:#5b6470">{{firma}}</div>
</div>`;

/** The mailbox's own HTML for the whole reply.
 *
 *  The signature and logo customise the footer of a fixed layout; some
 *  institutions need the layout itself. Empty means the built-in one, so
 *  this is something to opt into rather than a step to get through.
 *
 *  What gets substituted in is escaped server-side: the author owns the
 *  markup, the agent's reply is text. */
export function EmailTemplatePanel({
  accountId,
  inbox,
}: {
  accountId: string;
  inbox: InboxDetail;
}) {
  const update = useUpdateInbox(accountId);
  const [html, setHtml] = useState(inbox.template_html ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const missingContent = html.trim().length > 0 && !html.includes(CONTENT);

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    try {
      await update.mutateAsync({
        id: inbox.id,
        patch: { channel: { template_html: html } },
      });
      setSaved(true);
    } catch (err) {
      setError((err as { message?: string })?.message ?? "No se pudo guardar.");
    }
  }

  return (
    <form onSubmit={save} className="space-y-4">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="space-y-1.5">
        <Label htmlFor="template">HTML de la plantilla</Label>
        <Textarea
          id="template"
          rows={12}
          value={html}
          onChange={(e) => {
            setHtml(e.target.value);
            setSaved(false);
          }}
          spellCheck={false}
          className="font-mono text-xs"
          placeholder={EXAMPLE}
        />
        <p className="text-xs text-fg-muted">
          Vacío usa el diseño que trae AloStudio. Los estilos van en el
          atributo <code>style</code> de cada elemento: Gmail y Outlook
          descartan los bloques <code>&lt;style&gt;</code>.
        </p>
      </div>

      <div className="rounded-lg border border-border p-3">
        <p className="mb-2 text-xs font-semibold text-fg">
          Marcadores que podés usar
        </p>
        <ul className="space-y-1">
          {PLACEHOLDERS.map((p) => (
            <li key={p.token} className="flex flex-wrap gap-2 text-xs">
              <code className="rounded bg-surface-2 px-1.5 py-0.5 text-primary">
                {p.token}
              </code>
              <span className="text-fg-muted">{p.what}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Named before saving, because the server refuses it and an error
          after the fact reads as "the save failed" rather than "the
          template would have sent an empty message". */}
      {missingContent ? (
        <p role="alert" className="text-sm text-warning">
          Falta <code>{CONTENT}</code>. Sin eso, cada respuesta saldría sin
          el mensaje.
        </p>
      ) : null}

      <div className="flex items-center gap-3">
        <Button
          type="submit"
          size="sm"
          loading={update.isPending}
          disabled={missingContent}
        >
          Guardar plantilla
        </Button>
        {html.trim() ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              setHtml("");
              setSaved(false);
            }}
          >
            Volver al diseño por defecto
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => setHtml(EXAMPLE)}
          >
            Empezar desde un ejemplo
          </Button>
        )}
        {saved ? (
          <span role="status" className="text-sm text-success">
            Guardada
          </span>
        ) : null}
      </div>
    </form>
  );
}
