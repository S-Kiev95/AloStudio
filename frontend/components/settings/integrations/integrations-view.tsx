"use client";

import { ChevronRight, Puzzle } from "lucide-react";
import Link from "next/link";

import { type IntegrationApp, useIntegrationApps } from "@/lib/api/integrations";
import { cn } from "@/lib/utils";

export function IntegrationsView({ accountId }: { accountId: string }) {
  const { data, isLoading, isError } = useIntegrationApps(accountId);

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <h2 className="text-xl font-semibold text-fg">Integraciones</h2>

      <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar las integraciones.
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay integraciones disponibles.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {data?.map((app) => (
              <AppRow key={app.id} accountId={accountId} app={app} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function AppRow({
  accountId,
  app,
}: {
  accountId: string;
  app: IntegrationApp;
}) {
  const connected = app.hooks.length > 0;
  return (
    <li>
      <Link
        href={`/accounts/${accountId}/settings/integrations/${app.id}`}
        className="flex items-center gap-3 px-4 py-3 hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Puzzle className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">{app.name}</p>
          <p className="truncate text-xs text-fg-muted">
            {app.short_description || app.description}
          </p>
        </div>
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-xs font-medium",
            connected
              ? "bg-success/10 text-success"
              : app.enabled
                ? "bg-surface-2 text-fg-muted"
                : "bg-warning/10 text-warning",
          )}
        >
          {connected
            ? `${app.hooks.length} conectado${app.hooks.length === 1 ? "" : "s"}`
            : app.enabled
              ? "Disponible"
              : "Inactiva"}
        </span>
        <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
      </Link>
    </li>
  );
}
