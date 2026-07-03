"use client";

import { ArrowLeft, ExternalLink, Plus, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useInboxes } from "@/lib/api/inboxes";
import {
  type IntegrationApp,
  type IntegrationHook,
  useCreateIntegrationHook,
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
            <CardContent className="space-y-4">
              <ConnectSection accountId={accountId} app={app} />

              {app.hooks.length === 0 ? (
                <p className="text-sm text-fg-muted">
                  Esta integración aún no está conectada.
                </p>
              ) : (
                <ul className="divide-y divide-border">
                  {app.hooks.map((hook) => (
                    <HookRow key={hook.id} accountId={accountId} hook={hook} />
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

/**
 * The Connect affordance keyed off ``app.action``: an external URL → OAuth
 * link; a relative path → an inline hook-creation form; ``null`` → the app
 * needs extra server config first.
 */
function ConnectSection({
  accountId,
  app,
}: {
  accountId: string;
  app: IntegrationApp;
}) {
  if (app.action && /^https?:\/\//.test(app.action)) {
    return (
      <div className="space-y-1">
        <a href={app.action} className={buttonVariants({ size: "sm" })}>
          <ExternalLink className="h-4 w-4" aria-hidden />
          Conectar con {app.name}
        </a>
        <p className="text-xs text-fg-muted">
          Se abrirá el flujo de autorización de {app.name}.
        </p>
      </div>
    );
  }
  if (app.action) {
    return <InlineConnectForm accountId={accountId} app={app} />;
  }
  return (
    <p className="text-xs text-fg-muted">
      Esta integración requiere configuración adicional del servidor para
      conectarse.
    </p>
  );
}

function InlineConnectForm({
  accountId,
  app,
}: {
  accountId: string;
  app: IntegrationApp;
}) {
  const create = useCreateIntegrationHook(accountId);
  const inboxes = useInboxes(accountId);
  const [open, setOpen] = useState(false);
  const [inboxId, setInboxId] = useState("");
  const [rows, setRows] = useState<{ key: string; value: string }[]>([
    { key: "", value: "" },
  ]);
  const [error, setError] = useState<string | null>(null);

  const needsInbox = app.hook_type === "inbox";

  function setRow(idx: number, field: "key" | "value", val: string) {
    setRows((rs) => rs.map((r, i) => (i === idx ? { ...r, [field]: val } : r)));
  }

  async function submit() {
    setError(null);
    if (needsInbox && !inboxId) return setError("Elegí una bandeja.");
    const settings: Record<string, string> = {};
    for (const r of rows) {
      const k = r.key.trim();
      if (k) settings[k] = r.value;
    }
    try {
      await create.mutateAsync({
        app_id: app.id,
        hook_type: app.hook_type,
        inbox_id: needsInbox ? Number(inboxId) : undefined,
        settings,
      });
      setOpen(false);
      setRows([{ key: "", value: "" }]);
      setInboxId("");
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo conectar.");
    }
  }

  if (!open) {
    return (
      <Button size="sm" onClick={() => setOpen(true)}>
        <Plus className="h-4 w-4" aria-hidden />
        Conectar
      </Button>
    );
  }

  return (
    <div className="space-y-3 rounded-lg border border-border p-3">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      {needsInbox ? (
        <label className="block space-y-1 text-sm">
          <span className="text-fg-muted">Bandeja de entrada</span>
          <select
            aria-label="Bandeja de entrada"
            value={inboxId}
            onChange={(e) => setInboxId(e.target.value)}
            className="h-9 w-full rounded-md border border-border bg-surface px-2 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="">Elegí una bandeja…</option>
            {inboxes.data?.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <div className="space-y-2">
        <span className="text-sm text-fg-muted">Ajustes</span>
        {rows.map((r, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <Input
              aria-label={`Clave ${idx + 1}`}
              placeholder="clave"
              value={r.key}
              onChange={(e) => setRow(idx, "key", e.target.value)}
            />
            <Input
              aria-label={`Valor ${idx + 1}`}
              placeholder="valor"
              value={r.value}
              onChange={(e) => setRow(idx, "value", e.target.value)}
            />
            <button
              type="button"
              aria-label={`Quitar ajuste ${idx + 1}`}
              onClick={() => setRows((rs) => rs.filter((_, i) => i !== idx))}
              disabled={rows.length === 1}
              className="rounded p-1.5 text-fg-muted hover:text-danger disabled:opacity-40"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => setRows((rs) => [...rs, { key: "", value: "" }])}
          className="text-xs font-medium text-primary hover:underline"
        >
          + Agregar ajuste
        </button>
      </div>

      <div className="flex gap-2">
        <Button size="sm" onClick={submit} loading={create.isPending}>
          Conectar
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setOpen(false)}
          disabled={create.isPending}
        >
          Cancelar
        </Button>
      </div>
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
