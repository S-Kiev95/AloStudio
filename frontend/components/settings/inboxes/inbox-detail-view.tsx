"use client";

import { ArrowLeft, Check, Copy, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { EmailBrandingPanel } from "./email-branding-panel";
import { EmailTemplatePanel } from "./email-template-panel";
import { EmailTransportPanel } from "./email-transport-panel";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/errors";
import {
  channelLabel,
  useDeleteInbox,
  useInbox,
  useUpdateInbox,
} from "@/lib/api/inboxes";

import { HandoffAssigneePanel } from "./handoff-assignee-panel";
import { InboxMembersPanel } from "./inbox-members-panel";
import { useT } from "@/lib/i18n/provider";

export function InboxDetailView({
  accountId,
  inboxId,
}: {
  accountId: string;
  inboxId: number;
}) {
  const t = useT();
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
      setError(t("profile.nameRequired"));
      return;
    }
    try {
      await update.mutateAsync({ id: inboxId, patch: { name: name.trim() } });
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("settingsInboxes.saveFailed"));
    }
  }

  async function onDelete() {
    if (!window.confirm(t("settingsInboxes.deleteConfirm", { name: inbox?.name ?? "" }))) return;
    setError(null);
    try {
      await del.mutateAsync(inboxId);
      router.push(listHref);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("actions.deleteFailed"));
    }
  }

  if (isLoading) {
    return <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>;
  }
  if (isError || !inbox) {
    return (
      <p role="alert" className="p-8 text-center text-sm text-danger">
        {t("settingsInboxes.loadFailed")}
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
          {t("settingsInboxes.inboxes")}
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
          <CardTitle className="text-base">{t("settingsInboxes.general")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={saveName} className="space-y-3">
            <label className="block space-y-1">
              <span className="text-sm font-medium text-fg">{t("profile.name")}</span>
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
                {t("actions.save")}
              </Button>
              {saved ? (
                <span className="text-xs text-success">{t("settingsInboxes.savedCheck")}</span>
              ) : null}
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("settings.items.agents")}</CardTitle>
        </CardHeader>
        <CardContent>
          <InboxMembersPanel accountId={accountId} inboxId={inboxId} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("settingsInboxes.whenBotHandsOff")}</CardTitle>
        </CardHeader>
        <CardContent>
          <HandoffAssigneePanel
            accountId={accountId}
            inboxId={inboxId}
            current={inbox.handoff_assignee_id ?? null}
          />
        </CardContent>
      </Card>

      {inbox.channel_type === "Channel::Email" ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("settingsInboxes.mailServer")}</CardTitle>
            <p className="mt-1 text-sm text-fg-muted">
              {t("settingsInboxes.mailServerHint")}
            </p>
          </CardHeader>
          <CardContent>
            <EmailTransportPanel accountId={accountId} inbox={inbox} />
          </CardContent>
        </Card>
      ) : null}

      {inbox.channel_type === "Channel::Email" ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("settingsInboxes.signatureAndLogo")}</CardTitle>
            <p className="mt-1 text-sm text-fg-muted">
              {t("settingsInboxes.signedFrom", {
                from: inbox.email ?? t("settingsInboxes.thisMailbox"),
              })}
            </p>
          </CardHeader>
          <CardContent>
            <EmailBrandingPanel accountId={accountId} inbox={inbox} />
          </CardContent>
        </Card>
      ) : null}

      {inbox.channel_type === "Channel::Email" ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("settingsInboxes.mailTemplate")}</CardTitle>
            <p className="mt-1 text-sm text-fg-muted">
              {t("settingsInboxes.mailTemplateHint")}
            </p>
          </CardHeader>
          <CardContent>
            <EmailTemplatePanel accountId={accountId} inbox={inbox} />
          </CardContent>
        </Card>
      ) : null}

      {inbox.callback_webhook_url ||
      inbox.inbox_identifier ||
      inbox.webhook_verify_token ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("settingsInboxes.webhook")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-fg-muted">
              {t("settingsInboxes.webhookHint")}
            </p>
            {/* i18n-ignore-start: the provider names these fields in English */}
            {inbox.callback_webhook_url ? (
              <CodeRow label="Callback URL" value={inbox.callback_webhook_url} />
            ) : null}
            {inbox.webhook_verify_token ? (
              <CodeRow label="Verify token" value={inbox.webhook_verify_token} />
            ) : null}
            {inbox.inbox_identifier ? (
              <CodeRow label="Inbox identifier" value={inbox.inbox_identifier} />
            ) : null}
            {/* i18n-ignore-end */}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
          <div>
            <p className="text-sm font-medium text-fg">{t("settingsInboxes.deleteInbox")}</p>
            <p className="text-xs text-fg-muted">
              {t("settingsInboxes.deleteInboxHint")}
            </p>
          </div>
          <Button
            variant="destructive"
            size="sm"
            onClick={onDelete}
            loading={del.isPending}
          >
            <Trash2 className="h-4 w-4" aria-hidden />
            {t("actions.delete")}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function CodeRow({ label, value }: { label: string; value: string }) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase text-fg-muted">{label}</p>
      <div className="flex items-center gap-2">
        <code className="block min-w-0 flex-1 truncate rounded bg-surface-2 px-2 py-1 font-numeric text-xs text-fg">
          {value}
        </code>
        <button
          type="button"
          aria-label={t("settingsInboxes.copyNamed", { label })}
          title={t("settingsMcp.copy")}
          onClick={() => {
            void navigator.clipboard.writeText(value);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
          className="shrink-0 rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {copied ? (
            <Check className="h-4 w-4 text-success" aria-hidden />
          ) : (
            <Copy className="h-4 w-4" aria-hidden />
          )}
        </button>
      </div>
    </div>
  );
}
