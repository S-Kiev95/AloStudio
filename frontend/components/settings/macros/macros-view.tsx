"use client";

import { ChevronRight, Plus, Trash2, Zap } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import {
  type Macro,
  useDeleteMacro,
  useMacros,
} from "@/lib/api/macros";
import { cn } from "@/lib/utils";

export function MacrosView({ accountId }: { accountId: string }) {
  const { data, isLoading, isError } = useMacros(accountId);

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-fg">Macros</h2>
        <Link
          href={`/accounts/${accountId}/settings/macros/new`}
          className={buttonVariants({ size: "sm" })}
        >
          <Plus className="h-4 w-4" aria-hidden />
          Nuevo macro
        </Link>
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar los macros.
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay macros todavía.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {data?.map((m) => (
              <MacroRow key={m.id} accountId={accountId} macro={m} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function MacroRow({ accountId, macro }: { accountId: string; macro: Macro }) {
  const del = useDeleteMacro(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(`¿Eliminar el macro "${macro.name}"?`)) return;
    setError(null);
    try {
      await del.mutateAsync(macro.id);
    } catch (err) {
      setError((err as { message?: string })?.message ?? "No se pudo eliminar.");
    }
  }

  return (
    <li className="flex items-center gap-1 pr-2 hover:bg-surface-2">
      <Link
        href={`/accounts/${accountId}/settings/macros/${macro.id}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Zap className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">{macro.name}</p>
          <p className="text-xs text-fg-muted">
            {macro.actions.length}{" "}
            {macro.actions.length === 1 ? "acción" : "acciones"}
            {macro.created_by ? ` · por ${macro.created_by.name}` : ""}
          </p>
          {error ? (
            <p role="alert" className="text-xs text-danger">
              {error}
            </p>
          ) : null}
        </div>
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-xs font-medium",
            macro.visibility === "global"
              ? "bg-info/10 text-info"
              : "bg-surface-2 text-fg-muted",
          )}
        >
          {macro.visibility === "global" ? "Global" : "Personal"}
        </span>
      </Link>
      <button
        type="button"
        aria-label="Eliminar"
        title="Eliminar"
        onClick={onDelete}
        disabled={del.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
