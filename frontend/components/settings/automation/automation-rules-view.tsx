"use client";

import { ChevronRight, Copy, Plus, Trash2, Zap } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import {
  AUTOMATION_EVENT_LABELS,
  type AutomationRule,
  useAutomationRules,
  useCloneAutomationRule,
  useDeleteAutomationRule,
  useUpdateAutomationRule,
} from "@/lib/api/automation-rules";
import { cn } from "@/lib/utils";

export function AutomationRulesView({ accountId }: { accountId: string }) {
  const { data, isLoading, isError } = useAutomationRules(accountId);

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-fg">Automatización</h2>
        <Link
          href={`/accounts/${accountId}/settings/automation/new`}
          className={buttonVariants({ size: "sm" })}
        >
          <Plus className="h-4 w-4" aria-hidden />
          Nueva regla
        </Link>
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar las reglas.
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay reglas todavía.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {data?.map((r) => (
              <RuleRow key={r.id} accountId={accountId} rule={r} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function RuleRow({
  accountId,
  rule,
}: {
  accountId: string;
  rule: AutomationRule;
}) {
  const update = useUpdateAutomationRule(accountId);
  const del = useDeleteAutomationRule(accountId);
  const clone = useCloneAutomationRule(accountId);
  const [error, setError] = useState<string | null>(null);

  async function run(
    fn: () => Promise<unknown>,
    fallback: string,
    stopEvent?: React.MouseEvent,
  ) {
    if (stopEvent) {
      stopEvent.preventDefault();
      stopEvent.stopPropagation();
    }
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError((e as { message?: string })?.message ?? fallback);
    }
  }

  return (
    <li className="flex items-center gap-1 pr-2 hover:bg-surface-2">
      <Link
        href={`/accounts/${accountId}/settings/automation/${rule.id}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Zap className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">{rule.name}</p>
          <p className="truncate text-xs text-fg-muted">
            {AUTOMATION_EVENT_LABELS[rule.event_name]} ·{" "}
            {rule.conditions.length}{" "}
            {rule.conditions.length === 1 ? "condición" : "condiciones"} ·{" "}
            {rule.actions.length}{" "}
            {rule.actions.length === 1 ? "acción" : "acciones"}
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
            rule.active
              ? "bg-success/10 text-success"
              : "bg-surface-2 text-fg-muted",
          )}
        >
          {rule.active ? "Activa" : "Inactiva"}
        </span>
      </Link>
      <button
        type="button"
        role="switch"
        aria-checked={rule.active}
        aria-label={rule.active ? "Desactivar" : "Activar"}
        title={rule.active ? "Desactivar" : "Activar"}
        onClick={(e) =>
          run(
            () =>
              update.mutateAsync({
                id: rule.id,
                patch: { active: !rule.active },
              }),
            "No se pudo cambiar el estado.",
            e,
          )
        }
        disabled={update.isPending}
        className={cn(
          "h-5 w-9 shrink-0 rounded-full p-0.5 transition-colors disabled:opacity-50",
          rule.active ? "bg-success" : "bg-surface-2",
        )}
      >
        <span
          className={cn(
            "block h-4 w-4 rounded-full bg-surface transition-transform",
            rule.active ? "translate-x-4" : "translate-x-0",
          )}
        />
      </button>
      <button
        type="button"
        aria-label="Clonar"
        title="Clonar"
        onClick={(e) => run(() => clone.mutateAsync(rule.id), "No se pudo clonar.", e)}
        disabled={clone.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface hover:text-fg disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Copy className="h-4 w-4" aria-hidden />
      </button>
      <button
        type="button"
        aria-label="Eliminar"
        title="Eliminar"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          if (!window.confirm(`¿Eliminar la regla "${rule.name}"?`)) return;
          run(() => del.mutateAsync(rule.id), "No se pudo eliminar.");
        }}
        disabled={del.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
