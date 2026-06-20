"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAgents } from "@/lib/api/account";
import {
  type AudienceEntry,
  type Campaign,
  type CampaignInput,
  type CampaignType,
  CAMPAIGN_TYPES,
} from "@/lib/api/campaigns";
import { useInboxes } from "@/lib/api/inboxes";
import { useLabels } from "@/lib/api/labels";
import { cn } from "@/lib/utils";

const selectClass =
  "h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function CampaignForm({
  accountId,
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  accountId: string;
  initial?: Campaign;
  submitting?: boolean;
  onSubmit: (input: CampaignInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const inboxes = useInboxes(accountId);
  const agents = useAgents(accountId);
  const labels = useLabels(accountId);

  const [title, setTitle] = useState(initial?.title ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [message, setMessage] = useState(initial?.message ?? "");
  const [campaignType, setCampaignType] = useState<CampaignType>(
    initial?.campaign_type ?? "ongoing",
  );
  const [inboxId, setInboxId] = useState<string>(
    initial?.inbox_id ? String(initial.inbox_id) : "",
  );
  const [senderId, setSenderId] = useState<string>(
    initial?.sender_id ? String(initial.sender_id) : "",
  );
  const [scheduledAt, setScheduledAt] = useState<string>(
    initial?.scheduled_at ? isoToLocal(initial.scheduled_at) : "",
  );
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);
  const [businessHoursOnly, setBusinessHoursOnly] = useState(
    initial?.trigger_only_during_business_hours ?? false,
  );
  const [urlPattern, setUrlPattern] = useState<string>(
    typeof initial?.trigger_rules?.url === "string"
      ? (initial.trigger_rules.url as string)
      : "",
  );
  const [timeOnPage, setTimeOnPage] = useState<string>(
    typeof initial?.trigger_rules?.time_on_page === "number"
      ? String(initial.trigger_rules.time_on_page)
      : "",
  );
  const [audienceLabels, setAudienceLabels] = useState<Set<number>>(
    new Set(
      (initial?.audience ?? [])
        .filter((a) => a.type === "Label")
        .map((a) => a.id),
    ),
  );
  const [error, setError] = useState<string | null>(null);

  function toggleLabel(id: number) {
    setAudienceLabels((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function submit() {
    setError(null);
    if (!title.trim()) return setError("El título es obligatorio.");
    if (!inboxId)
      return setError("Elegí una bandeja.");
    if (campaignType === "one_off" && !scheduledAt)
      return setError("Las campañas puntuales necesitan fecha programada.");

    const audience: AudienceEntry[] = Array.from(audienceLabels).map((id) => ({
      type: "Label",
      id,
    }));

    const triggerRules: Record<string, unknown> = {};
    if (urlPattern.trim()) triggerRules.url = urlPattern.trim();
    if (timeOnPage.trim()) {
      const n = Number(timeOnPage);
      if (!Number.isNaN(n) && n > 0) triggerRules.time_on_page = n;
    }

    const input: CampaignInput = {
      title: title.trim(),
      description: description.trim() || null,
      message: message.trim() || null,
      inbox_id: Number(inboxId),
      sender_id: senderId ? Number(senderId) : null,
      enabled,
      campaign_type: campaignType,
      audience,
      trigger_rules: triggerRules,
      ...(campaignType === "one_off"
        ? { scheduled_at: localToIso(scheduledAt) }
        : {
            trigger_only_during_business_hours: businessHoursOnly,
          }),
    };

    try {
      await onSubmit(input);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo guardar la campaña.",
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
        <Label htmlFor="c-title" required>
          Título
        </Label>
        <Input
          id="c-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={255}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="c-desc">Descripción</Label>
        <Textarea
          id="c-desc"
          rows={2}
          value={description ?? ""}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label>Tipo</Label>
        <div className="flex flex-wrap gap-3 text-sm">
          {CAMPAIGN_TYPES.map((t) => (
            <label key={t.value} className="flex items-center gap-1.5">
              <input
                type="radio"
                checked={campaignType === t.value}
                onChange={() => setCampaignType(t.value)}
                disabled={Boolean(initial)}
              />
              {t.label}
            </label>
          ))}
        </div>
        {initial ? (
          <p className="text-xs text-fg-muted">
            El tipo no se puede cambiar después de crear la campaña.
          </p>
        ) : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="c-inbox" required>
            Bandeja
          </Label>
          <select
            id="c-inbox"
            className={selectClass}
            value={inboxId}
            onChange={(e) => setInboxId(e.target.value)}
          >
            <option value="">Elegí una bandeja…</option>
            {inboxes.data?.map((ib) => (
              <option key={ib.id} value={ib.id}>
                {ib.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="c-sender">Remitente</Label>
          <select
            id="c-sender"
            className={selectClass}
            value={senderId}
            onChange={(e) => setSenderId(e.target.value)}
          >
            <option value="">Sin remitente específico</option>
            {agents.data?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="c-msg">Mensaje</Label>
        <Textarea
          id="c-msg"
          rows={3}
          value={message ?? ""}
          onChange={(e) => setMessage(e.target.value)}
        />
      </div>

      {campaignType === "one_off" ? (
        <div className="space-y-1.5">
          <Label htmlFor="c-when" required>
            Fecha programada
          </Label>
          <Input
            id="c-when"
            type="datetime-local"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
          />
          {labels.data?.length ? (
            <div className="mt-3 space-y-1.5">
              <Label>Audiencia (etiquetas)</Label>
              <div className="flex flex-wrap gap-1.5">
                {labels.data.map((l) => {
                  const on = audienceLabels.has(l.id);
                  return (
                    <button
                      key={l.id}
                      type="button"
                      onClick={() => toggleLabel(l.id)}
                      aria-pressed={on}
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-xs",
                        on
                          ? "border-primary bg-surface-2 font-semibold text-fg"
                          : "border-border text-fg-muted hover:bg-surface-2",
                      )}
                    >
                      {l.title}
                    </button>
                  );
                })}
              </div>
              <p className="text-xs text-fg-muted">
                Sin etiquetas seleccionadas la campaña se envía a toda la base.
              </p>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="space-y-3 rounded-md border border-border bg-surface-2 p-3">
          <p className="text-xs font-medium uppercase text-fg-muted">
            Reglas del trigger
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="c-url">Patrón de URL</Label>
              <Input
                id="c-url"
                value={urlPattern}
                onChange={(e) => setUrlPattern(e.target.value)}
                placeholder="https://midominio.com/pricing"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="c-time">Tiempo en página (segundos)</Label>
              <Input
                id="c-time"
                type="number"
                min={0}
                value={timeOnPage}
                onChange={(e) => setTimeOnPage(e.target.value)}
                placeholder="30"
              />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-fg">
            <input
              type="checkbox"
              checked={businessHoursOnly}
              onChange={(e) => setBusinessHoursOnly(e.target.checked)}
            />
            Disparar solo durante horario laboral
          </label>
        </div>
      )}

      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
        Activa
      </label>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? "Guardar cambios" : "Crear campaña"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}

/** ISO 8601 → ``YYYY-MM-DDTHH:MM`` for ``<input type="datetime-local">``. */
function isoToLocal(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`;
}

function localToIso(local: string): string {
  if (!local) return new Date().toISOString();
  return new Date(local).toISOString();
}
