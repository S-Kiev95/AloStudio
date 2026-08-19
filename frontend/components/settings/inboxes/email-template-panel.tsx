"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { type InboxDetail, useUpdateInbox } from "@/lib/api/inboxes";
import {
  DEFAULT_DESIGN,
  type TemplateDesign,
  renderDesign,
} from "@/lib/inboxes/email-template-design";
import { cn } from "@/lib/utils";

import { EmailDesigner } from "./email-designer";

const CONTENT = "{{contenido}}";

const PLACEHOLDERS: { token: string; what: string }[] = [
  { token: CONTENT, what: "el mensaje que escribe el agente (obligatorio)" },
  { token: "{{firma}}", what: "la firma de esta casilla" },
  {
    token: "{{firma_agente}}",
    what: "la firma de quien responde, de su perfil",
  },
  { token: "{{logo}}", what: "el logo, como imagen" },
];

const EXAMPLE = `<div style="background:#003366;padding:24px;text-align:center">
  {{logo}}
</div>
<div style="padding:24px;font-family:Arial,sans-serif;color:#1f2328">
  {{contenido}}
  <div style="margin-top:16px;font-size:14px">{{firma_agente}}</div>
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
  const [design, setDesign] = useState<TemplateDesign>({
    ...DEFAULT_DESIGN,
    ...((inbox.template_design ?? {}) as Partial<TemplateDesign>),
  });
  // Hand-written HTML has no design behind it, so opening on the designer
  // would show controls that do not describe it — and saving would
  // silently replace it.
  const [mode, setMode] = useState<"design" | "code">(
    inbox.template_html && !inbox.template_design ? "code" : "design",
  );
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
        patch: {
          channel:
            mode === "design"
              ? {
                  template_html: renderDesign(design),
                  template_design: design,
                }
              : // No design goes with hand-written HTML; the server reads
                // its absence as "this was edited by hand" and forgets the
                // one it had.
                { template_html: html },
        },
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

      <div className="flex gap-1 rounded-lg border border-border p-1">
        {(
          [
            ["design", "Diseñador"],
            ["code", "HTML"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={mode === value}
            onClick={() => {
              // Moving to code carries the design across, so the author
              // starts from what they built rather than a blank box.
              if (value === "code" && mode === "design") {
                setHtml(renderDesign(design));
              }
              setMode(value);
              setSaved(false);
            }}
            className={cn(
              "flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              mode === value
                ? "bg-primary text-primary-fg"
                : "text-fg-muted hover:bg-surface-2",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === "design" ? (
        <EmailDesigner
          design={design}
          onChange={(d) => {
            setDesign(d);
            setSaved(false);
          }}
          logoUrl={inbox.logo_url ?? ""}
          signature={inbox.signature ?? ""}
        />
      ) : (
      <>
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
      </>
      )}

      <div className="flex items-center gap-3">
        <Button
          type="submit"
          size="sm"
          loading={update.isPending}
          disabled={mode === "code" && missingContent}
        >
          Guardar plantilla
        </Button>
        {mode === "code" && html.trim() ? (
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
        ) : mode === "code" ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => setHtml(EXAMPLE)}
          >
            Empezar desde un ejemplo
          </Button>
        ) : null}
        {saved ? (
          <span role="status" className="text-sm text-success">
            Guardada
          </span>
        ) : null}
      </div>
    </form>
  );
}
