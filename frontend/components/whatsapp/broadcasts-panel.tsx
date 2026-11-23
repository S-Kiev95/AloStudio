"use client";

import { ChevronDown, ChevronRight, Plus, Send, Trash2, X } from "lucide-react";
import Link from "next/link";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import {
  type AudienceEntry,
  type Campaign,
  type CampaignRecipient,
  useCampaignAnalytics,
  useCampaignRecipients,
  useCampaigns,
  useCreateCampaign,
  useDeleteCampaign,
} from "@/lib/api/campaigns";
import { useLabels } from "@/lib/api/labels";
import { useIsAccountAdmin } from "@/lib/api/profile";
import { useWhatsappTemplates } from "@/lib/api/whatsapp-templates";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";
import { cn } from "@/lib/utils";

import { renderTemplateText, WhatsappTemplatePreview } from "./templates-panel";

const STATUS_KEY: Record<CampaignRecipient["status"], MessageKey> = {
  progress: "whatsapp.broadcasts.recipientStatus.progress",
  sent: "whatsapp.broadcasts.recipientStatus.sent",
  delivered: "whatsapp.broadcasts.recipientStatus.delivered",
  read: "whatsapp.broadcasts.recipientStatus.read",
  failed: "whatsapp.broadcasts.recipientStatus.failed",
};

const STATUS_CLASS: Record<CampaignRecipient["status"], string> = {
  progress: "text-fg-muted",
  sent: "text-fg-muted",
  delivered: "text-fg",
  read: "text-success",
  failed: "text-danger",
};

/** `{nombre}` / `{primer_nombre}` as the preview shows them. */
function sampleNames(text: string): string {
  return text.replaceAll("{primer_nombre}", "Ana").replaceAll("{nombre}", "Ana Pérez");
}

function formatDate(iso: string | null, intlTag: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(intlTag, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function NewBroadcastForm({
  accountId,
  inboxId,
  inboxName,
  onDone,
}: {
  accountId: string;
  inboxId: number;
  inboxName: string;
  onDone: () => void;
}) {
  const t = useT();
  const templatesQ = useWhatsappTemplates(accountId, inboxId, true);
  const labelsQ = useLabels(accountId);
  const create = useCreateCampaign(accountId);
  const [title, setTitle] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [vars, setVars] = useState<Record<string, string>>({});
  const [audienceKind, setAudienceKind] = useState<"inbox" | "labels">("labels");
  const [labelIds, setLabelIds] = useState<Set<number>>(new Set());
  const [when, setWhen] = useState<"now" | "later">("now");
  const [scheduledAt, setScheduledAt] = useState("");
  const [error, setError] = useState<string | null>(null);

  const templates = templatesQ.data?.templates ?? [];
  const template = templates.find((tpl) => tpl.name === templateName);
  const missingVar = (template?.variables ?? []).some((n) => !(vars[String(n)] ?? "").trim());
  const noAudience = audienceKind === "labels" && labelIds.size === 0;
  const noDate = when === "later" && !scheduledAt;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!template) return;
    setError(null);
    const body: Record<string, string> = {};
    for (const n of template.variables) body[String(n)] = (vars[String(n)] ?? "").trim();
    const audience: AudienceEntry[] =
      audienceKind === "inbox"
        ? [{ type: "Inbox" }]
        : Array.from(labelIds).map((id) => ({ type: "Label", id }));
    try {
      await create.mutateAsync({
        title: title.trim() || template.name,
        campaign_type: "one_off",
        inbox_id: inboxId,
        enabled: true,
        audience,
        scheduled_at:
          when === "now" ? new Date().toISOString() : new Date(scheduledAt).toISOString(),
        message: renderTemplateText(template.body_text ?? template.name, body),
        template_params: {
          name: template.name,
          language: template.language ?? "es",
          processed_params: { body },
        },
      });
      onDone();
    } catch (err) {
      setError((err as Error).message || t("whatsapp.broadcasts.createError"));
    }
  }

  return (
    <div
      role="dialog"
      aria-label={t("whatsapp.broadcasts.dialogTitle")}
      className="rounded-xl border border-glass bg-surface-2 p-5 sm:p-6"
    >
      <div className="mb-5 flex items-center justify-between border-b border-glass pb-3">
        <h3 className="text-sm font-semibold text-fg">
          {t("whatsapp.broadcasts.dialogTitle")}
        </h3>
        <button
          type="button"
          aria-label={t("whatsapp.common.close")}
          onClick={onDone}
          className="relative rounded-md p-1 text-fg-muted after:absolute after:-inset-2 after:content-[''] hover:bg-hover-glass hover:text-fg"
        >
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>
      <form
        onSubmit={(e) => void submit(e)}
        className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]"
      >
        <div className="space-y-5">
          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          ) : null}
          <div className="space-y-1.5">
            <Label htmlFor="bc-title">{t("whatsapp.broadcasts.titleLabel")}</Label>
            <Input
              id="bc-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t("whatsapp.broadcasts.titlePlaceholder")}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="bc-template">{t("whatsapp.broadcasts.templateLabel")}</Label>
            {templatesQ.isLoading ? (
              <p className="text-sm text-fg-muted">
                {t("whatsapp.broadcasts.loadingTemplates")}
              </p>
            ) : templates.length === 0 ? (
              <p className="text-sm text-fg-muted">{t("whatsapp.broadcasts.noTemplates")}</p>
            ) : (
              <select
                id="bc-template"
                className={selectClassName()}
                value={templateName}
                onChange={(e) => {
                  setTemplateName(e.target.value);
                  setVars({});
                }}
              >
                <option value="">{t("whatsapp.broadcasts.selectTemplate")}</option>
                {templates.map((tpl) => (
                  <option key={`${tpl.name}:${tpl.language}`} value={tpl.name}>
                    {tpl.name} ({tpl.language})
                  </option>
                ))}
              </select>
            )}
          </div>

          {template && template.variables.length > 0 ? (
            <div className="space-y-3">
              <p className="text-xs text-fg-muted">
                {t("whatsapp.broadcasts.variablesHintPrefix")}{" "}
                <code>{"{nombre}"}</code> {t("whatsapp.broadcasts.variablesHintOr")}{" "}
                <code>{"{primer_nombre}"}</code>{" "}
                {t("whatsapp.broadcasts.variablesHintSuffix")}
              </p>
              {template.variables.map((n) => (
                <div key={n} className="space-y-1.5">
                  <Label htmlFor={`bc-var-${n}`}>
                    {t("whatsapp.broadcasts.variableLabel", { n })}
                  </Label>
                  <Input
                    id={`bc-var-${n}`}
                    value={vars[String(n)] ?? ""}
                    onChange={(e) => setVars((v) => ({ ...v, [String(n)]: e.target.value }))}
                  />
                </div>
              ))}
            </div>
          ) : null}

          <fieldset className="space-y-2">
            <legend className="mb-1 text-sm font-medium text-fg">
              {t("whatsapp.broadcasts.audienceLegend")}
            </legend>
            <label className="flex items-center gap-2 text-sm text-fg">
              <input
                type="radio"
                name="bc-audience"
                checked={audienceKind === "labels"}
                onChange={() => setAudienceKind("labels")}
              />
              {t("whatsapp.broadcasts.audienceLabels")}
            </label>
            {audienceKind === "labels" ? (
              <div className="flex flex-wrap gap-1.5 pl-6">
                {(labelsQ.data ?? []).length === 0 ? (
                  <p className="text-xs text-fg-muted">
                    {t("whatsapp.broadcasts.noLabels")}
                  </p>
                ) : (
                  (labelsQ.data ?? []).map((l) => {
                    const on = labelIds.has(l.id);
                    return (
                      <button
                        key={l.id}
                        type="button"
                        aria-pressed={on}
                        onClick={() =>
                          setLabelIds((prev) => {
                            const next = new Set(prev);
                            if (on) next.delete(l.id);
                            else next.add(l.id);
                            return next;
                          })
                        }
                        className={cn(
                          "rounded-pill border px-2.5 py-1 text-xs",
                          on
                            ? "border-neon bg-focused text-lit"
                            : "border-glass text-fg-muted hover:bg-hover-glass",
                        )}
                      >
                        {l.title}
                      </button>
                    );
                  })
                )}
              </div>
            ) : null}
            <label className="flex items-center gap-2 text-sm text-fg">
              <input
                type="radio"
                name="bc-audience"
                checked={audienceKind === "inbox"}
                onChange={() => setAudienceKind("inbox")}
              />
              {t("whatsapp.broadcasts.audienceInbox")}
            </label>
          </fieldset>

          <fieldset className="space-y-2">
            <legend className="mb-1 text-sm font-medium text-fg">
              {t("whatsapp.broadcasts.whenLegend")}
            </legend>
            <label className="flex items-center gap-2 text-sm text-fg">
              <input
                type="radio"
                name="bc-when"
                checked={when === "now"}
                onChange={() => setWhen("now")}
              />
              {t("whatsapp.broadcasts.whenNow")}
            </label>
            <label className="flex items-center gap-2 text-sm text-fg">
              <input
                type="radio"
                name="bc-when"
                checked={when === "later"}
                onChange={() => setWhen("later")}
              />
              {t("whatsapp.broadcasts.whenLater")}
            </label>
            {when === "later" ? (
              <Input
                aria-label={t("whatsapp.broadcasts.scheduledAtAria")}
                type="datetime-local"
                className="ml-6 w-auto"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
              />
            ) : null}
          </fieldset>

          <p className="rounded-lg border border-glass bg-surface px-3 py-2 text-xs text-fg-muted">
            {t("whatsapp.broadcasts.metaBillingNotice")}
          </p>

          <div className="flex gap-2">
            <Button
              type="submit"
              size="sm"
              loading={create.isPending}
              disabled={!template || missingVar || noAudience || noDate}
            >
              <Send className="h-4 w-4" aria-hidden />
              {when === "now"
                ? t("whatsapp.broadcasts.sendNow")
                : t("whatsapp.broadcasts.scheduleSend")}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={onDone}>
              {t("whatsapp.common.cancel")}
            </Button>
          </div>
        </div>

        <div className="space-y-2 lg:sticky lg:top-4 lg:self-start">
          <p className="text-xs font-medium text-fg-muted">
            {t("whatsapp.broadcasts.previewHeading")}
          </p>
          <WhatsappTemplatePreview
            framed
            businessName={inboxName}
            body={template?.body_text ?? ""}
            bodyValues={Object.fromEntries(
              Object.entries(vars).map(([k, v]) => [k, sampleNames(v)]),
            )}
          />
        </div>
      </form>
    </div>
  );
}

function BroadcastResults({ accountId, campaign }: { accountId: string; campaign: Campaign }) {
  const t = useT();
  const analytics = useCampaignAnalytics(accountId, campaign.display_id);
  const recipientsQ = useCampaignRecipients(accountId, campaign.display_id);
  const d = analytics.data?.delivery;
  const recipients = recipientsQ.data ?? [];
  return (
    <div className="space-y-4 border-t border-glass px-4 py-4">
      {d ? (
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          {(
            [
              [t("whatsapp.broadcasts.statRecipients"), analytics.data?.messages_count ?? 0],
              [t("whatsapp.broadcasts.statSent"), d.sent],
              [t("whatsapp.broadcasts.statDelivered"), d.delivered],
              [t("whatsapp.broadcasts.statRead"), d.read],
              [t("whatsapp.broadcasts.statFailed"), d.failed],
            ] as const
          ).map(([label, value]) => (
            <div key={label} className="rounded-lg border border-glass bg-surface-2 px-3 py-2">
              <dt className="text-[11px] uppercase tracking-wide text-fg-muted">{label}</dt>
              <dd className="text-lg font-semibold text-fg">{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {recipientsQ.isLoading ? (
        <p className="text-sm text-fg-muted">{t("whatsapp.broadcasts.loadingRecipients")}</p>
      ) : recipients.length === 0 ? (
        <p className="text-sm text-fg-muted">
          {campaign.campaign_status === "completed"
            ? t("whatsapp.broadcasts.noRecipientsCompleted")
            : t("whatsapp.broadcasts.notSentYet")}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="text-xs text-fg-muted">
              <tr>
                <th className="py-1.5 pr-3 font-medium">
                  {t("whatsapp.broadcasts.colContact")}
                </th>
                <th className="py-1.5 pr-3 font-medium">
                  {t("whatsapp.broadcasts.colPhone")}
                </th>
                <th className="py-1.5 pr-3 font-medium">
                  {t("whatsapp.broadcasts.colStatus")}
                </th>
                <th className="py-1.5 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-glass">
              {recipients.map((r) => (
                <tr key={`${r.contact_id}-${r.conversation_id}`}>
                  <td className="py-2 pr-3 text-fg">
                    {r.name ?? t("whatsapp.common.withoutName")}
                  </td>
                  <td className="py-2 pr-3 text-fg-muted">{r.phone_number ?? ""}</td>
                  <td className={cn("py-2 pr-3", STATUS_CLASS[r.status])}>
                    {STATUS_KEY[r.status] ? t(STATUS_KEY[r.status]) : r.status}
                    {r.error ? (
                      <span className="block text-xs text-danger">{r.error}</span>
                    ) : null}
                  </td>
                  <td className="py-2 text-right">
                    <Link
                      href={`/accounts/${accountId}/conversations/${r.conversation_id}`}
                      className="text-xs text-lit underline-offset-2 hover:underline"
                    >
                      {t("whatsapp.broadcasts.viewChat")}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** Mass sends of an approved template from one WhatsApp number (one-off
 *  campaigns of that inbox), with per-contact delivery results. */
export function BroadcastsPanel({
  accountId,
  inboxId,
  inboxName,
}: {
  accountId: string;
  inboxId: number;
  inboxName: string;
}) {
  const t = useT();
  const intlTag = useIntlTag();
  const confirm = useConfirm();
  const isAdmin = useIsAccountAdmin(accountId);
  const campaignsQ = useCampaigns(accountId);
  const remove = useDeleteCampaign(accountId);
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<number | null>(null);

  if (!isAdmin) {
    return <p className="text-sm text-fg-muted">{t("whatsapp.broadcasts.adminOnly")}</p>;
  }

  const broadcasts = (campaignsQ.data ?? [])
    .filter((c) => c.inbox_id === inboxId && c.campaign_type === "one_off")
    .sort((a, b) => b.display_id - a.display_id);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-fg-muted">{t("whatsapp.broadcasts.intro")}</p>
        {!creating ? (
          <Button type="button" size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            {t("whatsapp.broadcasts.newBroadcast")}
          </Button>
        ) : null}
      </div>

      {creating ? (
        <NewBroadcastForm
          accountId={accountId}
          inboxId={inboxId}
          inboxName={inboxName}
          onDone={() => setCreating(false)}
        />
      ) : null}

      {campaignsQ.isLoading ? (
        <p className="text-sm text-fg-muted">{t("whatsapp.broadcasts.loading")}</p>
      ) : broadcasts.length === 0 ? (
        <p className="py-4 text-center text-sm text-fg-muted">
          {t("whatsapp.broadcasts.empty")}
        </p>
      ) : (
        <ul className="divide-y divide-glass overflow-hidden rounded-xl border border-glass bg-surface">
          {broadcasts.map((c) => {
            const done = c.campaign_status === "completed";
            const tpl = (c.template_params?.name as string | undefined) ?? "";
            const expanded = open === c.display_id;
            return (
              <li key={c.display_id}>
                <div className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <button
                    type="button"
                    aria-expanded={expanded}
                    onClick={() => setOpen(expanded ? null : c.display_id)}
                    className="flex min-w-0 flex-1 items-center gap-2 text-left"
                  >
                    {expanded ? (
                      <ChevronDown className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
                    )}
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-fg">
                        {c.title}
                      </span>
                      <span className="block text-xs text-fg-muted">
                        {tpl ? <span className="font-mono">{tpl}</span> : null}
                        {tpl ? " · " : ""}
                        {formatDate(c.scheduled_at, intlTag)}
                      </span>
                    </span>
                  </button>
                  <span
                    className={cn(
                      "rounded-pill border px-2 py-0.5 text-xs font-medium",
                      done ? "border-success text-success" : "border-warning text-warning",
                    )}
                  >
                    {done
                      ? t("whatsapp.broadcasts.statusSent")
                      : t("whatsapp.broadcasts.statusScheduled")}
                  </span>
                  {!done ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-danger hover:text-danger"
                      loading={remove.isPending}
                      onClick={async () => {
                        if (await confirm(t("whatsapp.broadcasts.cancelConfirm"))) {
                          remove.mutate(c.display_id);
                        }
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden />
                      {t("whatsapp.common.cancel")}
                    </Button>
                  ) : null}
                </div>
                {expanded ? <BroadcastResults accountId={accountId} campaign={c} /> : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
