"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import { useInboxes } from "@/lib/api/inboxes";
import {
  WEBHOOK_EVENTS,
  type Webhook,
  type WebhookEvent,
  type WebhookInput,
} from "@/lib/api/webhooks";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";

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
  const t = useT();
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
    if (!url.trim()) return setError(t("settingsWebhooks.urlRequired"));
    if (events.size === 0)
      return setError(t("settingsWebhooks.eventsRequired"));

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
        (e as { message?: string })?.message ?? t("settingsWebhooks.saveFailed"),
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
        <Label htmlFor="wh-name">{t("profile.name")}</Label>
        <Input
          id="wh-name"
          value={name ?? ""}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="wh-url" required>
          {t("settingsWebhooks.url")}
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
        <Label htmlFor="wh-inbox">{t("settingsWebhooks.inboxOptional")}</Label>
        <select
          id="wh-inbox"
          className={selectClassName()}
          value={inboxId}
          onChange={(e) => setInboxId(e.target.value)}
        >
          <option value="">{t("conversations.allInboxes")}</option>
          {inboxes.data?.map((ib) => (
            <option key={ib.id} value={ib.id}>
              {ib.name}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <Label>{t("settingsWebhooks.events")}</Label>
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
                  "rounded-sm border px-2 py-0.5 text-xs transition-colors",
                  on
                    ? "border-neon bg-focused font-medium text-lit"
                    : "border-glass bg-field text-fg-muted hover:bg-hover-glass hover:text-fg",
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
          {initial ? t("common.saveChanges") : t("settingsWebhooks.create")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          {t("actions.cancel")}
        </Button>
      </div>
    </div>
  );
}
