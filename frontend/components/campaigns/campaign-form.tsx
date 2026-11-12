"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
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
import {
  useSyncWhatsappTemplates,
  useWhatsappTemplates,
} from "@/lib/api/whatsapp-templates";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";

const selectClass = selectClassName();

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
  const t = useT();
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

  // WhatsApp campaigns send an approved template, not free text. Detect the
  // selected inbox's channel and load its templates.
  const [templateName, setTemplateName] = useState<string>(
    (initial?.template_params as { name?: string } | null)?.name ?? "",
  );
  const [templateVars, setTemplateVars] = useState<Record<string, string>>(
    () => {
      const body = (
        initial?.template_params as {
          processed_params?: { body?: Record<string, string> };
        } | null
      )?.processed_params?.body;
      return body && typeof body === "object" ? { ...body } : {};
    },
  );
  const selectedInbox = inboxes.data?.find((ib) => String(ib.id) === inboxId);
  const isWhatsapp = selectedInbox?.channel_type === "Channel::Whatsapp";
  const templatesQ = useWhatsappTemplates(
    accountId,
    isWhatsapp ? Number(inboxId) : null,
    isWhatsapp,
  );
  const syncTemplates = useSyncWhatsappTemplates(
    accountId,
    isWhatsapp ? Number(inboxId) : null,
  );
  const selectedTemplate = templatesQ.data?.templates.find(
    (t) => t.name === templateName,
  );

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
    if (!title.trim()) return setError(t("agenda.dialog.titleRequired"));
    if (!inboxId)
      return setError(t("campaigns.form.pickInbox"));
    if (campaignType === "one_off" && !scheduledAt)
      return setError(t("campaigns.form.needsDate"));
    if (isWhatsapp && !templateName)
      return setError(t("campaigns.form.pickTemplate"));
    if (
      isWhatsapp &&
      (selectedTemplate?.variables ?? []).some(
        (n) => !(templateVars[String(n)] ?? "").trim(),
      )
    )
      return setError(t("campaigns.form.fillVariables"));

    // WhatsApp: build the template blob the backend validates + sends.
    let templateParams: Record<string, unknown> | null = null;
    if (isWhatsapp && templateName && selectedTemplate) {
      const body: Record<string, string> = {};
      for (const n of selectedTemplate.variables) {
        body[String(n)] = (templateVars[String(n)] ?? "").trim();
      }
      templateParams = {
        name: templateName,
        language: selectedTemplate.language,
        processed_params: { body },
      };
    }

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
      template_params: templateParams,
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
        (e as { message?: string })?.message ?? t("campaigns.form.saveFailed"),
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
          {t("agenda.dialog.titleLabel")}
        </Label>
        <Input
          id="c-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={255}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="c-desc">{t("products.form.description")}</Label>
        <Textarea
          id="c-desc"
          rows={2}
          value={description ?? ""}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label>{t("instagram.composer.typeLabel")}</Label>
        <div className="flex flex-wrap gap-3 text-sm">
          {CAMPAIGN_TYPES.map((ct) => (
            <label key={ct.value} className="flex items-center gap-1.5">
              <input
                type="radio"
                checked={campaignType === ct.value}
                onChange={() => setCampaignType(ct.value)}
                disabled={Boolean(initial)}
                className="accent-neon"
              />
              {t(ct.label)}
            </label>
          ))}
        </div>
        {initial ? (
          <p className="text-xs text-fg-muted">
            {t("campaigns.form.typeLocked")}
          </p>
        ) : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="c-inbox" required>
            {t("conversations.filters.attr.inbox")}
          </Label>
          <select
            id="c-inbox"
            className={selectClass}
            value={inboxId}
            onChange={(e) => setInboxId(e.target.value)}
          >
            <option value="">{t("campaigns.form.pickInboxPlaceholder")}</option>
            {inboxes.data?.map((ib) => (
              <option key={ib.id} value={ib.id}>
                {ib.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="c-sender">{t("campaigns.form.sender")}</Label>
          <select
            id="c-sender"
            className={selectClass}
            value={senderId}
            onChange={(e) => setSenderId(e.target.value)}
          >
            <option value="">{t("campaigns.form.noSender")}</option>
            {agents.data?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isWhatsapp ? (
        <div className="space-y-3 rounded-md border border-glass bg-surface-2 p-3">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
              {t("campaigns.form.waTemplate")}
            </p>
            <button
              type="button"
              onClick={() => syncTemplates.mutate()}
              disabled={syncTemplates.isPending}
              className="text-xs font-medium text-lit hover:underline disabled:opacity-50"
            >
              {syncTemplates.isPending
                ? t("campaigns.form.refreshing")
                : t("campaigns.form.refreshTemplates")}
            </button>
          </div>
          {templatesQ.isLoading ? (
            <p className="text-sm text-fg-muted">{t("campaigns.form.loadingTemplates")}</p>
          ) : (templatesQ.data?.templates.length ?? 0) === 0 ? (
            <p className="text-sm text-fg-muted">
              {t("campaigns.form.noTemplates")}
            </p>
          ) : (
            <>
              <div className="space-y-1.5">
                <Label htmlFor="c-tpl" required>
                  {t("campaigns.form.template")}
                </Label>
                <select
                  id="c-tpl"
                  className={selectClass}
                  value={templateName}
                  onChange={(e) => {
                    setTemplateName(e.target.value);
                    setTemplateVars({});
                  }}
                >
                  <option value="">{t("campaigns.form.pickTemplatePlaceholder")}</option>
                  {templatesQ.data!.templates.map((t) => (
                    <option key={`${t.name}:${t.language}`} value={t.name}>
                      {t.name} ({t.language})
                    </option>
                  ))}
                </select>
              </div>
              {selectedTemplate?.body_text ? (
                <p className="whitespace-pre-wrap rounded-md border border-glass bg-surface p-2 text-sm text-fg-muted">
                  {selectedTemplate.body_text}
                </p>
              ) : null}
              {(selectedTemplate?.variables ?? []).map((n) => (
                <div key={n} className="space-y-1.5">
                  <Label htmlFor={`c-var-${n}`} required>
                    {`Variable {{${n}}}`}
                  </Label>
                  <Input
                    id={`c-var-${n}`}
                    value={templateVars[String(n)] ?? ""}
                    onChange={(e) =>
                      setTemplateVars((prev) => ({
                        ...prev,
                        [String(n)]: e.target.value,
                      }))
                    }
                  />
                </div>
              ))}
            </>
          )}
        </div>
      ) : (
        <div className="space-y-1.5">
          <Label htmlFor="c-msg">{t("campaigns.form.message")}</Label>
          <Textarea
            id="c-msg"
            rows={3}
            value={message ?? ""}
            onChange={(e) => setMessage(e.target.value)}
          />
        </div>
      )}

      {campaignType === "one_off" ? (
        <div className="space-y-1.5">
          <Label htmlFor="c-when" required>
            {t("campaigns.form.scheduledAt")}
          </Label>
          <Input
            id="c-when"
            type="datetime-local"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            className="tabular-nums"
          />
          {labels.data?.length ? (
            <div className="mt-3 space-y-1.5">
              <Label>{t("campaigns.form.audience")}</Label>
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
                        "rounded-pill border px-2.5 py-0.5 text-xs transition-colors",
                        on
                          ? "border-neon bg-focused font-medium text-lit"
                          : "border-glass bg-field text-fg-muted hover:bg-hover-glass",
                      )}
                    >
                      {l.title}
                    </button>
                  );
                })}
              </div>
              <p className="text-xs text-fg-muted">
                {t("campaigns.form.noLabelsAll")}
              </p>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="space-y-3 rounded-md border border-glass bg-surface-2 p-3">
          <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
            {t("campaigns.form.triggerRules")}
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="c-url">{t("campaigns.form.urlPattern")}</Label>
              <Input
                id="c-url"
                value={urlPattern}
                onChange={(e) => setUrlPattern(e.target.value)}
                placeholder="https://midominio.com/pricing"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="c-time">{t("campaigns.form.timeOnPage")}</Label>
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
              className="accent-neon"
            />
            {t("campaigns.form.businessHoursOnly")}
          </label>
        </div>
      )}

      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
          className="accent-neon"
        />
        {t("campaigns.active")}
      </label>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? t("common.saveChanges") : t("campaigns.form.create")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          {t("actions.cancel")}
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
