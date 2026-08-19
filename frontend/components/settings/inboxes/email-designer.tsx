"use client";

import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  type TemplateDesign,
  renderDesign,
} from "@/lib/inboxes/email-template-design";

/** The controls a non-technical author gets instead of HTML.
 *
 *  Deliberately few. Every extra knob is another way to produce something
 *  that renders badly in Outlook, and the whole point is that whoever uses
 *  this cannot check that themselves. */
export function EmailDesigner({
  design,
  onChange,
  logoUrl,
  signature,
}: {
  design: TemplateDesign;
  onChange: (d: TemplateDesign) => void;
  logoUrl: string;
  signature: string;
}) {
  function set<K extends keyof TemplateDesign>(
    key: K,
    value: TemplateDesign[K],
  ) {
    onChange({ ...design, [key]: value });
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="d-title">Título del encabezado</Label>
          <Input
            id="d-title"
            value={design.headerTitle}
            onChange={(e) => set("headerTitle", e.target.value)}
            placeholder="Instituto Ejemplo"
          />
          <p className="text-xs text-fg-muted">
            Vacío y sin logo, el correo sale sin encabezado.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Swatch
            id="d-header"
            label="Color del encabezado"
            value={design.headerColor}
            onChange={(v) => set("headerColor", v)}
          />
          <Swatch
            id="d-headertext"
            label="Texto del encabezado"
            value={design.headerTextColor}
            onChange={(v) => set("headerTextColor", v)}
          />
          <Swatch
            id="d-page"
            label="Fondo del correo"
            value={design.pageColor}
            onChange={(v) => set("pageColor", v)}
          />
          <Swatch
            id="d-body"
            label="Fondo del texto"
            value={design.bodyColor}
            onChange={(v) => set("bodyColor", v)}
          />
        </div>

        <Toggle
          label="Mostrar el logo"
          checked={design.showLogo}
          onChange={(v) => set("showLogo", v)}
          hint={
            logoUrl
              ? undefined
              : "Todavía no cargaste un logo en Firma y logo."
          }
        />
        <Toggle
          label="Mostrar la firma del agente"
          checked={design.showAgentSignature}
          onChange={(v) => set("showAgentSignature", v)}
          hint="La que cada persona configura en Mi perfil."
        />
        <Toggle
          label="Mostrar la firma de la casilla"
          checked={design.showSignature}
          onChange={(v) => set("showSignature", v)}
          hint={
            signature.trim()
              ? undefined
              : "Todavía no cargaste una firma en Firma y logo."
          }
        />

        <div className="space-y-1.5">
          <Label htmlFor="d-note">Nota al pie</Label>
          <Input
            id="d-note"
            value={design.footerNote}
            onChange={(e) => set("footerNote", e.target.value)}
            placeholder="Este correo se envió desde nuestro sistema de soporte."
          />
        </div>
      </div>

      <DesignPreview design={design} logoUrl={logoUrl} signature={signature} />
    </div>
  );
}

function Swatch({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="flex items-center gap-2">
        <input
          id={id}
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="h-9 w-12 cursor-pointer rounded border border-border bg-surface"
        />
        <span className="font-mono text-xs text-fg-muted">{value}</span>
      </div>
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
  hint,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  hint?: string;
}) {
  return (
    <div>
      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="h-4 w-4 rounded border-border"
        />
        {label}
      </label>
      {hint ? <p className="mt-1 text-xs text-warning">{hint}</p> : null}
    </div>
  );
}

/** The design filled with real placeholder values.
 *
 *  Rendered from the same generator the save uses, so what is on screen is
 *  the email — not an approximation of it drawn with app styles. */
function DesignPreview({
  design,
  logoUrl,
  signature,
}: {
  design: TemplateDesign;
  logoUrl: string;
  signature: string;
}) {
  const html = renderDesign(design)
    .replace(
      "{{firma_agente}}",
      "<i>la firma de quien responda va acá</i>",
    )
    .replace(
      "{{contenido}}",
      "<p style=\"margin:0 0 12px\">Gracias por escribirnos, te confirmo enseguida.</p>",
    )
    .replace(
      "{{logo}}",
      logoUrl
        ? `<img src="${logoUrl}" alt="" style="max-width:160px;max-height:56px">`
        : "",
    )
    .replace(
      "{{firma}}",
      signature.trim()
        ? signature.replace(/\n/g, "<br>")
        : "<i>tu firma va acá</i>",
    );

  return (
    <div className="space-y-1.5">
      <Label>Cómo se ve</Label>
      <div
        className="overflow-hidden rounded-lg border border-border"
        // The generated markup, not app markup: this is the only place the
        // author can see what a recipient will get.
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
