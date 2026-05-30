"use client";

import { ArrowLeft, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type IntegrationHook,
  useDeleteIntegrationHook,
  useIntegrationApp,
} from "@/lib/api/integrations";

export function IntegrationAppView({
  accountId,
  appId,
}: {
  accountId: string;
  appId: string;
}) {
  const { data: app, isLoading, isError } = useIntegrationApp(accountId, appId);

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <Link
        href={`/accounts/${accountId}/settings/integrations`}
        className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Volver a integraciones
      </Link>

      {isLoading ? (
        <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
      ) : isError || !app ? (
        <p role="alert" className="p-8 text-center text-sm text-danger">
          No se pudo cargar la integración.
        </p>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>{app.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="text-sm text-fg">{app.description}</p>
              <p className="text-xs text-fg-muted">
                Estado: {app.enabled ? "Disponible" : "Inactiva"}
                {app.allow_multiple_hooks !== undefined
                  ? ` · Múltiples conexiones: ${app.allow_multiple_hooks ? "sí" : "no"}`
                  : ""}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Conexiones</CardTitle>
            </CardHeader>
            <CardContent>
              {app.hooks.length === 0 ? (
                <div className="space-y-2">
                  <p className="text-sm text-fg-muted">
                    Esta integración aún no está conectada.
                  </p>
                  <p className="text-xs text-fg-muted">
                    La conexión por OAuth depende del proveedor y se habilita
                    desde una próxima entrega.
                  </p>
                </div>
              ) : (
                <ul className="divide-y divide-border">
                  {app.hooks.map((hook) => (
                    <HookRow
                      key={hook.id}
                      accountId={accountId}
                      hook={hook}
                    />
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function HookRow({
  accountId,
  hook,
}: {
  accountId: string;
  hook: IntegrationHook;
}) {
  const del = useDeleteIntegrationHook(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    if (!window.confirm("¿Eliminar esta conexión?")) return;
    setError(null);
    try {
      await del.mutateAsync(hook.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo eliminar.");
    }
  }

  return (
    <li className="flex items-center gap-3 py-3">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-fg">
          {hook.inbox ? hook.inbox.name : "Conexión global"}
        </p>
        <p className="text-xs text-fg-muted">
          {hook.hook_type} · {hook.status ? "activa" : "inactiva"}
          {hook.reference_id ? ` · ref ${hook.reference_id}` : ""}
        </p>
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
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
