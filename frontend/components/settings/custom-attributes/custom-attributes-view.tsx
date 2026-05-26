"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ATTRIBUTE_DISPLAY_TYPES,
  type AttributeModel,
  type CustomAttribute,
  type CustomAttributeInput,
  useCreateCustomAttribute,
  useCustomAttributes,
  useDeleteCustomAttribute,
  useUpdateCustomAttribute,
} from "@/lib/api/custom-attributes";
import { cn } from "@/lib/utils";

import { CustomAttributeForm } from "./custom-attribute-form";

const MODEL_FILTERS: { key: AttributeModel | undefined; label: string }[] = [
  { key: undefined, label: "Todos" },
  { key: "conversation_attribute", label: "Conversaciones" },
  { key: "contact_attribute", label: "Contactos" },
];

const TYPE_LABEL: Record<string, string> = Object.fromEntries(
  ATTRIBUTE_DISPLAY_TYPES.map((t) => [t.value, t.label]),
);

export function CustomAttributesView({ accountId }: { accountId: string }) {
  const [model, setModel] = useState<AttributeModel | undefined>(undefined);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<CustomAttribute | null>(null);

  const { data, isLoading, isError } = useCustomAttributes(accountId, model);
  const create = useCreateCustomAttribute(accountId);
  const update = useUpdateCustomAttribute(accountId);

  async function handleCreate(input: CustomAttributeInput) {
    await create.mutateAsync(input);
    setCreating(false);
  }

  async function handleUpdate(input: CustomAttributeInput) {
    if (!editing) return;
    await update.mutateAsync({ id: editing.id, patch: input });
    setEditing(null);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-fg">
          Atributos personalizados
        </h2>
        {!creating && !editing ? (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            Nuevo atributo
          </Button>
        ) : null}
      </div>

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>Nuevo atributo</CardTitle>
          </CardHeader>
          <CardContent>
            <CustomAttributeForm
              submitting={create.isPending}
              onSubmit={handleCreate}
              onCancel={() => setCreating(false)}
            />
          </CardContent>
        </Card>
      ) : null}

      {editing ? (
        <Card>
          <CardHeader>
            <CardTitle>Editar atributo</CardTitle>
          </CardHeader>
          <CardContent>
            <CustomAttributeForm
              initial={editing}
              submitting={update.isPending}
              onSubmit={handleUpdate}
              onCancel={() => setEditing(null)}
            />
          </CardContent>
        </Card>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {MODEL_FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={() => setModel(f.key)}
            aria-pressed={model === f.key}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              model === f.key
                ? "bg-primary text-primary-fg"
                : "border border-border bg-surface text-fg hover:bg-surface-2",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar los atributos.
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay atributos definidos todavía.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {data?.map((a) => (
              <AttrRow
                key={a.id}
                accountId={accountId}
                attribute={a}
                onEdit={() => {
                  setCreating(false);
                  setEditing(a);
                }}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function AttrRow({
  accountId,
  attribute,
  onEdit,
}: {
  accountId: string;
  attribute: CustomAttribute;
  onEdit: () => void;
}) {
  const del = useDeleteCustomAttribute(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    if (!window.confirm(`¿Eliminar "${attribute.attribute_display_name}"?`))
      return;
    setError(null);
    try {
      await del.mutateAsync(attribute.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo eliminar.");
    }
  }

  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">
          {attribute.attribute_display_name}
        </p>
        <p className="text-xs text-fg-muted">
          <code>{attribute.attribute_key}</code> ·{" "}
          {TYPE_LABEL[attribute.attribute_display_type] ??
            attribute.attribute_display_type}
          {attribute.attribute_description
            ? ` · ${attribute.attribute_description}`
            : ""}
        </p>
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
      <span
        className={cn(
          "rounded-full px-2 py-0.5 text-xs",
          attribute.attribute_model === "conversation_attribute"
            ? "bg-info/10 text-info"
            : "bg-warning/10 text-warning",
        )}
      >
        {attribute.attribute_model === "conversation_attribute"
          ? "Conversaciones"
          : "Contactos"}
      </span>
      <button
        type="button"
        aria-label="Editar"
        title="Editar"
        onClick={onEdit}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Pencil className="h-4 w-4" aria-hidden />
      </button>
      <button
        type="button"
        aria-label="Eliminar"
        title="Eliminar"
        onClick={onDelete}
        disabled={del.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
    </li>
  );
}
