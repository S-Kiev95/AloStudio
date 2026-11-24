"use client";

import { Monitor, Moon, Smartphone, Sun } from "lucide-react";
import { useMemo, useState } from "react";

import type { CanvasKind } from "@/lib/inboxes/email-blocks";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

export type SampleProfile = {
  name?: string;
  jobTitle?: string;
  email?: string;
  phone?: string;
  avatarUrl?: string;
  logoUrl?: string;
  signatureHtml?: string;
  orgSignatureHtml?: string;
};

function esc(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function safeUrl(raw: string): string {
  const url = (raw || "").trim();
  return /^(https?:\/\/|\/public\/|data:image\/(?:png|jpe?g|gif|webp);base64,)/i.test(url)
    ? esc(url)
    : "";
}

/** Fill template and signature placeholders with sample (or profile) data. */
export function fillPreviewPlaceholders(
  rawHtml: string,
  kind: CanvasKind,
  sample: SampleProfile = {},
): string {
  const name = sample.name?.trim() || "Ana Pérez";
  const jobTitle = sample.jobTitle?.trim() || "Atención al cliente";
  const email = sample.email?.trim() || "ana@ejemplo.com";
  const phone = sample.phone?.trim() || "+598 99 123 456";
  const avatar = safeUrl(sample.avatarUrl ?? "");
  const logo = safeUrl(sample.logoUrl ?? "");

  const photoTag = avatar
    ? `<img src="${avatar}" alt="${esc(name)}" width="48" height="48" style="width:48px;height:48px;border-radius:50%;object-fit:cover;display:block;border:0" />`
    : `<span style="display:inline-block;width:48px;height:48px;border-radius:50%;background:#003366;color:#ffffff;font-weight:bold;font-size:18px;line-height:48px;text-align:center">${esc(
        name.slice(0, 1).toUpperCase(),
      )}</span>`;

  const logoTag = logo
    ? `<img src="${logo}" alt="" style="max-width:160px;max-height:56px;display:block" />`
    : `<span style="display:inline-block;padding:6px 14px;border-radius:4px;background:#e5e7eb;color:#1f2328;font-weight:bold;font-size:13px">LOGO</span>`;

  const sampleBody =
    `<p style="margin:0 0 12px">Hola, gracias por escribirnos.</p>` +
    `<p style="margin:0 0 12px">Así se ve el mensaje que escribe quien responde desde la bandeja de correo.</p>`;

  const defaultUserSig =
    `<strong>${esc(name)}</strong><br><span style="color:#5b6470">${esc(
      jobTitle,
    )} · ${esc(email)}</span>`;
  const defaultOrgSig = `<strong>Organización Ejemplo</strong><br>contacto@ejemplo.com`;

  const userSig = sample.signatureHtml?.trim() || defaultUserSig;
  const orgSig = sample.orgSignatureHtml?.trim() || defaultOrgSig;

  let out = rawHtml
    .replace(/\{\{nombre\}\}/g, esc(name))
    .replace(/\{\{cargo\}\}/g, esc(jobTitle))
    .replace(/\{\{correo\}\}/g, esc(email))
    .replace(/\{\{telefono\}\}/g, esc(phone))
    .replace(/\{\{foto\}\}/g, photoTag)
    .replace(/\{\{foto_url\}\}/g, avatar);

  if (kind === "template") {
    out = out
      .replace(/\{\{contenido\}\}/g, sampleBody)
      .replace(/\{\{logo\}\}/g, logoTag)
      .replace(/\{\{firma\}\}/g, userSig || orgSig)
      .replace(/\{\{firma_organizacion\}\}/g, orgSig)
      .replace(/\{\{firma_agente\}\}/g, userSig);
  }
  return out;
}

/**
 * Sandboxed email preview.
 *
 * Always renders inside ``<iframe sandbox="" srcDoc={...} />`` — never
 * ``dangerouslySetInnerHTML`` — so untrusted HTML pasted by a user or
 * returned by AI can never execute scripts or access the dashboard DOM.
 */
export function EmailPreviewFrame({
  html,
  kind = "template",
  sample,
  height = 460,
  title,
  compact = false,
}: {
  html: string;
  kind?: CanvasKind;
  sample?: SampleProfile;
  height?: number;
  title?: string;
  compact?: boolean;
}) {
  const t = useT();
  const [viewport, setViewport] = useState<"desktop" | "mobile">("desktop");
  const [scheme, setScheme] = useState<"light" | "dark">("light");

  const srcDoc = useMemo(() => {
    const filled = fillPreviewPlaceholders(html, kind, sample);
    // Mail-client dark mode simulation: dark canvas + subtle inversion when
    // the author left bright white backgrounds, keeping images un-inverted.
    const darkStyle =
      scheme === "dark"
        ? "body{background:#111827 !important;color:#f3f4f6 !important;filter:invert(0.9) hue-rotate(180deg);}img{filter:invert(1) hue-rotate(180deg);}"
        : "body{background:#ffffff;color:#1f2328;}";
    return (
      `<!doctype html><html><head><meta charset="utf-8" />` +
      `<meta name="viewport" content="width=device-width,initial-scale=1" />` +
      `<style>html,body{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}${darkStyle}</style>` +
      `</head><body><div style="padding:${kind === "signature" ? "16px" : "0"}">${filled}</div></body></html>`
    );
  }, [html, kind, sample, scheme]);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-medium text-fg-muted">
          {title ?? t("settingsEmailTpl.preview")}
        </span>
        <div className="flex items-center gap-1.5">
          {!compact ? (
            <div
              role="group"
              aria-label={t("settingsEmailTpl.previewViewport")}
              className="inline-flex rounded-md border border-glass bg-field p-0.5"
            >
              <button
                type="button"
                aria-pressed={viewport === "desktop"}
                onClick={() => setViewport("desktop")}
                className={cn(
                  "inline-flex items-center gap-1 rounded-sm px-2 py-1 text-xs font-medium transition-colors",
                  viewport === "desktop"
                    ? "bg-focused text-lit"
                    : "text-fg-muted hover:bg-hover-glass hover:text-fg",
                )}
              >
                <Monitor className="h-3.5 w-3.5" aria-hidden />
                {t("settingsEmailTpl.desktop")}
              </button>
              <button
                type="button"
                aria-pressed={viewport === "mobile"}
                onClick={() => setViewport("mobile")}
                className={cn(
                  "inline-flex items-center gap-1 rounded-sm px-2 py-1 text-xs font-medium transition-colors",
                  viewport === "mobile"
                    ? "bg-focused text-lit"
                    : "text-fg-muted hover:bg-hover-glass hover:text-fg",
                )}
              >
                <Smartphone className="h-3.5 w-3.5" aria-hidden />
                {t("settingsEmailTpl.mobile")}
              </button>
            </div>
          ) : null}

          <div
            role="group"
            aria-label={t("settingsEmailTpl.previewTheme")}
            className="inline-flex rounded-md border border-glass bg-field p-0.5"
          >
            <button
              type="button"
              aria-pressed={scheme === "light"}
              onClick={() => setScheme("light")}
              className={cn(
                "inline-flex items-center gap-1 rounded-sm px-2 py-1 text-xs font-medium transition-colors",
                scheme === "light"
                  ? "bg-focused text-lit"
                  : "text-fg-muted hover:bg-hover-glass hover:text-fg",
              )}
            >
              <Sun className="h-3.5 w-3.5" aria-hidden />
              {t("theme.light")}
            </button>
            <button
              type="button"
              aria-pressed={scheme === "dark"}
              onClick={() => setScheme("dark")}
              className={cn(
                "inline-flex items-center gap-1 rounded-sm px-2 py-1 text-xs font-medium transition-colors",
                scheme === "dark"
                  ? "bg-focused text-lit"
                  : "text-fg-muted hover:bg-hover-glass hover:text-fg",
              )}
            >
              <Moon className="h-3.5 w-3.5" aria-hidden />
              {t("theme.dark")}
            </button>
          </div>
        </div>
      </div>

      <div className="flex justify-center overflow-auto rounded-md border border-glass bg-surface-2 p-2">
        <iframe
          title={title ?? t("settingsEmailTpl.preview")}
          sandbox=""
          srcDoc={srcDoc}
          style={{
            width: viewport === "mobile" ? "375px" : "100%",
            height: `${height}px`,
          }}
          className="rounded-sm border border-glass bg-white transition-[width] duration-200"
        />
      </div>

      <p className="text-xs text-fg-muted">{t("settingsEmailTpl.previewNote")}</p>
    </div>
  );
}
