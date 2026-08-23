"use client";

import { Mail, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";

import { EmailDesigner } from "@/components/settings/inboxes/email-designer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type EmailTemplate,
  useCreateEmailTemplate,
  useDeleteEmailTemplate,
  useEmailTemplates,
  useUpdateEmailTemplate,
} from "@/lib/api/email-templates";
import {
  DEFAULT_DESIGN,
  type TemplateDesign,
  renderDesign,
} from "@/lib/inboxes/email-template-design";
import { cn } from "@/lib/utils";

import { TestSendBox } from "./test-send-box";

const CONTENT = "{{contenido}}";

export function EmailTemplatesView({ accountId }: { accountId: string }) {
  const templates = useEmailTemplates(accountId);
  const create = useCreateEmailTemplate(accountId);
  const [selected, setSelected] = useState<number | null>(null);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const list = templates.data ?? [];
  const current = list.find((t) => t.id === selected) ?? null;

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const created = await create.mutateAsync({
        name: newName.trim(),
        // Starts from the built-in design rather than a blank page, so a
        // new template is already sendable.
        template_html: renderDesign(DEFAULT_DESIGN),
      });
      setNewName("");
      setSelected(created.id);
    } catch (err) {
      setError((err as { message?: string })?.message ?? "No se pudo crear.");
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold">Plantillas de correo</h1>
        <p className="text-sm text-fg-muted">
          El diseño con el que salen los correos. Una organización puede
          tener varias — bienvenida, cierre de ticket, avisos — y cada
          casilla elige cuál usa.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Tus plantillas</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {templates.isLoading ? (
            <p className="text-sm text-fg-muted">Cargando…</p>
          ) : list.length === 0 ? (
            <p className="text-sm text-fg-muted">
              Todavía no hay ninguna. Las casillas siguen usando el diseño
              que traen por defecto.
            </p>
          ) : (
            <ul className="space-y-2">
              {list.map((t) => (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(t.id === selected ? null : t.id)}
                    aria-pressed={t.id === selected}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors",
                      t.id === selected
                        ? "border-primary bg-primary/5"
                        : "border-border hover:bg-surface-2",
                    )}
                  >
                    <Mail className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
                    <span className="font-medium">{t.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          <form onSubmit={onCreate} className="flex flex-wrap items-end gap-2">
            <div className="min-w-[12rem] flex-1 space-y-1.5">
              <Label htmlFor="new-template">Nueva plantilla</Label>
              <Input
                id="new-template"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Bienvenida"
              />
            </div>
            <Button
              type="submit"
              loading={create.isPending}
              disabled={newName.trim() === ""}
            >
              <Plus className="h-4 w-4" aria-hidden />
              Crear
            </Button>
          </form>
          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {current ? (
        <TemplateEditor
          key={current.id}
          accountId={accountId}
          template={current}
          onDeleted={() => setSelected(null)}
        />
      ) : null}
    </div>
  );
}

function TemplateEditor({
  accountId,
  template,
  onDeleted,
}: {
  accountId: string;
  template: EmailTemplate;
  onDeleted: () => void;
}) {
  const update = useUpdateEmailTemplate(accountId);
  const remove = useDeleteEmailTemplate(accountId);

  const [name, setName] = useState(template.name);
  const [html, setHtml] = useState(template.template_html);
  const [design, setDesign] = useState<TemplateDesign>({
    ...DEFAULT_DESIGN,
    ...((template.template_design ?? {}) as Partial<TemplateDesign>),
  });
  // Hand-written HTML has no design behind it, so opening on the designer
  // would show controls that do not describe it — and saving would
  // silently replace it.
  const [mode, setMode] = useState<"design" | "code">(
    template.template_html && !template.template_design ? "code" : "design",
  );
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const missingContent = html.trim().length > 0 && !html.includes(CONTENT);

  function touched() {
    setDirty(true);
    setSaved(false);
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    try {
      await update.mutateAsync({
        id: template.id,
        patch: {
          name: name.trim(),
          ...(mode === "design"
            ? { template_html: renderDesign(design), template_design: design }
            : // No design goes with hand-written HTML; the server reads
              // its absence as "edited by hand".
              { template_html: html, template_design: null }),
        },
      });
      setSaved(true);
      setDirty(false);
    } catch (err) {
      setError((err as { message?: string })?.message ?? "No se pudo guardar.");
    }
  }

  async function onDelete() {
    if (
      !window.confirm(
        `¿Eliminar la plantilla «${template.name}»? Las casillas que la usen vuelven a su propio diseño.`,
      )
    ) {
      return;
    }
    setError(null);
    try {
      await remove.mutateAsync(template.id);
      onDeleted();
    } catch (err) {
      setError((err as { message?: string })?.message ?? "No se pudo eliminar.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Editar «{template.name}»</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={save} className="space-y-4">
          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          ) : null}

          <div className="space-y-1.5">
            <Label htmlFor="tpl-name" required>
              Nombre
            </Label>
            <Input
              id="tpl-name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                touched();
              }}
            />
          </div>

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
                  // Moving to code carries the design across, so the
                  // author starts from what they built.
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
                touched();
              }}
              logoUrl=""
              signature=""
            />
          ) : (
            <div className="space-y-1.5">
              <Label htmlFor="tpl-html">HTML de la plantilla</Label>
              <Textarea
                id="tpl-html"
                rows={14}
                value={html}
                onChange={(e) => {
                  setHtml(e.target.value);
                  touched();
                }}
                spellCheck={false}
                className="font-mono text-xs"
              />
              {missingContent ? (
                <p role="alert" className="text-xs text-danger">
                  Falta {CONTENT}. Sin ese marcador el mensaje del agente no
                  se incluye y el correo sale vacío.
                </p>
              ) : (
                <p className="text-xs text-fg-muted">
                  Los estilos van en el atributo <code>style</code> de cada
                  elemento: Gmail y Outlook descartan los bloques{" "}
                  <code>&lt;style&gt;</code>.
                </p>
              )}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" loading={update.isPending}>
              Guardar
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={onDelete}
              loading={remove.isPending}
              className="text-danger hover:bg-danger/10"
            >
              <Trash2 className="h-4 w-4" aria-hidden />
              Eliminar
            </Button>
            {saved ? (
              <span role="status" className="text-sm text-success">
                Guardado.
              </span>
            ) : null}
          </div>
        </form>

        <TestSendBox
          accountId={accountId}
          templateId={template.id}
          disabled={dirty}
        />
      </CardContent>
    </Card>
  );
}
