"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useInboxes } from "@/lib/api/inboxes";
import {
  WEBHOOK_EVENTS,
  type Webhook,
  type WebhookEvent,
  type WebhookInput,
} from "@/lib/api/webhooks";
import { cn } from "@/lib/utils";

const selectClass =
  "h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function WebhookForm({
  accountId,
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  accountId: string;
  initial?: Webhook;
  submitting?: boolean;
  onSubmit: (input: WebhookInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const inboxes = useInboxes(accountId);

  const [name, setName] = useState(initial?.name ?? "");
  const [url, setUrl] = useState(initial?.url ?? "");
  const [inboxId, setInboxId] = useState<string>(
    initial?.inbox?.id ? String(initial.inbox.id) : "",
  );
  const [events, setEvents] = useState<Set<WebhookEvent>>(
    new Set(initial?.subscriptions ?? []),
  );
  const [error, setError] = useState<string | null>(null);

  function toggle(ev: WebhookEvent) {
    setEvents((prev) => {
      const next = new Set(prev);
      if (next.has(ev)) next.delete(ev);
      else next.add(ev);
      return next;
    });
  }

  async function submit() {
    setError(null);
    if (!url.trim()) return setError("La URL es obligatoria.");
    if (events.size === 0)
      return setError("Elegí al menos un evento al que suscribirse.");

    const input: WebhookInput = {
      name: name.trim() || null,
      url: url.trim(),
      inbox_id: inboxId ? Number(inboxId) : null,
      subscriptions: Array.from(events),
    };
    try {
      await onSubmit(input);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo guardar el webhook.",
      );
    }
  }

  return (
    <div className="space-y-4">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="space-y-1.5">
        <Label htmlFor="wh-name">Nombre</Label>
        <Input
          id="wh-name"
          value={name ?? ""}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="wh-url" required>
          URL
        </Label>
        <Input
          id="wh-url"
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://…"
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="wh-inbox">Bandeja (opcional)</Label>
        <select
          id="wh-inbox"
          className={selectClass}
          value={inboxId}
          onChange={(e) => setInboxId(e.target.value)}
        >
          <option value="">Todas las bandejas</option>
          {inboxes.data?.map((ib) => (
            <option key={ib.id} value={ib.id}>
              {ib.name}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <Label>Eventos suscritos</Label>
        <div className="flex flex-wrap gap-1.5">
          {WEBHOOK_EVENTS.map((ev) => {
            const on = events.has(ev);
            return (
              <button
                key={ev}
                type="button"
                onClick={() => toggle(ev)}
                aria-pressed={on}
                className={cn(
                  "rounded-full border px-2 py-0.5 text-xs",
                  on
                    ? "border-primary bg-primary text-primary-fg"
                    : "border-border text-fg-muted hover:bg-surface-2",
                )}
              >
                {ev}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? "Guardar cambios" : "Crear webhook"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
