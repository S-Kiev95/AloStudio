"use client";

import { ArrowLeft, ExternalLink, Plus, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { selectClassName } from "@/components/ui/select";
import { useInboxes } from "@/lib/api/inboxes";
import {
  type IntegrationApp,
  type IntegrationHook,
  useCreateIntegrationHook,
  useDeleteIntegrationHook,
  useIntegrationApp,
} from "@/lib/api/integrations";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";

export function IntegrationAppView({
  accountId,
  appId,
}: {
  accountId: string;
  appId: string;
}) {
  const t = useT();
  const { data: app, isLoading, isError } = useIntegrationApp(accountId, appId);

  return (
    <div className="max-w-3xl space-y-4">
      <Link
        href={`/accounts/${accountId}/settings/integrations`}
        className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        {t("settingsIntegrations.back")}
      </Link>

      {isLoading ? (
        <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
      ) : isError || !app ? (
        <p role="alert" className="p-8 text-center text-sm text-danger">
          {t("settingsIntegrations.loadFailed")}
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
                {t("settingsIntegrations.status", {
                  status: app.enabled
                    ? t("settingsIntegrations.available")
                    : t("campaigns.inactive"),
                })}
                {app.allow_multiple_hooks !== undefined
                  ? ` · ${t("settingsIntegrations.multipleConnections", {
                      value: app.allow_multiple_hooks ? t("actions.yes") : t("actions.no"),
                    })}`
                  : ""}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("settingsIntegrations.connections")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <ConnectSection accountId={accountId} app={app} />

              {app.hooks.length === 0 ? (
                <p className="text-sm text-fg-muted">
                  {t("settingsIntegrations.notConnected")}
                </p>
              ) : (
                <ul className="divide-y divide-glass">
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
  const t = useT();
  if (app.action && /^https?:\/\//.test(app.action)) {
    return (
      <div className="space-y-1">
        <a href={app.action} className={buttonVariants({ size: "sm" })}>
          <ExternalLink className="h-4 w-4" aria-hidden />
          {t("settingsIntegrations.connectWith", { name: app.name })}
        </a>
        <p className="text-xs text-fg-muted">
          {t("settingsIntegrations.authFlowNote", { name: app.name })}
        </p>
      </div>
    );
  }
  if (app.action) {
    return <InlineConnectForm accountId={accountId} app={app} />;
  }
  return (
    <p className="text-xs text-fg-muted">
      {t("settingsIntegrations.needsServerConfig")}
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
  const t = useT();
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
    if (needsInbox && !inboxId) return setError(t("settingsIntegrations.pickInbox"));
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
      setError((e as { message?: string })?.message ?? t("settingsIntegrations.connectFailed"));
    }
  }

  if (!open) {
    return (
      <Button size="sm" onClick={() => setOpen(true)}>
        <Plus className="h-4 w-4" aria-hidden />
        {t("settingsIntegrations.connect")}
      </Button>
    );
  }

  return (
    <div className="space-y-3 rounded-md border border-glass p-3">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      {needsInbox ? (
        <label className="block space-y-1 text-sm">
          <span className="text-fg-muted">{t("settingsIntegrations.inbox")}</span>
          <select
            aria-label={t("settingsIntegrations.inbox")}
            value={inboxId}
            onChange={(e) => setInboxId(e.target.value)}
            className={cn(selectClassName("sm"), "w-full")}
          >
            <option value="">{t("settingsIntegrations.pickInboxPlaceholder")}</option>
            {inboxes.data?.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <div className="space-y-2">
        <span className="text-sm text-fg-muted">{t("settingsIntegrations.settings")}</span>
        {rows.map((r, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <Input
              aria-label={t("settingsIntegrations.keyN", { n: idx + 1 })}
              placeholder={t("settingsIntegrations.keyPlaceholder")}
              value={r.key}
              onChange={(e) => setRow(idx, "key", e.target.value)}
            />
            <Input
              aria-label={t("settingsIntegrations.valueN", { n: idx + 1 })}
              placeholder={t("settingsIntegrations.valuePlaceholder")}
              value={r.value}
              onChange={(e) => setRow(idx, "value", e.target.value)}
            />
            <button
              type="button"
              aria-label={t("settingsIntegrations.removeSettingN", { n: idx + 1 })}
              onClick={() => setRows((rs) => rs.filter((_, i) => i !== idx))}
              disabled={rows.length === 1}
              className="rounded-sm p-1.5 text-fg-muted hover:text-danger disabled:opacity-40"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => setRows((rs) => [...rs, { key: "", value: "" }])}
          className="text-xs font-medium text-lit hover:underline"
        >
          {t("settingsIntegrations.addSetting")}
        </button>
      </div>

      <div className="flex gap-2">
        <Button size="sm" onClick={submit} loading={create.isPending}>
          {t("settingsIntegrations.connect")}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setOpen(false)}
          disabled={create.isPending}
        >
          {t("actions.cancel")}
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
  const t = useT();
  const del = useDeleteIntegrationHook(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    if (!window.confirm(t("settingsIntegrations.deleteConfirm"))) return;
    setError(null);
    try {
      await del.mutateAsync(hook.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? t("actions.deleteFailed"));
    }
  }

  return (
    <li className="flex items-center gap-3 py-3">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-fg">
          {hook.inbox ? hook.inbox.name : t("settingsIntegrations.globalConnection")}
        </p>
        <p className="text-xs text-fg-muted">
          {hook.hook_type} ·{" "}
          {hook.status
            ? t("settingsIntegrations.hookActive")
            : t("settingsIntegrations.hookInactive")}
          {hook.reference_id ? ` · ref ${hook.reference_id}` : ""} {/* i18n-ignore */}
        </p>
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
      <button
        type="button"
        aria-label={t("actions.delete")}
        title={t("actions.delete")}
        onClick={onDelete}
        disabled={del.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-hover-glass hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
    </li>
  );
}
