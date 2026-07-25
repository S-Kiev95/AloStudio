"use client";

import { Pencil, Plus, Search, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type CannedResponse,
  type CannedResponseInput,
  useCannedResponses,
  useCreateCannedResponse,
  useDeleteCannedResponse,
  useUpdateCannedResponse,
} from "@/lib/api/canned-responses";

import { CannedResponseForm } from "./canned-response-form";

export function CannedResponsesView({ accountId }: { accountId: string }) {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const id = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(id);
  }, [search]);

  const { data, isLoading, isError } = useCannedResponses(
    accountId,
    debouncedSearch || undefined,
  );
  const create = useCreateCannedResponse(accountId);
  const update = useUpdateCannedResponse(accountId);

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<CannedResponse | null>(null);

  async function handleCreate(input: CannedResponseInput) {
    await create.mutateAsync(input);
    setCreating(false);
  }

  async function handleUpdate(input: CannedResponseInput) {
    if (!editing) return;
    await update.mutateAsync({ id: editing.id, patch: input });
    setEditing(null);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-fg">Respuestas predefinidas</h2>
        {!creating && !editing ? (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            Nueva respuesta
          </Button>
        ) : null}
      </div>

      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted"
          aria-hidden
        />
        <input
          type="search"
          aria-label="Buscar respuestas"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar por atajo o contenido…"
          className="h-11 w-full rounded-md border border-border bg-surface pl-9 pr-9 text-sm text-fg placeholder:text-fg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
        />
        {search ? (
          <button
            type="button"
            aria-label="Limpiar búsqueda"
            onClick={() => setSearch("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-fg-muted hover:bg-surface-2 hover:text-fg"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        ) : null}
      </div>

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>Nueva respuesta</CardTitle>
          </CardHeader>
          <CardContent>
            <CannedResponseForm
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
            <CardTitle>Editar respuesta</CardTitle>
          </CardHeader>
          <CardContent>
            <CannedResponseForm
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
            No se pudieron cargar las respuestas.
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {debouncedSearch
              ? "No se encontraron respuestas."
              : "No hay respuestas todavía."}
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {data?.map((cr) => (
              <CannedRow
                key={cr.id}
                accountId={accountId}
                canned={cr}
                onEdit={() => {
                  setCreating(false);
                  setEditing(cr);
                }}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function CannedRow({
  accountId,
  canned,
  onEdit,
}: {
  accountId: string;
  canned: CannedResponse;
  onEdit: () => void;
}) {
  const del = useDeleteCannedResponse(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    if (!window.confirm(`¿Eliminar "/${canned.short_code}"?`)) return;
    setError(null);
    try {
      await del.mutateAsync(canned.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo eliminar.");
    }
  }

  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <code className="shrink-0 rounded bg-surface-2 px-1.5 py-0.5 text-xs font-semibold text-fg">
        /{canned.short_code}
      </code>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-fg">{canned.content}</p>
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
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
