"use client";

import {
  ExternalLink,
  Pencil,
  Phone,
  Plus,
  RefreshCw,
  Reply,
  Trash2,
  X,
} from "lucide-react";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/errors";
import { useIsAccountAdmin } from "@/lib/api/profile";
import {
  type WhatsappTemplateButton,
  type WhatsappTemplateCategory,
  type WhatsappTemplateComponent,
  type WhatsappTemplateFull,
  useAllWhatsappTemplates,
  useCreateWhatsappTemplate,
  useDeleteWhatsappTemplate,
  useEditWhatsappTemplate,
  useSyncWhatsappTemplates,
} from "@/lib/api/whatsapp-templates";
import { cn } from "@/lib/utils";

const TEMPLATE_NAME_RE = /^[a-z0-9_]{1,512}$/;

export function isValidTemplateName(name: string): boolean {
  return TEMPLATE_NAME_RE.test(name);
}

/** Sorted, distinct `{{n}}` variable numbers found in `text`. */
export function extractTemplateVariables(text: string): number[] {
  const found = new Set<number>();
  for (const m of text.matchAll(/\{\{(\d+)\}\}/g)) {
    const n = Number(m[1]);
    if (Number.isFinite(n) && n > 0) found.add(n);
  }
  return [...found].sort((a, b) => a - b);
}

/** Replace `{{n}}` placeholders with their value (or leave `{{n}}` when blank). */
export function renderTemplateText(
  text: string,
  values: Record<string, string>,
): string {
  return text.replace(/\{\{(\d+)\}\}/g, (full, digits: string) => {
    const val = values[digits]?.trim();
    return val ? val : full;
  });
}

const REJECTED_REASON_LABELS: Record<string, string> = {
  INVALID_FORMAT: "Formato inválido",
  INCORRECT_CATEGORY: "Categoría incorrecta",
  ABUSIVE_CONTENT: "Contenido abusivo",
  PROMOTIONAL: "Contenido promocional no permitido en esta categoría",
  TAG_CONTENT_MISMATCH: "El contenido no coincide con la categoría",
  SCAM: "Posible estafa o engaño",
};

export function translateRejectedReason(
  reason: string | null | undefined,
): string | null {
  if (!reason || reason === "NONE") return null;
  return REJECTED_REASON_LABELS[reason] ?? reason;
}

const STATUS_META: Record<string, { label: string; className: string }> = {
  APPROVED: {
    label: "Aprobada",
    className: "border border-success bg-surface-2 text-success",
  },
  PENDING: {
    label: "Pendiente",
    className: "border border-warning bg-surface-2 text-warning",
  },
  IN_APPEAL: {
    label: "Pendiente",
    className: "border border-warning bg-surface-2 text-warning",
  },
  PENDING_DELETION: {
    label: "Pendiente",
    className: "border border-warning bg-surface-2 text-warning",
  },
  REJECTED: {
    label: "Rechazada",
    className: "border border-danger bg-surface-2 text-danger",
  },
  PAUSED: {
    label: "Pausada",
    className: "border border-warning bg-surface-2 text-warning",
  },
  DISABLED: {
    label: "Desactivada",
    className: "border border-glass bg-surface-2 text-fg-muted",
  },
};

const CATEGORY_OPTIONS: Array<{
  value: WhatsappTemplateCategory;
  label: string;
  description: string;
}> = [
  {
    value: "UTILITY",
    label: "Utilidad",
    description:
      "Confirmaciones, turnos, estado de pedidos o avisos sobre algo que el contacto ya pidió.",
  },
  {
    value: "MARKETING",
    label: "Marketing",
    description:
      "Promociones, ofertas, novedades o invitaciones a conocer un producto o servicio.",
  },
  {
    value: "AUTHENTICATION",
    label: "Autenticación",
    description:
      "Códigos de verificación de un solo uso para iniciar sesión o validar identidad.",
  },
];

const LANGUAGE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "es", label: "Español (es)" },
  { value: "es_AR", label: "Español — Argentina (es_AR)" },
  { value: "es_MX", label: "Español — México (es_MX)" },
  { value: "en_US", label: "Inglés — EE. UU. (en_US)" },
  { value: "pt_BR", label: "Portugués — Brasil (pt_BR)" },
];

function categoryLabel(cat: string | null | undefined): string {
  if (!cat) return "";
  const upper = cat.toUpperCase();
  return CATEGORY_OPTIONS.find((c) => c.value === upper)?.label ?? cat;
}

export type DraftButton = {
  type: "QUICK_REPLY" | "URL" | "PHONE_NUMBER";
  text: string;
  url: string;
  urlExample: string;
  phoneNumber: string;
};

export type TemplateEditorDraft = {
  headerText: string;
  headerExample: string;
  bodyText: string;
  bodyExamples: Record<string, string>;
  footerText: string;
  buttons: DraftButton[];
};

/** Build Meta's `components` array from the editor fields. */
export function buildTemplateComponents(
  draft: TemplateEditorDraft,
): WhatsappTemplateComponent[] {
  const components: WhatsappTemplateComponent[] = [];

  const header = draft.headerText.trim();
  if (header) {
    const headerVars = extractTemplateVariables(header);
    const headerEx = draft.headerExample.trim();
    components.push(
      headerVars.length > 0 && headerEx
        ? {
            type: "HEADER",
            format: "TEXT",
            text: header,
            example: { header_text: [headerEx] },
          }
        : {
            type: "HEADER",
            format: "TEXT",
            text: header,
          },
    );
  }

  const body = draft.bodyText.trim();
  const bodyVars = extractTemplateVariables(body);
  if (bodyVars.length > 0) {
    components.push({
      type: "BODY",
      text: body,
      example: {
        body_text: [
          bodyVars.map((n) => (draft.bodyExamples[String(n)] ?? "").trim()),
        ],
      },
    });
  } else {
    components.push({
      type: "BODY",
      text: body,
    });
  }

  const footer = draft.footerText.trim();
  if (footer) {
    components.push({
      type: "FOOTER",
      text: footer,
    });
  }

  const builtButtons: WhatsappTemplateButton[] = [];
  for (const b of draft.buttons) {
    const text = b.text.trim();
    if (!text) continue;
    if (b.type === "QUICK_REPLY") {
      builtButtons.push({ type: "QUICK_REPLY", text });
    } else if (b.type === "URL") {
      const url = b.url.trim();
      const ex = b.urlExample.trim();
      builtButtons.push(
        url.includes("{{1}}") && ex
          ? { type: "URL", text, url, example: [ex] }
          : { type: "URL", text, url },
      );
    } else if (b.type === "PHONE_NUMBER") {
      builtButtons.push({
        type: "PHONE_NUMBER",
        text,
        phone_number: b.phoneNumber.trim(),
      });
    }
  }
  if (builtButtons.length > 0) {
    components.push({
      type: "BUTTONS",
      buttons: builtButtons,
    });
  }

  return components;
}

function parseTemplateComponents(tpl: WhatsappTemplateFull): TemplateEditorDraft {
  const draft: TemplateEditorDraft = {
    headerText: "",
    headerExample: "",
    bodyText: tpl.body_text ?? "",
    bodyExamples: {},
    footerText: "",
    buttons: [],
  };

  for (const comp of tpl.components ?? []) {
    if (comp.type === "HEADER" && typeof comp.text === "string") {
      draft.headerText = comp.text;
      const ex = comp.example?.header_text?.[0];
      if (typeof ex === "string") draft.headerExample = ex;
    } else if (comp.type === "BODY" && typeof comp.text === "string") {
      draft.bodyText = comp.text;
      const vars = extractTemplateVariables(comp.text);
      const exRow = comp.example?.body_text?.[0] ?? [];
      vars.forEach((n, idx) => {
        if (typeof exRow[idx] === "string") {
          draft.bodyExamples[String(n)] = exRow[idx];
        }
      });
    } else if (comp.type === "FOOTER" && typeof comp.text === "string") {
      draft.footerText = comp.text;
    } else if (comp.type === "BUTTONS" && Array.isArray(comp.buttons)) {
      draft.buttons = comp.buttons.map((b) => {
        if (b.type === "URL") {
          return {
            type: "URL",
            text: b.text ?? "",
            url: b.url ?? "",
            urlExample: Array.isArray(b.example) ? (b.example[0] ?? "") : "",
            phoneNumber: "",
          };
        }
        if (b.type === "PHONE_NUMBER") {
          return {
            type: "PHONE_NUMBER",
            text: b.text ?? "",
            url: "",
            urlExample: "",
            phoneNumber: b.phone_number ?? "",
          };
        }
        return {
          type: "QUICK_REPLY",
          text: b.text ?? "",
          url: "",
          urlExample: "",
          phoneNumber: "",
        };
      });
    }
  }

  return draft;
}

/** How the contact sees the template in WhatsApp: a received bubble with the
 *  buttons attached under it. `framed` puts it in a chat (top bar with the
 *  business name and the wallpaper) for the editor; the composer shows the
 *  bubble alone. Colors are WhatsApp's own, light and dark. */
export function WhatsappTemplatePreview({
  header,
  headerValues,
  body,
  bodyValues,
  footer,
  buttons,
  businessName,
  framed = false,
}: {
  header?: string | null;
  headerValues?: Record<string, string>;
  body: string;
  bodyValues?: Record<string, string>;
  footer?: string | null;
  buttons?: Array<{
    type: string;
    text: string;
    url?: string;
    phone_number?: string;
  }>;
  businessName?: string;
  framed?: boolean;
}) {
  const renderedHeader = header?.trim()
    ? renderTemplateText(header.trim(), headerValues ?? {})
    : null;
  const renderedBody = renderTemplateText(body, bodyValues ?? {});
  const trimmedFooter = footer?.trim() || null;
  const visibleButtons = (buttons ?? []).filter((b) => b.text.trim().length > 0);

  const bubble = (
    <div className="relative w-full max-w-[300px] rounded-lg rounded-tl-none bg-white text-[#111b21] shadow-[0_1px_0.5px_rgba(11,20,26,0.13)] dark:bg-[#202c33] dark:text-[#e9edef]">
      <span
        aria-hidden
        className="absolute -left-2 top-0 h-0 w-0 border-l-[8px] border-t-[8px] border-l-transparent border-t-white dark:border-t-[#202c33]"
      />
      <div className="px-2.5 pb-1.5 pt-2">
        {renderedHeader ? (
          <p className="mb-1 text-[15px] font-bold leading-5">{renderedHeader}</p>
        ) : null}
        <p
          className={cn(
            "whitespace-pre-wrap break-words text-[14px] leading-[19px]",
            !renderedBody && "italic text-[#667781] dark:text-[#8696a0]",
          )}
        >
          {renderedBody || "Escribí el cuerpo de la plantilla…"}
        </p>
        {trimmedFooter ? (
          <p className="mt-1 text-[13px] leading-[17px] text-[#667781] dark:text-[#8696a0]">
            {trimmedFooter}
          </p>
        ) : null}
        <p className="mt-0.5 text-right text-[11px] leading-none text-[#667781] dark:text-[#8696a0]">
          10:24
        </p>
      </div>
      {visibleButtons.map((btn, idx) => (
        <div
          key={idx}
          className="flex items-center justify-center gap-1.5 border-t border-[#e9edef] px-3 py-2 text-[14px] font-medium text-[#027eb5] dark:border-[#2a3942] dark:text-[#53bdeb]"
        >
          {btn.type === "URL" ? (
            <ExternalLink className="h-4 w-4 shrink-0" aria-hidden />
          ) : btn.type === "PHONE_NUMBER" ? (
            <Phone className="h-4 w-4 shrink-0" aria-hidden />
          ) : (
            <Reply className="h-4 w-4 shrink-0" aria-hidden />
          )}
          <span className="truncate">{btn.text}</span>
        </div>
      ))}
    </div>
  );

  if (!framed) {
    return <div data-testid="whatsapp-template-preview">{bubble}</div>;
  }

  const name = businessName?.trim() || "Tu empresa";
  return (
    <div
      data-testid="whatsapp-template-preview"
      className="overflow-hidden rounded-2xl border border-glass shadow-lg"
    >
      <div className="flex items-center gap-2.5 bg-[#008069] px-3 py-2.5 text-white dark:bg-[#202c33] dark:text-[#e9edef]">
        <span
          aria-hidden
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#dfe5e7] text-sm font-semibold text-[#54656f]"
        >
          {name.charAt(0).toUpperCase()}
        </span>
        <div className="min-w-0">
          <p className="truncate text-[15px] font-medium leading-5">{name}</p>
          <p className="text-[12px] leading-4 text-[#d9fdd3] dark:text-[#8696a0]">
            Cuenta de empresa
          </p>
        </div>
      </div>
      <div className="flex min-h-[360px] flex-col items-start bg-[#efeae2] px-4 py-4 dark:bg-[#0b141a]">
        <span className="mb-3 self-center rounded-md bg-white px-2.5 py-1 text-[11px] font-medium uppercase text-[#54656f] shadow-sm dark:bg-[#182229] dark:text-[#8696a0]">
          Hoy
        </span>
        {bubble}
      </div>
    </div>
  );
}

export function WhatsappTemplatesPanel({
  accountId,
  inboxId,
  inboxName,
}: {
  accountId: string;
  inboxId: number;
  /** Shown as the business name in the preview's chat bar. */
  inboxName?: string;
}) {
  const isAdmin = useIsAccountAdmin(accountId);
  const templatesQ = useAllWhatsappTemplates(accountId, inboxId);
  const syncMutation = useSyncWhatsappTemplates(accountId, inboxId);
  const createMutation = useCreateWhatsappTemplate(accountId, inboxId);
  const editMutation = useEditWhatsappTemplate(accountId, inboxId);
  const deleteMutation = useDeleteWhatsappTemplate(accountId, inboxId);

  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<WhatsappTemplateFull | null>(null);
  const [name, setName] = useState("");
  const [category, setCategory] = useState<WhatsappTemplateCategory>("UTILITY");
  const [language, setLanguage] = useState("es");
  const [headerText, setHeaderText] = useState("");
  const [headerExample, setHeaderExample] = useState("");
  const [bodyText, setBodyText] = useState("");
  const [bodyExamples, setBodyExamples] = useState<Record<string, string>>({});
  const [footerText, setFooterText] = useState("");
  const [buttons, setButtons] = useState<DraftButton[]>([]);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [panelError, setPanelError] = useState<string | null>(null);
  const [reviewNotice, setReviewNotice] = useState<string | null>(null);

  const templates = templatesQ.data?.templates ?? [];
  const lastUpdated = templatesQ.data?.last_updated ?? null;

  function openCreate() {
    setEditing(null);
    setName("");
    setCategory("UTILITY");
    setLanguage("es");
    setHeaderText("");
    setHeaderExample("");
    setBodyText("");
    setBodyExamples({});
    setFooterText("");
    setButtons([]);
    setEditorError(null);
    setReviewNotice(null);
    setEditorOpen(true);
  }

  function openEdit(tpl: WhatsappTemplateFull) {
    const parsed = parseTemplateComponents(tpl);
    setEditing(tpl);
    setName(tpl.name);
    setCategory(
      (tpl.category?.toUpperCase() as WhatsappTemplateCategory) || "UTILITY",
    );
    setLanguage(tpl.language || "es");
    setHeaderText(parsed.headerText);
    setHeaderExample(parsed.headerExample);
    setBodyText(parsed.bodyText);
    setBodyExamples(parsed.bodyExamples);
    setFooterText(parsed.footerText);
    setButtons(parsed.buttons);
    setEditorError(null);
    setReviewNotice(null);
    setEditorOpen(true);
  }

  function closeEditor() {
    setEditorOpen(false);
    setEditing(null);
    setEditorError(null);
  }

  function addBodyVariable() {
    const existing = extractTemplateVariables(bodyText);
    const nextNum = existing.length > 0 ? Math.max(...existing) + 1 : 1;
    const spacer =
      bodyText.length > 0 && !/\s$/.test(bodyText) ? " " : "";
    setBodyText(`${bodyText}${spacer}{{${nextNum}}}`);
  }

  const quickReplyCount = buttons.filter((b) => b.type === "QUICK_REPLY").length;
  const actionButtonCount = buttons.filter(
    (b) => b.type === "URL" || b.type === "PHONE_NUMBER",
  ).length;

  function addButton(type: DraftButton["type"]) {
    if (type === "QUICK_REPLY" && quickReplyCount >= 3) return;
    if (type !== "QUICK_REPLY" && actionButtonCount >= 2) return;
    setButtons((prev) => [
      ...prev,
      { type, text: "", url: "", urlExample: "", phoneNumber: "" },
    ]);
  }

  function updateButton(idx: number, patch: Partial<DraftButton>) {
    setButtons((prev) =>
      prev.map((b, i) => (i === idx ? { ...b, ...patch } : b)),
    );
  }

  function removeButton(idx: number) {
    setButtons((prev) => prev.filter((_, i) => i !== idx));
  }

  const nameTouchedInvalid =
    !editing && name.length > 0 && !isValidTemplateName(name);
  const bodyVars = extractTemplateVariables(bodyText);
  const headerVars = extractTemplateVariables(headerText);
  const isSaving = createMutation.isPending || editMutation.isPending;

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setEditorError(null);

    if (!editing) {
      const trimmedName = name.trim();
      if (!trimmedName || !isValidTemplateName(trimmedName)) {
        setEditorError(
          "El nombre va en minúsculas, sin espacios: solo letras, números y guiones bajos (_).",
        );
        return;
      }
    }

    if (!bodyText.trim()) {
      setEditorError("El cuerpo de la plantilla es obligatorio.");
      return;
    }

    if (headerVars.length > 0 && !headerExample.trim()) {
      setEditorError(
        "Completá el ejemplo para la variable del encabezado (Meta lo exige).",
      );
      return;
    }

    const missingBodyExample = bodyVars.some(
      (n) => !(bodyExamples[String(n)] ?? "").trim(),
    );
    if (missingBodyExample) {
      setEditorError(
        "Completá un ejemplo para cada variable del cuerpo (Meta lo exige).",
      );
      return;
    }

    for (const b of buttons) {
      if (!b.text.trim()) {
        setEditorError("Completá el texto de cada botón o quitá los vacíos.");
        return;
      }
      if (b.type === "URL" && !b.url.trim()) {
        setEditorError("Completá la URL del botón.");
        return;
      }
      if (b.type === "URL" && b.url.includes("{{1}}") && !b.urlExample.trim()) {
        setEditorError("Completá el ejemplo para la variable de la URL.");
        return;
      }
      if (b.type === "PHONE_NUMBER" && !b.phoneNumber.trim()) {
        setEditorError("Completá el teléfono del botón.");
        return;
      }
    }

    const components = buildTemplateComponents({
      headerText,
      headerExample,
      bodyText,
      bodyExamples,
      footerText,
      buttons,
    });

    try {
      if (editing && editing.id) {
        await editMutation.mutateAsync({
          id: String(editing.id),
          category,
          components,
        });
      } else {
        await createMutation.mutateAsync({
          name: name.trim(),
          category,
          language,
          components,
        });
      }
      closeEditor();
      setReviewNotice("Meta la revisa; puede tardar de minutos a horas.");
    } catch (err) {
      setEditorError(
        err instanceof ApiError
          ? err.message
          : (err as { message?: string })?.message ??
              "No se pudo guardar la plantilla.",
      );
    }
  }

  async function handleDelete(tpl: WhatsappTemplateFull) {
    if (
      !window.confirm(
        `¿Borrar la plantilla "${tpl.name}"? Se borra también en Meta.`,
      )
    ) {
      return;
    }
    setPanelError(null);
    try {
      await deleteMutation.mutateAsync(String(tpl.id ?? tpl.name));
    } catch (err) {
      setPanelError(
        err instanceof ApiError
          ? err.message
          : (err as { message?: string })?.message ??
              "No se pudo borrar la plantilla.",
      );
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            loading={syncMutation.isPending}
            onClick={() => syncMutation.mutate()}
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden />
            Actualizar desde Meta
          </Button>
          {lastUpdated ? (
            <span className="text-xs text-fg-muted">
              Última actualización:{" "}
              {new Date(lastUpdated * 1000).toLocaleString("es-UY")}
            </span>
          ) : null}
        </div>
        {isAdmin && !editorOpen ? (
          <Button type="button" size="sm" onClick={openCreate}>
            <Plus className="h-4 w-4" aria-hidden />
            Nueva plantilla
          </Button>
        ) : null}
      </div>

      {reviewNotice ? (
        <p
          role="status"
          className="rounded-md border border-glass bg-surface-2 px-3 py-2 text-xs text-fg-muted"
        >
          {reviewNotice}
        </p>
      ) : null}

      {panelError ? (
        <p role="alert" className="text-sm text-danger">
          {panelError}
        </p>
      ) : null}

      {editorOpen && isAdmin ? (
        <div
          role="dialog"
          aria-label={editing ? "Editar plantilla" : "Nueva plantilla"}
          className="rounded-xl border border-glass bg-surface-2 p-5 sm:p-6"
        >
          <div className="mb-5 flex items-center justify-between border-b border-glass pb-3">
            <h3 className="text-sm font-semibold text-fg">
              {editing ? `Editar plantilla: ${editing.name}` : "Nueva plantilla"}
            </h3>
            <button
              type="button"
              aria-label="Cerrar editor"
              onClick={closeEditor}
              className="rounded-md p-1 text-fg-muted hover:bg-hover-glass hover:text-fg"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>

          <form
            onSubmit={(e) => void handleSave(e)}
            className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]"
          >
            <div className="space-y-5">
              {editorError ? (
                <p role="alert" className="text-sm text-danger">
                  {editorError}
                </p>
              ) : null}

              <div className="grid gap-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
                <div className="space-y-1">
                  <Label htmlFor="wa-tpl-name">
                    Nombre
                  </Label>
                  <Input
                    id="wa-tpl-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    disabled={Boolean(editing)}
                    placeholder="recordatorio_turno"
                    aria-invalid={nameTouchedInvalid}
                  />
                  {nameTouchedInvalid ? (
                    <p role="alert" className="text-xs text-danger">
                      Usá solo minúsculas, números y guiones bajos (_), sin
                      espacios.
                    </p>
                  ) : (
                    <p className="text-[11px] text-fg-muted">
                      Solo minúsculas, números y _.
                    </p>
                  )}
                </div>

                <div className="space-y-1">
                  <Label htmlFor="wa-tpl-language">
                    Idioma
                  </Label>
                  <select
                    id="wa-tpl-language"
                    className={selectClassName()}
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    disabled={Boolean(editing)}
                  >
                    {LANGUAGE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <fieldset className="space-y-1.5">
                <legend className="mb-1.5 text-sm font-medium text-fg">
                  Categoría
                </legend>
                <div className="grid gap-2 sm:grid-cols-3">
                  {CATEGORY_OPTIONS.map((opt) => (
                    <label
                      key={opt.value}
                      className={cn(
                        "flex cursor-pointer flex-col gap-1 rounded-lg border px-3 py-2.5 transition-colors",
                        category === opt.value
                          ? "border-neon bg-focused"
                          : "border-glass bg-surface hover:bg-hover-glass",
                      )}
                    >
                      <span className="flex items-center gap-2 text-sm font-medium text-fg">
                        <input
                          type="radio"
                          name="wa-tpl-category"
                          value={opt.value}
                          checked={category === opt.value}
                          onChange={() => setCategory(opt.value)}
                          className="accent-[currentColor]"
                        />
                        {opt.label}
                      </span>
                      <span className="text-xs leading-snug text-fg-muted">
                        {opt.description}
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>

              <div className="space-y-1.5">
                <Label htmlFor="wa-tpl-header">Encabezado (opcional)</Label>
                <Input
                  id="wa-tpl-header"
                  value={headerText}
                  onChange={(e) => setHeaderText(e.target.value)}
                  placeholder="Ej.: Turno {{1}}"
                />
                {headerVars.length > 0 ? (
                  <div className="space-y-1 pt-1">
                    <Label htmlFor="wa-tpl-header-example">
                      Ejemplo de encabezado
                    </Label>
                    <Input
                      id="wa-tpl-header-example"
                      value={headerExample}
                      onChange={(e) => setHeaderExample(e.target.value)}
                      placeholder="Ej.: martes"
                    />
                  </div>
                ) : null}
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <Label htmlFor="wa-tpl-body">
                    Cuerpo
                  </Label>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={addBodyVariable}
                  >
                    <Plus className="h-3.5 w-3.5" aria-hidden />
                    Agregar variable
                  </Button>
                </div>
                <Textarea
                  id="wa-tpl-body"
                  rows={6}
                  value={bodyText}
                  onChange={(e) => setBodyText(e.target.value)}
                  placeholder="Hola {{1}}, te esperamos el {{2}}."
                />
                {bodyVars.length > 0 ? (
                  <div className="space-y-2 rounded-md border border-glass bg-surface p-2.5">
                    <p className="text-xs font-medium text-fg">
                      Ejemplos de variables (Meta los exige para revisar la
                      plantilla)
                    </p>
                    {bodyVars.map((n) => (
                      <div key={n} className="space-y-1">
                        <Label htmlFor={`wa-tpl-var-${n}`}>
                          {`Ejemplo {{${n}}}`}
                        </Label>
                        <Input
                          id={`wa-tpl-var-${n}`}
                          value={bodyExamples[String(n)] ?? ""}
                          onChange={(e) =>
                            setBodyExamples((prev) => ({
                              ...prev,
                              [String(n)]: e.target.value,
                            }))
                          }
                          placeholder={`Valor de ejemplo para {{${n}}}`}
                        />
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="wa-tpl-footer">Pie (opcional)</Label>
                <Input
                  id="wa-tpl-footer"
                  value={footerText}
                  onChange={(e) => setFooterText(e.target.value)}
                  placeholder="Ej.: CTC Salto"
                />
              </div>

              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Label>Botones (opcional)</Label>
                  <div className="flex flex-wrap gap-1.5">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={quickReplyCount >= 3}
                      onClick={() => addButton("QUICK_REPLY")}
                    >
                      + Respuesta rápida
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={actionButtonCount >= 2}
                      onClick={() => addButton("URL")}
                    >
                      + Botón URL
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={actionButtonCount >= 2}
                      onClick={() => addButton("PHONE_NUMBER")}
                    >
                      + Botón teléfono
                    </Button>
                  </div>
                </div>
                <p className="text-[11px] text-fg-muted">
                  Hasta 3 respuestas rápidas, o hasta 2 botones de acción (URL
                  y/o teléfono).
                </p>

                {buttons.map((btn, idx) => (
                  <div
                    key={idx}
                    className="space-y-2 rounded-md border border-glass bg-surface p-2.5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-medium text-fg">
                        {btn.type === "QUICK_REPLY"
                          ? "Respuesta rápida"
                          : btn.type === "URL"
                            ? "Botón URL"
                            : "Botón teléfono"}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeButton(idx)}
                        aria-label={`Quitar botón ${idx + 1}`}
                        className="rounded p-1 text-xs text-fg-muted hover:text-danger"
                      >
                        Quitar
                      </button>
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor={`wa-tpl-btn-text-${idx}`}>
                        Texto del botón
                      </Label>
                      <Input
                        id={`wa-tpl-btn-text-${idx}`}
                        value={btn.text}
                        onChange={(e) =>
                          updateButton(idx, { text: e.target.value })
                        }
                        placeholder="Ej.: Confirmo"
                      />
                    </div>
                    {btn.type === "URL" ? (
                      <div className="space-y-2">
                        <div className="space-y-1">
                          <Label htmlFor={`wa-tpl-btn-url-${idx}`}>
                            URL
                          </Label>
                          <Input
                            id={`wa-tpl-btn-url-${idx}`}
                            value={btn.url}
                            onChange={(e) =>
                              updateButton(idx, { url: e.target.value })
                            }
                            placeholder="https://ctc.edu.uy/{{1}}"
                          />
                        </div>
                        {btn.url.includes("{{1}}") ? (
                          <div className="space-y-1">
                            <Label htmlFor={`wa-tpl-btn-urlex-${idx}`}>
                              Ejemplo de URL
                            </Label>
                            <Input
                              id={`wa-tpl-btn-urlex-${idx}`}
                              value={btn.urlExample}
                              onChange={(e) =>
                                updateButton(idx, {
                                  urlExample: e.target.value,
                                })
                              }
                              placeholder="Ej.: excel"
                            />
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                    {btn.type === "PHONE_NUMBER" ? (
                      <div className="space-y-1">
                        <Label htmlFor={`wa-tpl-btn-phone-${idx}`}>
                          Teléfono
                        </Label>
                        <Input
                          id={`wa-tpl-btn-phone-${idx}`}
                          value={btn.phoneNumber}
                          onChange={(e) =>
                            updateButton(idx, { phoneNumber: e.target.value })
                          }
                          placeholder="+59847300000"
                        />
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>

              <p className="text-xs text-fg-muted">
                Meta la revisa; puede tardar de minutos a horas.
              </p>

              <div className="flex items-center gap-2 pt-1">
                <Button
                  type="submit"
                  size="sm"
                  loading={isSaving}
                  disabled={nameTouchedInvalid}
                >
                  Guardar plantilla
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={closeEditor}
                  disabled={isSaving}
                >
                  Cancelar
                </Button>
              </div>
            </div>

            <div className="space-y-2 lg:sticky lg:top-4 lg:self-start">
              <p className="text-xs font-medium text-fg-muted">
                Vista previa: así lo ve el contacto
              </p>
              <WhatsappTemplatePreview
                framed
                businessName={inboxName}
                header={headerText}
                headerValues={{ "1": headerExample }}
                body={bodyText}
                bodyValues={bodyExamples}
                footer={footerText}
                buttons={buttons.map((b) => ({
                  type: b.type,
                  text: b.text,
                  url: b.url,
                  phone_number: b.phoneNumber,
                }))}
              />
            </div>
          </form>
        </div>
      ) : null}

      {templatesQ.isLoading ? (
        <p className="py-4 text-center text-sm text-fg-muted">
          Cargando plantillas…
        </p>
      ) : templatesQ.isError ? (
        <p role="alert" className="py-4 text-center text-sm text-danger">
          No se pudieron cargar las plantillas.
        </p>
      ) : templates.length === 0 ? (
        <p className="py-4 text-center text-sm text-fg-muted">
          No hay plantillas sincronizadas en esta bandeja.
        </p>
      ) : (
        <ul className="divide-y divide-glass overflow-hidden rounded-md border border-glass bg-surface">
          {templates.map((tpl) => {
            const statusUpper = (tpl.status ?? "").toUpperCase();
            const badge = STATUS_META[statusUpper] ?? {
              label: tpl.status || "Desconocido",
              className: "border border-glass bg-surface-2 text-fg-muted",
            };
            const rejectedReason =
              statusUpper === "REJECTED" || tpl.rejected_reason
                ? translateRejectedReason(tpl.rejected_reason)
                : null;
            return (
              <li
                key={tpl.id ?? `${tpl.name}:${tpl.language}`}
                className="flex flex-wrap items-start justify-between gap-3 px-4 py-3"
              >
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm font-semibold text-fg">
                      {tpl.name}
                    </span>
                    {tpl.language ? (
                      <span className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-fg-muted">
                        {tpl.language}
                      </span>
                    ) : null}
                    {tpl.category ? (
                      <span className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-fg-muted">
                        {categoryLabel(tpl.category)}
                      </span>
                    ) : null}
                    <span
                      className={cn(
                        "rounded-pill px-2 py-0.5 text-xs font-medium",
                        badge.className,
                      )}
                    >
                      {badge.label}
                    </span>
                  </div>
                  {tpl.body_text ? (
                    <p className="line-clamp-2 whitespace-pre-wrap text-xs text-fg-muted">
                      {tpl.body_text}
                    </p>
                  ) : null}
                  {rejectedReason ? (
                    <p className="text-xs text-danger">
                      Motivo de rechazo: {rejectedReason}
                    </p>
                  ) : null}
                </div>

                {isAdmin ? (
                  <div className="flex shrink-0 items-center gap-1.5">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => openEdit(tpl)}
                    >
                      <Pencil className="h-3.5 w-3.5" aria-hidden />
                      Editar
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      loading={deleteMutation.isPending}
                      onClick={() => void handleDelete(tpl)}
                      className="text-danger hover:text-danger"
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden />
                      Borrar
                    </Button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
