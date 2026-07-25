"use client";

import { Eye, EyeOff, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type Label as LabelType,
  type LabelInput,
  useCreateLabel,
  useDeleteLabel,
  useLabels,
  useUpdateLabel,
} from "@/lib/api/labels";

import { LabelForm } from "./label-form";

export function LabelsView({ accountId }: { accountId: string }) {
  const { data, isLoading, isError } = useLabels(accountId);
  const create = useCreateLabel(accountId);
  const update = useUpdateLabel(accountId);

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<LabelType | null>(null);

  async function handleCreate(input: LabelInput) {
    await create.mutateAsync(input);
    setCreating(false);
  }

  async function handleUpdate(input: LabelInput) {
    if (!editing) return;
    await update.mutateAsync({ id: editing.id, patch: input });
    setEditing(null);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-fg">Etiquetas</h2>
        {!creating && !editing ? (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            Nueva etiqueta
          </Button>
        ) : null}
      </div>

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>Nueva etiqueta</CardTitle>
          </CardHeader>
          <CardContent>
            <LabelForm
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
            <CardTitle>Editar etiqueta</CardTitle>
          </CardHeader>
          <CardContent>
            <LabelForm
              initial={editing}
              submitting={update.isPending}
              onSubmit={handleUpdate}
              onCancel={() => setEditing(null)}
            />
          </CardContent>
        </Card>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar las etiquetas.
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay etiquetas todavía.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {data?.map((l) => (
              <LabelRow
                key={l.id}
                accountId={accountId}
                label={l}
                onEdit={() => {
                  setCreating(false);
                  setEditing(l);
                }}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function LabelRow({
  accountId,
  label,
  onEdit,
}: {
  accountId: string;
  label: LabelType;
  onEdit: () => void;
}) {
  const del = useDeleteLabel(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    if (!window.confirm(`¿Eliminar "${label.title}"?`)) return;
    setError(null);
    try {
      await del.mutateAsync(label.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo eliminar.");
    }
  }

  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <span
        className="h-5 w-5 shrink-0 rounded-full border border-border"
        aria-hidden
        style={{ backgroundColor: label.color ?? "transparent" }}
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">{label.title}</p>
        {label.description ? (
          <p className="truncate text-xs text-fg-muted">{label.description}</p>
        ) : null}
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
      <span
        className="flex items-center gap-1 text-xs text-fg-muted"
        title={
          label.show_on_sidebar
            ? "Visible en la barra lateral"
            : "Oculto en la barra lateral"
        }
      >
        {label.show_on_sidebar ? (
          <Eye className="h-4 w-4" aria-hidden />
        ) : (
          <EyeOff className="h-4 w-4" aria-hidden />
        )}
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
