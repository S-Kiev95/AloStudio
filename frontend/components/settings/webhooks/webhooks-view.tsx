"use client";

import { Pencil, Plus, Trash2, Webhook as WebhookIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type Webhook,
  type WebhookInput,
  useCreateWebhook,
  useDeleteWebhook,
  useUpdateWebhook,
  useWebhooks,
} from "@/lib/api/webhooks";

import { WebhookForm } from "./webhook-form";

export function WebhooksView({ accountId }: { accountId: string }) {
  const { data, isLoading, isError } = useWebhooks(accountId);
  const create = useCreateWebhook(accountId);
  const update = useUpdateWebhook(accountId);

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Webhook | null>(null);

  async function handleCreate(input: WebhookInput) {
    await create.mutateAsync(input);
    setCreating(false);
  }

  async function handleUpdate(input: WebhookInput) {
    if (!editing) return;
    await update.mutateAsync({ id: editing.id, patch: input });
    setEditing(null);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-fg">Webhooks</h2>
        {!creating && !editing ? (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            Nuevo webhook
          </Button>
        ) : null}
      </div>

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>Nuevo webhook</CardTitle>
          </CardHeader>
          <CardContent>
            <WebhookForm
              accountId={accountId}
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
            <CardTitle>Editar webhook</CardTitle>
          </CardHeader>
          <CardContent>
            <WebhookForm
              accountId={accountId}
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
            No se pudieron cargar los webhooks.
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay webhooks todavía.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {data?.map((w) => (
              <WebhookRow
                key={w.id}
                accountId={accountId}
                webhook={w}
                onEdit={() => {
                  setCreating(false);
                  setEditing(w);
                }}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function WebhookRow({
  accountId,
  webhook,
  onEdit,
}: {
  accountId: string;
  webhook: Webhook;
  onEdit: () => void;
}) {
  const del = useDeleteWebhook(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    if (!window.confirm(`¿Eliminar este webhook?`)) return;
    setError(null);
    try {
      await del.mutateAsync(webhook.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo eliminar.");
    }
  }

  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <WebhookIcon className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">
          {webhook.name?.trim() || webhook.url}
        </p>
        <p className="truncate text-xs text-fg-muted">{webhook.url}</p>
        <p className="text-xs text-fg-muted">
          {webhook.subscriptions.length}{" "}
          {webhook.subscriptions.length === 1 ? "evento" : "eventos"}
          {webhook.inbox ? ` · ${webhook.inbox.name}` : " · Todas las bandejas"}
        </p>
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
