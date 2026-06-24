"use client";

import { ArrowLeft, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/errors";
import {
  channelLabel,
  useDeleteInbox,
  useInbox,
  useUpdateInbox,
} from "@/lib/api/inboxes";

import { InboxMembersPanel } from "./inbox-members-panel";

export function InboxDetailView({
  accountId,
  inboxId,
}: {
  accountId: string;
  inboxId: number;
}) {
  const { data: inbox, isLoading, isError } = useInbox(accountId, inboxId);
  const update = useUpdateInbox(accountId);
  const del = useDeleteInbox(accountId);
  const router = useRouter();
  const listHref = `/accounts/${accountId}/settings/inboxes`;

  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (inbox) setName(inbox.name);
  }, [inbox]);

  async function saveName(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    if (!name.trim()) {
      setError("El nombre es obligatorio.");
      return;
    }
    try {
      await update.mutateAsync({ id: inboxId, patch: { name: name.trim() } });
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar.");
    }
  }

  async function onDelete() {
    if (!window.confirm(`¿Eliminar la bandeja "${inbox?.name}"?`)) return;
    setError(null);
    try {
      await del.mutateAsync(inboxId);
      router.push(listHref);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo eliminar.");
    }
  }

  if (isLoading) {
    return <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>;
  }
  if (isError || !inbox) {
    return (
      <p role="alert" className="p-8 text-center text-sm text-danger">
        No se pudo cargar la bandeja.
      </p>
    );
  }

  return (
    <div className="max-w-2xl space-y-4">
      <div>
        <Link
          href={listHref}
          className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Bandejas
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-semibold text-fg">{inbox.name}</h2>
          <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs font-medium text-fg-muted">
            {channelLabel(inbox.channel_type)}
          </span>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">General</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={saveName} className="space-y-3">
            <label className="block space-y-1">
              <span className="text-sm font-medium text-fg">Nombre</span>
              <Input
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setSaved(false);
                }}
              />
            </label>
            {error ? (
              <p role="alert" className="text-sm text-danger">
                {error}
              </p>
            ) : null}
            <div className="flex items-center gap-2">
              <Button type="submit" size="sm" loading={update.isPending}>
                Guardar
              </Button>
              {saved ? (
                <span className="text-xs text-success">Guardado ✓</span>
              ) : null}
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Agentes</CardTitle>
        </CardHeader>
        <CardContent>
          <InboxMembersPanel accountId={accountId} inboxId={inboxId} />
        </CardContent>
      </Card>

      {inbox.callback_webhook_url || inbox.inbox_identifier ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Webhook</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {inbox.callback_webhook_url ? (
              <CodeRow label="Callback URL" value={inbox.callback_webhook_url} />
            ) : null}
            {inbox.inbox_identifier ? (
              <CodeRow label="Inbox identifier" value={inbox.inbox_identifier} />
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
          <div>
            <p className="text-sm font-medium text-fg">Eliminar bandeja</p>
            <p className="text-xs text-fg-muted">
              Borra el canal. Las conversaciones existentes quedan sin bandeja.
            </p>
          </div>
          <Button
            variant="destructive"
            size="sm"
            onClick={onDelete}
            loading={del.isPending}
          >
            <Trash2 className="h-4 w-4" aria-hidden />
            Eliminar
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function CodeRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase text-fg-muted">{label}</p>
      <code className="block truncate rounded bg-surface-2 px-2 py-1 font-numeric text-xs text-fg">
        {value}
      </code>
    </div>
  );
}
