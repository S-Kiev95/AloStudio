"use client";

import { BookOpen, ChevronRight, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type Portal,
  type PortalInput,
  useCreatePortal,
  useDeletePortal,
  usePortals,
} from "@/lib/api/portals";
import { cn } from "@/lib/utils";

import { PortalForm } from "./portal-form";

export function PortalsView({ accountId }: { accountId: string }) {
  const { data, isLoading, isError } = usePortals(accountId);
  const create = useCreatePortal(accountId);

  const [creating, setCreating] = useState(false);

  async function handleCreate(input: PortalInput) {
    await create.mutateAsync(input);
    setCreating(false);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-fg">Help Center</h2>
        {!creating ? (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            Nuevo portal
          </Button>
        ) : null}
      </div>

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>Nuevo portal</CardTitle>
          </CardHeader>
          <CardContent>
            <PortalForm
              accountId={accountId}
              submitting={create.isPending}
              onSubmit={handleCreate}
              onCancel={() => setCreating(false)}
            />
          </CardContent>
        </Card>
      ) : null}

      <div className="overflow-hidden rounded-lg border border-border bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar los portales.
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay portales todavía. Creá uno para empezar.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {data?.map((p) => (
              <PortalRow key={p.id} accountId={accountId} portal={p} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function PortalRow({
  accountId,
  portal,
}: {
  accountId: string;
  portal: Portal;
}) {
  const del = useDeletePortal(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(`¿Eliminar el portal "${portal.name}"?`)) return;
    setError(null);
    try {
      await del.mutateAsync(portal.slug);
    } catch (err) {
      setError(
        (err as { message?: string })?.message ?? "No se pudo eliminar.",
      );
    }
  }

  return (
    <li className="flex items-center gap-1 pr-2 hover:bg-surface-2">
      <Link
        href={`/accounts/${accountId}/help-center/${portal.slug}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white"
          style={{ backgroundColor: portal.color ?? "#1f93ff" }}
        >
          <BookOpen className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">
            {portal.name}
            {portal.archived ? (
              <span className="ml-2 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium uppercase text-fg-muted">
                Archivado
              </span>
            ) : null}
          </p>
          <p className="truncate text-xs text-fg-muted">
            /{portal.slug}
            {portal.custom_domain ? ` · ${portal.custom_domain}` : ""}
          </p>
          {error ? (
            <p role="alert" className="text-xs text-danger">
              {error}
            </p>
          ) : null}
        </div>
      </Link>
      <button
        type="button"
        aria-label="Eliminar"
        title="Eliminar"
        onClick={onDelete}
        disabled={del.isPending}
        className={cn(
          "rounded-md p-1.5 text-fg-muted hover:bg-surface hover:text-danger disabled:opacity-50",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
